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
        return cleaned