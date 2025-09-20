
from django.db import models
from django.conf import settings

class PrinterComment(models.Model):
    printer = models.ForeignKey('Printer', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.printer} at {self.created_at:%Y-%m-%d %H:%M}"

class InventoryItem(models.Model):
    name = models.CharField(max_length=100, help_text="User-friendly name, e.g., 'Toshiba color black toner'")
    model_number = models.CharField(max_length=100, blank=True, help_text="Exact model/part number, e.g., 'T-FC415K'")
    category = models.CharField(
        max_length=50,
        choices=[
            ('toner', 'Toner'),
            ('staple', 'Staple'),
            ('waste_basket', 'Waste Basket'),
            # Add more categories as needed
        ]
    )
    quantity_on_hand = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=1)
    compatible_printers = models.ManyToManyField('Printer', blank=True)

    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_threshold

    def __str__(self):
        return f"{self.name} ({self.category}) [{self.model_number}]"
from django.core.validators import RegexValidator
from django.utils.crypto import get_random_string

def default_qr_token():
    return get_random_string(22)

# Accepts 00:11:22:33:44:55 or 00-11-22-33-44-55 (upper/lower)
mac_validator = RegexValidator(
    regex=r'^([0-9A-Fa-f]{2}([-:])){5}([0-9A-Fa-f]{2})$',
    message="Enter a valid MAC address (e.g., 00:11:22:33:44:55)."
)

class Printer(models.Model):
    # Core identifiers
    campus_label = models.CharField(
        max_length=80,
        help_text="College-specific unique label used for internal lookup."
    )
    asset_tag = models.CharField(
        max_length=50,
        help_text="Physical asset/inventory tag."
    )

    # Hardware identity
    serial_number = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="Device serial number (unique when known)."
    )
    make = models.CharField(max_length=80, help_text="Manufacturer, e.g., Toshiba, Lexmark")
    model = models.CharField(max_length=120, help_text="Model, e.g., e-STUDIO 3515AC, M3150")

    # Location (split)
    building = models.CharField(max_length=120, help_text="Building name, e.g., Hutchins Library")
    location_in_building = models.CharField(
        max_length=120,
        help_text="Room/area, e.g., 1st Floor Near Circulation"
    )

    # Network
    ip_address = models.GenericIPAddressField(
        protocol='both', unpack_ipv4=True, null=True, blank=True,
        help_text="IPv4 or IPv6; optional if DHCP/unassigned."
    )
    mac_address = models.CharField(
        max_length=17,  # 'XX:XX:XX:XX:XX:XX'
        validators=[mac_validator],
        help_text="Physical NIC MAC, unique per device (e.g., 00:11:22:33:44:55)."
    )

    # QR identity & status
    qr_token = models.CharField(max_length=64, unique=True, default=default_qr_token)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["asset_tag"]),
            models.Index(fields=["building"]),
            models.Index(fields=["location_in_building"]),
            models.Index(fields=["make"]),
            models.Index(fields=["model"]),
        ]

    def __str__(self):
        return f"{self.campus_label} | {self.asset_tag} — {self.building} / {self.location_in_building}"

    def clean(self):
        from django.core.exceptions import ValidationError
        generic_values = {
            'mac_address': ['UNKNOWN-MACADDRESS', '00:00:00:00:00:00'],
            'ip_address': '0.0.0.0',
            'serial_number': 'UNKNOWN-SERIAL',
            'asset_tag': 'UNKNOWN-ASSET',
            'campus_label': 'UNKNOWN-LABEL',
        }
        # Only enforce uniqueness for non-generic values
        for field, unknown in generic_values.items():
            value = getattr(self, field, None)
            if field == 'mac_address':
                if value and value not in unknown:
                    lookup = {field: value}
                    qs = Printer.objects.filter(**lookup)
                    if self.pk:
                        qs = qs.exclude(pk=self.pk)
                    if qs.exists():
                        raise ValidationError({field: f"{field.replace('_', ' ').title()} must be unique unless using the generic value."})
            else:
                if value and value != unknown:
                    lookup = {field: value}
                    qs = Printer.objects.filter(**lookup)
                    if self.pk:
                        qs = qs.exclude(pk=self.pk)
                    if qs.exists():
                        raise ValidationError({field: f"{field.replace('_', ' ').title()} must be unique unless using the generic value."})

    def save(self, *args, **kwargs):
        # Normalize MAC to uppercase with colons
        if self.mac_address:
            mac = self.mac_address.replace('-', ':').upper()
            self.mac_address = mac
        self.full_clean()
        super().save(*args, **kwargs)

class RequestTicket(models.Model):
    SUPPLY = 'SUPPLY'
    ISSUE = 'ISSUE'
    TYPE_CHOICES = [(SUPPLY, 'Supply'), (ISSUE, 'Issue')]

    NEW = 'NEW'
    IN_PROGRESS = 'IN_PROGRESS'
    FULFILLED = 'FULFILLED'
    CLOSED = 'CLOSED'
    STATUS_CHOICES = [
        (NEW, 'New'),
        (IN_PROGRESS, 'In Progress'),
        (FULFILLED, 'Fulfilled'),
        (CLOSED, 'Closed'),
    ]

    printer = models.ForeignKey(Printer, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)

    requester_name = models.CharField(max_length=120, blank=True)
    requester_email = models.EmailField(blank=True)
    details = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.type}] {self.printer.campus_label} — {self.status}"
