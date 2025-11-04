from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils.crypto import get_random_string


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
    # Optional barcode/UPC/EAN text for scanning workflows
    barcode = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Optional UPC/EAN/Code128 text used by the scanner page.",
    )
    # Optional physical shelf location
    # Rows are letters (e.g., A, B, ... or AA), columns are numbers (e.g., 1, 2, 10)
    shelf_row = models.CharField(
        max_length=1,
        blank=True,
        null=True,
        db_index=True,
        validators=[RegexValidator(r'^[A-Za-z]$', message='Shelf row must be a single letter (A-Z).')],
        help_text="Shelf row letter (A-Z)."
    )
    shelf_column = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Shelf column number (e.g., 1, 2, 10)."
    )

    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_threshold

    def __str__(self):
        return f"{self.name} ({self.category}) [{self.model_number}]"

    # --- Shelf helpers ---
    @property
    def shelf_code(self) -> str:
        """Returns a human-friendly shelf coordinate like 'A-3' or '' if unset."""
        if not self.shelf_row or self.shelf_column is None:
            return ""
        return f"{self.shelf_row}-{self.shelf_column}"

    def _row_number(self) -> int:
        """Convert row letters (A, B, ..., Z, AA, AB, ...) to a 1-based number.

        This matches spreadsheet-style base-26 encoding: A=1, Z=26, AA=27, AB=28, etc.
        Returns 0 if row is not set.
        """
        if not self.shelf_row:
            return 0
        total = 0
        for ch in self.shelf_row.strip().upper():
            if 'A' <= ch <= 'Z':
                total = total * 26 + (ord(ch) - ord('A') + 1)
            else:
                # Non-letter encountered; stop processing
                break
        return total

    @property
    def shelf_sort_key(self) -> tuple[int, int, str]:
        """Key for Python-level sorting: by row (letters), then column (number), then name.

        Useful for in-memory sorts where DB ordering is not enough.
        """
        row_num = self._row_number()
        col_num = self.shelf_column or 0
        return (row_num, col_num, (self.name or ""))

    def clean(self):
        # Normalize shelf_row to uppercase letters (if provided)
        super().clean()
        if self.shelf_row:
            self.shelf_row = ''.join(ch for ch in self.shelf_row.strip().upper() if ch.isalpha())[:1]


class PrinterGroup(models.Model):
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="managed_printer_groups",
        help_text="Users allowed to manage printers in this group."
    )
    name = models.CharField(max_length=120, unique=True)
    building = models.CharField(max_length=120, blank=True, help_text="Optional building name if different from group name.")
    description = models.TextField(blank=True)
    group_order_allowed_emails = models.TextField(
        blank=True,
        help_text=(
            "Comma or newline separated list of email addresses allowed to place group-wide orders. "
            "Leave blank to allow any requester."
        ),
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def allowed_email_set(self):
        raw = (self.group_order_allowed_emails or '').replace(';', ',')
        raw = raw.replace('\r', ',').replace('\n', ',')
        tokens = [chunk.strip().lower() for chunk in raw.split(',') if chunk.strip()]
        return set(tokens)

    def allows_email(self, email: str | None) -> bool:
        allowed = self.allowed_email_set
        if not allowed:
            return True
        if not email:
            return False
        return email.strip().lower() in allowed


# Accepts 00:11:22:33:44:55 or 00-11-22-33-44-55 (upper/lower)
mac_validator = RegexValidator(
    regex=r'^([0-9A-Fa-f]{2}([-:])){5}([0-9A-Fa-f]{2})$',
    message="Enter a valid MAC address (e.g., 00:11:22:33:44:55)."
)


def default_qr_token():
    return get_random_string(22)


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
        null=True,
        blank=True,
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
    group = models.ForeignKey(
        PrinterGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='printers',
        help_text="Logical grouping (e.g., building) for supply/issue management."
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
        return f"{self.campus_label} | {self.asset_tag} | {self.building} / {self.location_in_building}"

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
    group = models.ForeignKey(PrinterGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    applies_to_group = models.BooleanField(default=False)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)

    requester_name = models.CharField(max_length=120, blank=True)
    requester_email = models.EmailField(blank=True)
    details = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        scope = 'group' if self.applies_to_group else 'single'
        return f"[{self.type}] {self.printer.campus_label} ({scope}) | {self.status}"

class IssueSummaryState(models.Model):
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Issue summary state'
        verbose_name_plural = 'Issue summary state'

    def __str__(self):
        if self.last_sent_at:
            return f"Issue summary last sent at {self.last_sent_at:%Y-%m-%d %H:%M:%S}"
        return 'Issue summary has not been sent yet'

class IssueSummaryRecipient(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='issue_summary_recipient')
    subscribed = models.BooleanField(
        'Receive daily issue summary',
        default=True,
        help_text='Receive the daily printer issue summary email.',
    )

    class Meta:
        verbose_name = 'Issue summary recipient'
        verbose_name_plural = 'Issue summary recipients'

    def __str__(self):
        name = self.user.get_full_name() or self.user.get_username()
        return f"{name} ({self.user.email})" if self.user.email else name

class PrinterStatus(models.Model):
    printer = models.OneToOneField(Printer, on_delete=models.CASCADE, related_name='status')
    status_code = models.PositiveSmallIntegerField(default=0)
    status_label = models.CharField(max_length=50, blank=True)
    device_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    device_status_label = models.CharField(max_length=50, blank=True)
    error_state_raw = models.CharField(max_length=16, blank=True)
    error_flags = models.JSONField(default=list, blank=True)
    alerts = models.JSONField(default=list, blank=True)
    supplies = models.JSONField(default=list, blank=True)
    attention = models.BooleanField(default=False)
    snmp_ok = models.BooleanField(default=True)
    snmp_message = models.CharField(max_length=255, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Printer status'
        verbose_name_plural = 'Printer statuses'

    def as_dict(self) -> dict:
        return {
            'printer_id': self.printer_id,
            'status_code': self.status_code,
            'status_label': self.status_label or 'Unknown',
            'device_status_code': self.device_status_code,
            'device_status_label': self.device_status_label or '',
            'error_state_raw': self.error_state_raw or '',
            'error_flags': list(self.error_flags or []),
            'alerts': list(self.alerts or []),
            'supplies': list(self.supplies or []),
            'attention': bool(self.attention),
            'snmp_ok': bool(self.snmp_ok),
            'snmp_message': self.snmp_message or '',
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def badge_level(self) -> str:
        if not self.snmp_ok:
            return 'error'
        if self.attention:
            return 'warning'
        return 'normal'



