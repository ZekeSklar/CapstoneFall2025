from datetime import timedelta

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.core.exceptions import PermissionDenied

from django.shortcuts import get_object_or_404, redirect, render

from django.urls import reverse, reverse_lazy

from django.core.mail import send_mail
from django.http import JsonResponse

from django.conf import settings
from django.views.decorators.http import require_GET

from django.utils import timezone



from .models import Printer, PrinterGroup, RequestTicket

from .forms import SupplyRequestForm, IssueReportForm, SupplyItemFormSet
from .printer_status import (
    POLL_INTERVAL_SECONDS,
    ensure_latest_status,
    build_status_payload,
    attach_status_to_printers,
)





def _combine_details(base: str, extra_lines: list[str]) -> str:

    details = (base or "").strip()

    if extra_lines:

        if details:

            details += "\n\n"

        details += "\n".join(extra_lines)

    return details





def _send_ticket_email(ticket: RequestTicket, printer: Printer, scope_label: str) -> None:

    body_lines = [

        f"Printer: {printer.campus_label} | {printer.asset_tag}",

        f"Location: {printer.building} / {printer.location_in_building}",

        f"Make/Model: {printer.make} {printer.model}",

        f"IP/MAC: {printer.ip_address} / {printer.mac_address}",

        "",

        f"Scope: {scope_label}",

        f"Requester: {ticket.requester_name} <{ticket.requester_email}>",

        "",

        "Details:",

        ticket.details or "(none)",

    ]

    if ticket.applies_to_group and ticket.group:

        body_lines.append("")

        body_lines.append("Group members:")

        for member in ticket.group.printers.order_by('campus_label'):

            body_lines.append(

                f"  - {member.campus_label} | {member.asset_tag} | {member.location_in_building}"

            )



    subject = f"[{ticket.type}] {printer.campus_label} ({printer.asset_tag})"

    body = "\n".join(body_lines)

    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, settings.EMAIL_TO or ["sklarz@berea.edu"])





ISSUE_RATE_LIMIT_MAX = 3

ISSUE_RATE_LIMIT_WINDOW = timedelta(hours=1)


def _issue_rate_limit_reached(printer: Printer) -> bool:

    window_start = timezone.now() - ISSUE_RATE_LIMIT_WINDOW

    recent_count = RequestTicket.objects.filter(

        printer=printer,

        type=RequestTicket.ISSUE,

        created_at__gte=window_start,

    ).count()

    return recent_count >= ISSUE_RATE_LIMIT_MAX



def _user_can_manage_printer(user, printer: Printer) -> bool:

    if not printer.group:

        return False

    return printer.group.managers.filter(pk=user.pk).exists()





def _managed_groups_queryset(user):

    return user.managed_printer_groups.prefetch_related("printers", "printers__status").order_by("name")





def _get_managed_group(user, group_id: int) -> PrinterGroup:

    group = get_object_or_404(PrinterGroup.objects.prefetch_related('printers'), pk=group_id)

    if not group.managers.filter(pk=user.pk).exists():

        raise PermissionDenied("You are not assigned to this printer group.")

    return group






_TRUTHY_QUERY_VALUES = {'1', 'true', 'yes', 'y', 'on', 'force', 'now'}


def _query_flag(request, name: str) -> bool:
    value = request.GET.get(name)
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_QUERY_VALUES


def printer_portal(request, qr_token):

    printer = get_object_or_404(Printer, qr_token=qr_token)

    group_printers = None

    if printer.group:

        group_printers = list(printer.group.printers.order_by('campus_label'))



    can_order = request.user.is_authenticated and request.user.is_staff



    return render(
        request,
        'tickets/portal.html',
        {
            'printer': printer,
            'group_printers': group_printers,
            'can_order': can_order,
        },
    )


