from django import forms
from django.forms import formset_factory, BaseFormSet

from .models import RequestTicket, InventoryItem
from django.core.validators import RegexValidator


class SupplyRequestForm(forms.ModelForm):
    apply_to_group = forms.BooleanField(required=False, label="Apply request to entire group")
    drop_off_location = forms.CharField(
        required=True,
        max_length=120,
        label="Drop-off location",
        help_text="Where should we deliver these supplies?",
        widget=forms.TextInput(attrs={
            'placeholder': 'Building / room or desk (e.g., Hutchins 101 front desk)',
            'autocomplete': 'off',
        }),
    )

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


OTHER_SENTINEL = "__OTHER__"


class InventorySupplyItemForm(forms.Form):
    def __init__(self, *args, allowed_items_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = allowed_items_qs if allowed_items_qs is not None else InventoryItem.objects.none()
        # Build choices from queryset plus an explicit "Other" option
        choices = [("", "---------")] + [
            (str(obj.id), f"{obj.name}{f' [{obj.model_number}]' if obj.model_number else ''}")
            for obj in qs
        ]
        choices.append((OTHER_SENTINEL, "Other / Not listed"))
        self.fields['supply_item'].choices = choices

    supply_item = forms.ChoiceField(
        choices=[],
        label="Supply item",
        required=True,
        help_text="Only items compatible with the selected printer(s).",
    )
    supply_other = forms.CharField(
        max_length=200,
        required=False,
        label="Describe the item",
        help_text="If choosing Other, briefly describe the needed supply.",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., Staple cartridge for MX611',
            'autocomplete': 'off',
        }),
    )
    supply_quantity = forms.IntegerField(min_value=1, label="Quantity", initial=1)

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get('supply_item')
        other_text = (cleaned.get('supply_other') or '').strip()
        if selected == OTHER_SENTINEL and not other_text:
            self.add_error('supply_other', 'Please describe the item for Other / Not listed.')
        return cleaned


class BaseInventorySupplyItemFormSet(BaseFormSet):
    def __init__(self, *args, allowed_items_qs=None, **kwargs):
        self.allowed_items_qs = allowed_items_qs if allowed_items_qs is not None else InventoryItem.objects.none()
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['allowed_items_qs'] = self.allowed_items_qs
        return super()._construct_form(i, **kwargs)


InventorySupplyItemFormSet = formset_factory(
    InventorySupplyItemForm,
    formset=BaseInventorySupplyItemFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=10,
)


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


class InventoryItemAdminForm(forms.ModelForm):
    shelf_row = forms.CharField(
        required=False,
        max_length=1,
        label="Shelf row",
        validators=[RegexValidator(r'^[A-Za-z]$', 'Shelf row must be a single letter (A-Z).')],
        widget=forms.TextInput(
            attrs={
                'maxlength': '1',
                'pattern': '[A-Za-z]',
                'title': 'Single letter A–Z',
                'style': 'text-transform:uppercase;width:4.5em',
                'autocomplete': 'off',
                'inputmode': 'text',
            }
        ),
    )

    class Meta:
        model = InventoryItem
        fields = '__all__'

    def clean_shelf_row(self):
        v = self.cleaned_data.get('shelf_row') or ''
        v = ''.join(ch for ch in v.strip().upper() if ch.isalpha())[:1]
        return v or None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Normalize any mojibake titles for the shelf_row widget
        try:
            self.fields['shelf_row'].widget.attrs['title'] = 'Single letter A-Z'
        except Exception:
            pass
