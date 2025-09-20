from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings

from .models import Printer, RequestTicket
from .forms import RequestTicketForm


def printer_portal(request, qr_token):
    printer = get_object_or_404(Printer, qr_token=qr_token)

    if request.method == 'POST':
        form = RequestTicketForm(request.POST, printer=printer)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.printer = printer
            apply_to_group = bool(form.cleaned_data.get('apply_to_group') and printer.group)
            ticket.applies_to_group = apply_to_group
            ticket.group = printer.group if apply_to_group else None

            # Merge conditional fields into details for now
            extra = []
            if ticket.type == RequestTicket.SUPPLY:
                extra.append(f"Supply type: {form.cleaned_data['supply_type']}")
                extra.append(f"Quantity: {form.cleaned_data['supply_quantity']}")
            elif ticket.type == RequestTicket.ISSUE:
                extra.append(f"Issue category: {form.cleaned_data['issue_category']}")

            if ticket.applies_to_group and ticket.group:
                group_name = ticket.group.name or ticket.group.building or 'group'
                extra.append(f"Scope: Applies to entire group ({group_name})")

            if extra:
                ticket.details = (ticket.details or "")
                if ticket.details:
                    ticket.details += "\n\n"
                ticket.details += "\n".join(extra)

            ticket.save()

            # Dev email - prints to the terminal with console backend
            subject = f"[{ticket.type}] {printer.campus_label} ({printer.asset_tag})"
            scope_line = "Group" if ticket.applies_to_group else "Single printer"
            body_lines = [
                f"Printer: {printer.campus_label} | {printer.asset_tag}",
                f"Location: {printer.building} / {printer.location_in_building}",
                f"Make/Model: {printer.make} {printer.model}",
                f"IP/MAC: {printer.ip_address} / {printer.mac_address}",
                "",
                f"Scope: {scope_line}",
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

            body = "\n".join(body_lines)
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, settings.EMAIL_TO or ["sklarz@berea.edu"])

            return redirect(reverse('ticket_thanks'))
    else:
        form = RequestTicketForm(printer=printer)

    selected_type = form['type'].value() or RequestTicket.SUPPLY
    selected_issue = form['issue_category'].value() or ''

    group_printers = None
    if printer.group:
        group_printers = list(printer.group.printers.order_by('campus_label'))

    return render(request, 'tickets/portal.html', {
        'printer': printer,
        'form': form,
        'group_printers': group_printers,
        'selected_type': selected_type,
        'selected_issue': selected_issue,
    })


def ticket_thanks(request):
    return render(request, 'tickets/thanks.html')