@login_required
@require_GET
@login_required
@require_GET
def manager_printer_status(request, printer_id):
    """Manager-only status endpoint (by printer id). Returns same shape as manager feed.

    Useful when showing live status in non-QR parts of the site (requires login
    and group management permission).
    """
    printer = get_object_or_404(Printer.objects.select_related('group'), pk=printer_id)
    if not _user_can_manage_printer(request.user, printer):
        raise PermissionDenied('You are not assigned to this printer.')

    force = _query_flag(request, 'force') or _query_flag(request, 'refresh')
    status = ensure_latest_status(printer, force=force)
    payload = build_status_payload(printer, status)
    # Return same top-level shape as manager_status_feed uses
    resp = JsonResponse({'printers': [payload], 'poll_interval_seconds': POLL_INTERVAL_SECONDS})
    resp['Cache-Control'] = 'no-store'
    return resp
@login_required
@require_GET
def manager_status_feed(request):

    force = _query_flag(request, 'force') or _query_flag(request, 'refresh')
    printer_id = request.GET.get('printer')

    payloads: list[dict] = []

    if printer_id:

        printer = get_object_or_404(Printer.objects.select_related('group'), pk=printer_id)

        if not _user_can_manage_printer(request.user, printer):

            raise PermissionDenied('You are not assigned to this printer.')

        status = ensure_latest_status(printer, force=force)
        payloads.append(build_status_payload(printer, status))

    else:

        groups = list(_managed_groups_queryset(request.user))

        for group in groups:

            for printer in group.printers.all():

                status = ensure_latest_status(printer, force=force)
                payloads.append(build_status_payload(printer, status))

    resp = JsonResponse({'printers': payloads, 'poll_interval_seconds': POLL_INTERVAL_SECONDS})
    resp['Cache-Control'] = 'no-store'
    return resp

@login_required(login_url=reverse_lazy('admin:login'))

def printer_order(request, qr_token):

    printer = get_object_or_404(Printer, qr_token=qr_token)

    if not request.user.is_staff:

        raise PermissionDenied("Supply ordering is restricted to staff.")



    if request.method == 'POST':

        items_formset = SupplyItemFormSet(request.POST, prefix='items')

        form = SupplyRequestForm(request.POST, printer=printer)

        if form.is_valid() and items_formset.is_valid():

            ticket = form.save(commit=False)

            ticket.printer = printer

            ticket.type = RequestTicket.SUPPLY



            apply_to_group = bool(form.cleaned_data.get('apply_to_group') and printer.group)

            ticket.applies_to_group = apply_to_group

            ticket.group = printer.group if apply_to_group else None



            extra = []

            for idx, item in enumerate([item for item in items_formset.cleaned_data if item], start=1):

                if not item:

                    continue

                extra.append(f"Item {idx}: {item['supply_type']} (qty {item['supply_quantity']})")

            if ticket.applies_to_group and ticket.group:
                group_name = ticket.group.name or 'group'
                extra.append(f"Scope: Applies to entire group ({group_name})")



            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)

            ticket.save()



            scope = 'Group' if ticket.applies_to_group else 'Single printer'

            _send_ticket_email(ticket, printer, scope)

            return redirect(reverse('ticket_thanks'))

    else:

        form = SupplyRequestForm(printer=printer)

        items_formset = SupplyItemFormSet(prefix='items', initial=[{}])



    group_printers = None

    if printer.group:

        group_printers = list(printer.group.printers.order_by('campus_label'))



    return render(request, 'tickets/supply_form.html', {

        'printer': printer,

        'form': form,

        'items_formset': items_formset,

        'group_printers': group_printers,

    })

