from django import forms
from .models import RequestTicket


class RequestTicketForm(forms.ModelForm):
    # Conditional fields shown/required based on type
    supply_type = forms.CharField(required=False, max_length=120, label="Supply type (e.g., Black toner)")
    supply_quantity = forms.IntegerField(required=False, min_value=1, label="Quantity")
    issue_category = forms.ChoiceField(
        required=False,
        choices=[
            ('PAPER_JAM', 'Paper jam'),
            ('PRINT_QUALITY', 'Print quality'),
            ('ERROR_CODE', 'Error code on panel'),
            ('OTHER', 'Other')
        ],
        label="Issue category"
    )
    apply_to_group = forms.BooleanField(required=False, label="Apply request to entire group")

    def __init__(self, *args, printer=None, **kwargs):
        self.printer = printer
        super().__init__(*args, **kwargs)
        self.has_group = bool(printer and printer.group)
        if self.has_group:
            group_name = printer.group.name or printer.group.building or "this group"
            self.fields['apply_to_group'].label = f"Apply request to all printers in {group_name}"
        else:
            self.fields['apply_to_group'].initial = False

    class Meta:
        model = RequestTicket
        fields = ['type', 'requester_name', 'requester_email', 'details']  # printer set in the view

    def clean(self):
        cleaned = super().clean()
        t = cleaned.get('type')
        if t == RequestTicket.SUPPLY:
            if not cleaned.get('supply_type'):
                self.add_error('supply_type', "Supply type is required.")
            if not cleaned.get('supply_quantity'):
                self.add_error('supply_quantity', "Quantity is required.")
        elif t == RequestTicket.ISSUE:
            if not cleaned.get('issue_category'):
                self.add_error('issue_category', "Select an issue category.")

        apply_to_group = cleaned.get('apply_to_group')
        if apply_to_group:
            if not self.has_group:
                self.add_error('apply_to_group', "This printer is not assigned to a group yet.")
            else:
                email = cleaned.get('requester_email')
                if not email:
                    self.add_error('requester_email', "Provide an email so we can confirm group-wide requests.")
                elif not self.printer.group.allows_email(email):
                    self.add_error('apply_to_group', "You are not authorized to request for the entire group.")
        return cleaned
