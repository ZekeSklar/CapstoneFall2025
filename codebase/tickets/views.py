from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.core.exceptions import PermissionDenied

from django.shortcuts import get_object_or_404, redirect, render

from django.urls import reverse, reverse_lazy

from django.core.mail import send_mail

from django.conf import settings



from .models import Printer, PrinterGroup, RequestTicket

from .forms import SupplyRequestForm, IssueReportForm, SupplyItemFormSet





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





def _user_can_manage_printer(user, printer: Printer) -> bool:

    if not printer.group:

        return False

    return printer.group.managers.filter(pk=user.pk).exists()





def _managed_groups_queryset(user):

    return user.managed_printer_groups.prefetch_related("printers").order_by("name")





def _get_managed_group(user, group_id: int) -> PrinterGroup:

    group = get_object_or_404(PrinterGroup.objects.prefetch_related('printers'), pk=group_id)

    if not group.managers.filter(pk=user.pk).exists():

        raise PermissionDenied("You are not assigned to this printer group.")

    return group





def printer_portal(request, qr_token):

    printer = get_object_or_404(Printer, qr_token=qr_token)

    group_printers = None

    if printer.group:

        group_printers = list(printer.group.printers.order_by('campus_label'))



    can_order = request.user.is_authenticated and request.user.is_staff



    return render(request, 'tickets/portal.html', {

        'printer': printer,

        'group_printers': group_printers,

        'can_order': can_order,

    })





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

                group_name = ticket.group.name or ticket.group.building or 'group'

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





def printer_issue(request, qr_token):

    printer = get_object_or_404(Printer, qr_token=qr_token)

    if request.method == 'POST':

        form = IssueReportForm(request.POST)

        if form.is_valid():

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

    groups = list(_managed_groups_queryset(request.user))

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

            group_name = group.name or group.building or 'group'

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

    items_initial = [{'supply_type': 'Copy paper (case)', 'supply_quantity': 1}]

    return _handle_group_order_request(

        request,

        group,

        items_initial=items_initial,

        allow_item_add=False,

        success_message='Paper request submitted to Printing Services.',

    )





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