@login_required(login_url=reverse_lazy('admin:login'))
def printer_paper_order(request, qr_token):
    printer = get_object_or_404(Printer.objects.select_related('group'), qr_token=qr_token)
    if not request.user.is_staff:
        raise PermissionDenied("Supply ordering is restricted to staff.")

    group_param = request.GET.get('group')
    target_group = None
    if group_param:
        target_group = _get_managed_group(request.user, group_param)
        if not printer.group or str(printer.group_id) != str(target_group.id):
            raise PermissionDenied("This printer is not part of the requested group.")

    initial_items = [{'supply_type': 'Copy paper (case)', 'supply_quantity': 1}]
    allow_item_add = False

    if request.method == 'POST':
        items_formset = SupplyItemFormSet(request.POST, prefix='items')
        for form in items_formset.forms:
            form.fields['supply_type'].widget.input_type = 'hidden'
        form = SupplyRequestForm(
            request.POST,
            printer=printer,
            user=request.user,
            manager_override=False,
            force_apply_to_group=bool(target_group),
        )
        if form.is_valid() and items_formset.is_valid():
            ticket = form.save(commit=False)
            ticket.printer = printer
            ticket.type = RequestTicket.SUPPLY
            ticket.applies_to_group = bool(target_group)
            ticket.group = target_group if target_group else None

            extra = []
            for idx, item in enumerate([item for item in items_formset.cleaned_data if item], start=1):
                if not item:
                    continue
                item['supply_type'] = 'Copy paper (case)'
                extra.append(f"Item {idx}: {item['supply_type']} (qty {item['supply_quantity']})")

            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)
            ticket.save()

            scope_label = 'Group order' if ticket.applies_to_group else 'Single printer'
            _send_ticket_email(ticket, printer, scope_label)
            messages.success(request, 'Paper order submitted to Printing Services.')
            return redirect('ticket_thanks')
    else:
        items_formset = SupplyItemFormSet(prefix='items', initial=initial_items)
        for form in items_formset.forms:
            form.fields['supply_type'].widget.input_type = 'hidden'
        initial_data = {
            'requester_name': (request.user.get_full_name() or '').strip() or request.user.get_username(),
            'requester_email': request.user.email or ''
        }
        form = SupplyRequestForm(
            printer=printer,
            user=request.user,
            manager_override=False,
            force_apply_to_group=bool(target_group),
            initial=initial_data,
        )

    return render(request, 'tickets/paper_form.html', {
        'printer': printer,
        'group': target_group,
        'form': form,
        'items_formset': items_formset,
        'allow_item_add': allow_item_add,
    })





def printer_issue(request, qr_token):

    printer = get_object_or_404(Printer, qr_token=qr_token)

    if request.method == 'POST':

        form = IssueReportForm(request.POST)

        if form.is_valid():

            if _issue_rate_limit_reached(printer):

                return redirect(reverse('ticket_thanks'))

            ticket = form.save(commit=False)

            ticket.printer = printer

            ticket.type = RequestTicket.ISSUE

            ticket.applies_to_group = False

            ticket.group = None



            extra = [f"Issue category: {form.cleaned_data['issue_category']}"]

            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)

            ticket.save()

            _send_ticket_email(ticket, printer, scope_label='Single printer')

            return redirect(reverse('ticket_thanks'))

    else:

        form = IssueReportForm()



    return render(request, 'tickets/issue_form.html', {

        'printer': printer,

        'form': form,

    })





@login_required
def manager_dashboard(request):
    """
    Manager landing page.

    Avoid synchronous SNMP fetches on initial render so the page loads fast.
    Use cached PrinterStatus payloads and let the frontend refresh via
    manager_status_feed (AJAX).
    """
    groups = list(_managed_groups_queryset(request.user))

    # Collect all printers, attach cached statuses in one query
    all_printers = []
    for g in groups:
        all_printers.extend(list(g.printers.all()))
    attach_status_to_printers(all_printers)

    status_payloads: list[dict] = []
    attention_labels: list[str] = []
    snmp_fault_labels: list[str] = []

    for group in groups:
        for printer in group.printers.all():
            status = getattr(printer, 'status_cached', None)
            payload = build_status_payload(printer, status)
            status_payloads.append(payload)
            printer.status_payload = payload

            status_data = payload.get('status', {})
            if status_data.get('attention'):
                attention_labels.append(payload['printer']['campus_label'])
            if not status_data.get('snmp_ok', True):
                snmp_fault_labels.append(payload['printer']['campus_label'])

    attention_labels.sort()
    snmp_fault_labels.sort()

    group_ids = [group.id for group in groups]

    recent_issues = []

    if group_ids:

        recent_issues = list(

            RequestTicket.objects.filter(

                type=RequestTicket.ISSUE,

                printer__group_id__in=group_ids,

            ).select_related('printer').order_by('-created_at')[:25]

        )



    display_name = (request.user.get_full_name() or '').strip() or request.user.get_username()

    context = {

        'display_name': display_name,

        'groups': groups,

        'recent_issues': recent_issues,

        'missing_email': not bool(request.user.email),

        'printer_status_payloads': status_payloads,

        'attention_count': len(attention_labels),

        'attention_labels': attention_labels,

        'snmp_fault_count': len(snmp_fault_labels),

        'snmp_fault_labels': snmp_fault_labels,

        'poll_interval_seconds': POLL_INTERVAL_SECONDS,

    }

    return render(request, 'tickets/manager_dashboard.html', context)







