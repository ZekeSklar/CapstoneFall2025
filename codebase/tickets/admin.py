from import_export import resources
from import_export.admin import ImportExportModelAdmin
from django.db import models
# Custom admin index view to inject low inventory notifications
from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.http import HttpResponse
import csv
from .models import Printer, RequestTicket, InventoryItem, PrinterComment, PrinterGroup
# Inline for PrinterComment
class PrinterCommentInline(admin.TabularInline):
    model = PrinterComment
    extra = 1
    readonly_fields = ('created_at',)
    fields = ('comment', 'created_at')  # Hide user field

    def save_new_instance(self, form, commit=True):
        obj = form.save(commit=False)
        obj.user = self.request.user
        if commit:
            obj.save()
        return obj

    def get_formset(self, request, obj=None, **kwargs):
        self.request = request
        return super().get_formset(request, obj, **kwargs)

    class Media:
        js = ('tickets/js/one_click_delete.js',)


class CustomAdminSite(admin.AdminSite):
    site_url = None  # Remove 'View site' button
    def index(self, request, extra_context=None):
        low_inventory_items = InventoryItem.objects.filter(quantity_on_hand__lte=models.F('reorder_threshold'))
        # Missing data summary for printers
        from .models import Printer
        generic_values = {
            'mac_address': 'UNKNOWN-MACADDRESS',
            'ip_address': '0.0.0.0',
            'serial_number': 'UNKNOWN-SERIAL',
            'asset_tag': 'UNKNOWN-ASSET',
            'campus_label': 'UNKNOWN-LABEL',
            'make': 'UNKNOWN-MAKE',
            'model': 'UNKNOWN-MODEL',
            'building': 'UNKNOWN-BUILDING',
            'location_in_building': 'UNKNOWN-LOCATION',
        }
        missing_summary = {}
        for field, unknown in generic_values.items():
            count = Printer.objects.filter(**{field: unknown}).count()
            if count > 0:
                missing_summary[field] = count
        if extra_context is None:
            extra_context = {}
        extra_context['low_inventory_items'] = low_inventory_items
        extra_context['missing_data_summary'] = missing_summary
        return super().index(request, extra_context=extra_context)

# Swap out the default admin site for the custom one
admin.site.__class__ = CustomAdminSite
# ---------- InventoryItem Admin ----------
@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity_on_hand', 'reorder_threshold')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(PrinterGroup)
class PrinterGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'member_count')
    search_fields = ('name', 'building')

    def member_count(self, obj):
        return obj.printers.count()


# ---- Shared helpers ----
def _csv_http_response(prefix: str) -> HttpResponse:
    """Small helper to return a CSV HttpResponse with a nice filename."""
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{prefix}.csv"'
    return resp


# ---- Admin-wide CSS (via mixin) ----
# Put your stylesheet at: tickets/static/tickets/admin.css
class AdminCSSMixin:
    class Media:
        css = {"all": ("tickets/admin.css",)}


# ---------- Printer Admin + Export ----------

class PrinterResource(resources.ModelResource):
    class Meta:
        model = Printer

@admin.register(Printer)
class PrinterAdmin(AdminCSSMixin, ImportExportModelAdmin):
    resource_class = PrinterResource
    inlines = [PrinterCommentInline]
    list_display = (
        "campus_label", "asset_tag", "qr_token",
        "make", "model",
        "building", "location_in_building", "group",
        "ip_address", "mac_address",
        "is_active",
    )
    search_fields = (
        "campus_label", "asset_tag", "serial_number",
        "make", "model",
        "building", "location_in_building", "group__name",
        "ip_address", "mac_address",
    )
    list_filter = ("is_active", "make", "model", "building", "group")
    ordering = ("campus_label",)
    list_per_page = 50
    actions = ["export_printers_csv"]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, PrinterComment) and not obj.user_id:
                obj.user = request.user
            obj.save()
        formset.save_m2m()

    @admin.action(description="Export selected printers to CSV")
    def export_printers_csv(self, request, queryset):
        resp = _csv_http_response("printers")
        writer = csv.writer(resp)
        writer.writerow([
            "campus_label", "asset_tag", "serial_number",
            "make", "model",
            "building", "location_in_building",
            "ip_address", "mac_address",
            "qr_token", "is_active",
        ])
        for p in queryset:
            writer.writerow([
                p.campus_label, p.asset_tag, p.serial_number or "",
                p.make, p.model,
                p.building, p.location_in_building,
                p.ip_address or "", p.mac_address,
                p.qr_token, "true" if p.is_active else "false",
            ])
        return resp


# ---------- RequestTicket Admin + Export + Quick Status Actions ----------
@admin.register(RequestTicket)
class RequestTicketAdmin(AdminCSSMixin, admin.ModelAdmin):
    list_display = ("printer", "type", "status", "applies_to_group", "created_at")
    list_filter = ("type", "status", "created_at", "applies_to_group", "group", "printer__building", "printer__make")
    search_fields = (
        "printer__campus_label",
        "printer__asset_tag",
        "printer__serial_number",
        "printer__building",
        "printer__location_in_building",
        "printer__ip_address",
        "printer__mac_address",
        "group__name",
        "requester_email",
    )
    autocomplete_fields = ("printer",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 50
    list_select_related = ("printer", "group")
    actions = ["mark_in_progress", "mark_fulfilled", "mark_closed", "export_tickets_csv"]

    @admin.action(description="Mark selected as In Progress")
    def mark_in_progress(self, request, queryset):
        queryset.update(status=RequestTicket.IN_PROGRESS)

    @admin.action(description="Mark selected as Fulfilled")
    def mark_fulfilled(self, request, queryset):
        queryset.update(status=RequestTicket.FULFILLED)

    @admin.action(description="Mark selected as Closed")
    def mark_closed(self, request, queryset):
        queryset.update(status=RequestTicket.CLOSED)

    @admin.action(description="Export selected tickets to CSV")
    def export_tickets_csv(self, request, queryset):
        resp = _csv_http_response("tickets")
        writer = csv.writer(resp)
        writer.writerow([
            "created_at", "type", "status",
            # Printer fields (flattened for reporting)
            "printer_campus_label", "printer_asset_tag",
            "printer_make", "printer_model",
            "printer_building", "printer_location",
            "printer_ip", "printer_mac",
            "scope", "group_name",
            # Requester + details
            "requester_name", "requester_email", "details",
        ])
        for t in queryset.select_related("printer", "group"):
            p = t.printer
            scope = "Group" if t.applies_to_group else "Single"
            group_name = t.group.name if t.group else ""
            writer.writerow([
                t.created_at.isoformat(timespec="seconds"),
                t.type, t.status,
                p.campus_label, p.asset_tag,
                p.make, p.model,
                p.building, p.location_in_building,
                p.ip_address or "", p.mac_address,
                scope, group_name,
                t.requester_name or "", t.requester_email or "",
                (t.details or "").replace("\r\n", " ").replace("\n", " "),
            ])
        return resp

# ---- Custom Admin Branding ----
admin.site.site_header = "Berea College Printing Services"
admin.site.site_title = "Berea College Admin Portal"
admin.site.index_title = "Welcome to Berea College Printing Services Admin"


