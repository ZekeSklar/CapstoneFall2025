from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.mail import send_mail
from .models import Printer, RequestTicket
from .forms import RequestTicketForm
from django.conf import settings

def printer_portal(request, qr_token):
    printer = get_object_or_404(Printer, qr_token=qr_token)

    if request.method == 'POST':
        form = RequestTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.printer = printer

            # Merge conditional fields into details for now
            extra = []
            if ticket.type == RequestTicket.SUPPLY:
                extra.append(f"Supply type: {form.cleaned_data['supply_type']}")
                extra.append(f"Quantity: {form.cleaned_data['supply_quantity']}")
            elif ticket.type == RequestTicket.ISSUE:
                extra.append(f"Issue category: {form.cleaned_data['issue_category']}")

            if extra:
                ticket.details = (ticket.details or "")
                if ticket.details:
                    ticket.details += "\n\n"
                ticket.details += "\n".join(extra)

            ticket.save()

            # Dev email → prints to the terminal with console backend
            subject = f"[{ticket.type}] {printer.campus_label} ({printer.asset_tag})"
            body = (
                f"Printer: {printer.campus_label} | {printer.asset_tag}\n"
                f"Location: {printer.building} / {printer.location_in_building}\n"
                f"Make/Model: {printer.make} {printer.model}\n"
                f"IP/MAC: {printer.ip_address} / {printer.mac_address}\n\n"
                f"Requester: {ticket.requester_name} <{ticket.requester_email}>\n"
                f"Details:\n{ticket.details}\n"
            )
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, settings.EMAIL_TO or ["sklarz@berea.edu"])

            return redirect(reverse('ticket_thanks'))
    else:
        form = RequestTicketForm()

    return render(request, 'tickets/portal.html', {'printer': printer, 'form': form})

def ticket_thanks(request):
    return render(request, 'tickets/thanks.html')