@login_required

def manager_printer_order(request, printer_id):

    printer = get_object_or_404(Printer.objects.select_related('group'), pk=printer_id)

    if not _user_can_manage_printer(request.user, printer):

        raise PermissionDenied('You are not assigned to this printer.')



    if not request.user.email:

        messages.error(request, 'Add an email address to your account before submitting an order.')

        return redirect('manager_dashboard')



    initial = {}

    display_name = (request.user.get_full_name() or '').strip() or request.user.get_username()

    if display_name:

        initial['requester_name'] = display_name

    if request.user.email:

        initial['requester_email'] = request.user.email



    if request.method == 'POST':

        items_formset = SupplyItemFormSet(request.POST, prefix='items')

        form = SupplyRequestForm(

            request.POST,

            printer=printer,

            user=request.user,

            manager_override=True,

        )

        if form.is_valid() and items_formset.is_valid():

            ticket = form.save(commit=False)

            ticket.printer = printer

            ticket.type = RequestTicket.SUPPLY



            apply_to_group = bool(form.cleaned_data.get('apply_to_group') and printer.group)

            ticket.applies_to_group = apply_to_group

            ticket.group = printer.group if apply_to_group else None



            extra = []

            for idx, item in enumerate([item for item in items_formset.cleaned_data if item], start=1):

                if not item:

                    continue

                extra.append(f"Item {idx}: {item['supply_type']} (qty {item['supply_quantity']})")

            if ticket.applies_to_group and ticket.group:

                group_name = ticket.group.name or ticket.group.building or 'group'

                extra.append(f"Scope: Applies to entire group ({group_name})")



            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)

            ticket.save()



            scope = 'Group' if ticket.applies_to_group else 'Single printer'

            _send_ticket_email(ticket, printer, scope)

            messages.success(request, 'Supply order submitted to Printing Services.')

            return redirect('manager_dashboard')

    else:

        form = SupplyRequestForm(

            printer=printer,

            user=request.user,

            manager_override=True,

            initial=initial,

        )

        items_formset = SupplyItemFormSet(prefix='items', initial=[{}])



    return render(request, 'tickets/manager_supply_form.html', {

        'printer': printer,

        'group': printer.group,

        'group_mode': False,

        'allow_item_add': True,

        'form': form,

        'items_formset': items_formset,

        'group_printers': list(printer.group.printers.order_by('campus_label')) if printer.group else None,

    })





