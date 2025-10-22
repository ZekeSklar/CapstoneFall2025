from django import forms
from django.forms import formset_factory

from .models import RequestTicket


class SupplyRequestForm(forms.ModelForm):
    apply_to_group = forms.BooleanField(required=False, label="Apply request to entire group")

    def __init__(self, *args, printer=None, user=None, manager_override=False, **kwargs):
        self.force_apply_to_group = kwargs.pop("force_apply_to_group", False)
        self.printer = printer
        self.user = user
        self.manager_override = manager_override
        super().__init__(*args, **kwargs)

        self.has_group = bool(printer and printer.group)
        if self.has_group:
            group_name = printer.group.name or printer.group.building or "this group"
            self.fields['apply_to_group'].label = f"Apply request to all printers in {group_name}"
        else:
            self.fields['apply_to_group'].initial = False

        if self.force_apply_to_group:
            self.fields['apply_to_group'].initial = True
            self.fields['apply_to_group'].widget = forms.HiddenInput()
            self.fields['apply_to_group'].disabled = True
        else:
            # Manager and staff flows no longer expose the toggle
            self.fields['apply_to_group'].initial = False
            self.fields['apply_to_group'].widget = forms.HiddenInput()
            self.fields['apply_to_group'].disabled = True

        if self.user:
            display_name = (self.user.get_full_name() or '').strip() or self.user.get_username()
            if display_name and not self.fields['requester_name'].initial:
                self.fields['requester_name'].initial = display_name
            if self.user.email and not self.fields['requester_email'].initial:
                self.fields['requester_email'].initial = self.user.email

        if self.manager_override:
            self.fields['requester_name'].widget = forms.HiddenInput()
            self.fields['requester_email'].widget = forms.HiddenInput()

        self.fields['requester_email'].required = True

    class Meta:
        model = RequestTicket
        fields = ['requester_name', 'requester_email', 'details']

    def clean(self):
        cleaned = super().clean()
        if self.force_apply_to_group:
            cleaned['apply_to_group'] = True
        else:
            cleaned['apply_to_group'] = False
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


class SupplyItemForm(forms.Form):
    supply_type = forms.CharField(max_length=120, label="Supply type")
    supply_quantity = forms.IntegerField(min_value=1, label="Quantity", initial=1)


SupplyItemFormSet = formset_factory(SupplyItemForm, extra=0, min_num=1, validate_min=True, max_num=10)


class IssueReportForm(forms.ModelForm):
    def __init__(self, *args, user=None, manager_override=False, **kwargs):
        self.user = user
        self.manager_override = manager_override
        super().__init__(*args, **kwargs)
        if self.user:
            display_name = (self.user.get_full_name() or '').strip() or self.user.get_username()
            if display_name and not self.fields['requester_name'].initial:
                self.fields['requester_name'].initial = display_name
            if self.user.email and not self.fields['requester_email'].initial:
                self.fields['requester_email'].initial = self.user.email
        if self.manager_override:
            self.fields['requester_name'].widget = forms.HiddenInput()
            self.fields['requester_email'].widget = forms.HiddenInput()

    issue_category = forms.ChoiceField(
        required=True,
        choices=[
            ('PAPER_JAM', 'Paper jam'),
            ('PRINT_QUALITY', 'Print quality'),
            ('ERROR_CODE', 'Error code on panel'),
            ('OTHER', 'Other'),
        ],
        label="Issue category",
    )

    class Meta:
        model = RequestTicket
        fields = ['requester_name', 'requester_email', 'details']