def _handle_group_order_request(request, group: PrinterGroup, items_initial=None, allow_item_add=True, success_message='Supply order submitted to Printing Services.'):

    primary_printer = group.printers.order_by('campus_label').first()

    if not primary_printer:

        messages.error(request, 'This group does not have any printers assigned yet.')

        return redirect('manager_dashboard')



    if not request.user.email:

        messages.error(request, 'Add an email address to your account before submitting an order.')

        return redirect('manager_dashboard')



    user_initial = {}

    display_name = (request.user.get_full_name() or '').strip() or request.user.get_username()

    if display_name:

        user_initial['requester_name'] = display_name

    if request.user.email:

        user_initial['requester_email'] = request.user.email



    if request.method == 'POST':

        items_formset = SupplyItemFormSet(request.POST, prefix='items')

        form = SupplyRequestForm(

            request.POST,

            printer=primary_printer,

            user=request.user,

            manager_override=True,

            force_apply_to_group=True,

        )

        if form.is_valid() and items_formset.is_valid():

            ticket = form.save(commit=False)

            ticket.printer = primary_printer

            ticket.group = group

            ticket.type = RequestTicket.SUPPLY

            ticket.applies_to_group = True



            extra = []

            for idx, item in enumerate([item for item in items_formset.cleaned_data if item], start=1):

                if not item:

                    continue

                extra.append(f"Item {idx}: {item['supply_type']} (qty {item['supply_quantity']})")

            group_name = group.name or 'group'

            extra.append(f"Scope: Applies to entire group ({group_name})")



            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)

            ticket.save()



            _send_ticket_email(ticket, primary_printer, scope_label='Group order')

            messages.success(request, success_message)

            return redirect('manager_dashboard')

    else:

        initial_items = items_initial if items_initial is not None else [{}]

        items_formset = SupplyItemFormSet(prefix='items', initial=initial_items)

        form = SupplyRequestForm(

            printer=primary_printer,

            user=request.user,

            manager_override=True,

            force_apply_to_group=True,

            initial=user_initial,

        )



    return render(request, 'tickets/manager_supply_form.html', {

        'printer': primary_printer,

        'group': group,

        'group_mode': True,

        'allow_item_add': allow_item_add,

        'form': form,

        'items_formset': items_formset,

        'group_printers': list(group.printers.order_by('campus_label')),

    })





@login_required

def manager_group_order(request, group_id):

    group = _get_managed_group(request.user, group_id)

    return _handle_group_order_request(request, group)





@login_required

def manager_group_quick_paper(request, group_id):

    group = _get_managed_group(request.user, group_id)

    primary = group.printers.order_by('campus_label').first()
    if not primary:
        messages.error(request, 'This group does not have any printers assigned yet.')
        return redirect('manager_dashboard')

    url = reverse('printer_paper_order', args=[primary.qr_token])
    return redirect(f"{url}?group={group.id}")





@login_required

def manager_printer_issue(request, printer_id):

    printer = get_object_or_404(Printer.objects.select_related('group'), pk=printer_id)

    if not _user_can_manage_printer(request.user, printer):

        raise PermissionDenied('You are not assigned to this printer.')



    if not request.user.email:

        messages.error(request, 'Add an email address to your account before reporting issues.')

        return redirect('manager_dashboard')



    initial = {}

    display_name = (request.user.get_full_name() or '').strip() or request.user.get_username()

    if display_name:

        initial['requester_name'] = display_name

    if request.user.email:

        initial['requester_email'] = request.user.email



    if request.method == 'POST':

        form = IssueReportForm(

            request.POST,

            user=request.user,

            manager_override=True,

        )

        if form.is_valid():

            if _issue_rate_limit_reached(printer):

                messages.success(request, 'Issue reported to Printing Services.')

                return redirect('manager_dashboard')

            ticket = form.save(commit=False)

            ticket.printer = printer

            ticket.type = RequestTicket.ISSUE

            ticket.applies_to_group = False

            ticket.group = printer.group if printer.group else None



            extra = [f"Issue category: {form.cleaned_data['issue_category']}"]

            ticket.details = _combine_details(form.cleaned_data.get('details'), extra)

            ticket.save()

            _send_ticket_email(ticket, printer, scope_label='Single printer')

            messages.success(request, 'Issue reported to Printing Services.')

            return redirect('manager_dashboard')

    else:

        form = IssueReportForm(user=request.user, manager_override=True, initial=initial)



    recent_issues = RequestTicket.objects.filter(

        type=RequestTicket.ISSUE,

        printer=printer,

    ).order_by('-created_at')[:10]



    return render(request, 'tickets/manager_issue_form.html', {

        'printer': printer,

        'form': form,

        'recent_issues': recent_issues,

    })





def ticket_thanks(request):

    return render(request, 'tickets/thanks.html')

