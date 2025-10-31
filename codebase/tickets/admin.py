from import_export import resources
from import_export.admin import ImportExportModelAdmin
from django.db import models
# Custom admin index view to inject low inventory notifications
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.safestring import mark_safe
from django.utils.html import format_html
import json
import csv
from .printer_status import POLL_INTERVAL_SECONDS, ensure_latest_status, build_status_payload
from .forms import InventoryItemAdminForm
from .models import (
    InventoryItem,
    IssueSummaryRecipient,
    Printer,
    PrinterComment,
    PrinterGroup,
    RequestTicket,
)
# Inline for PrinterComment
User = get_user_model()


_ADMIN_TRUTHY_VALUES = {'1', 'true', 'yes', 'y', 'on', 'force', 'now'}
class IssueSummaryRecipientInline(admin.StackedInline):
    model = IssueSummaryRecipient
    fields = ("subscribed",)
    extra = 0
    max_num = 1
    verbose_name = "Daily issue summary subscription"
    verbose_name_plural = "Daily issue summary subscription"

    def get_extra(self, request, obj=None, **kwargs):
        if obj and hasattr(obj, 'issue_summary_recipient'):
            return 0
        return 1

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        if obj and hasattr(obj, 'issue_summary_recipient'):
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


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
        from .models import Printer, PrinterStatus
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

        status_qs = PrinterStatus.objects.select_related('printer').filter(
            models.Q(attention=True) | models.Q(snmp_ok=False)
        ).order_by('printer__campus_label')
        alert_total = status_qs.count()
        printer_status_alerts = list(status_qs[:20])
        alert_overflow = max(alert_total - len(printer_status_alerts), 0)
        attention_total = PrinterStatus.objects.filter(attention=True).count()
        snmp_fault_total = PrinterStatus.objects.filter(snmp_ok=False).count()

        if extra_context is None:
            extra_context = {}
        extra_context['low_inventory_items'] = low_inventory_items
        extra_context['missing_data_summary'] = missing_summary
        extra_context['printer_status_alerts'] = printer_status_alerts
        extra_context['printer_status_alert_total'] = alert_total
        extra_context['printer_status_alert_overflow'] = alert_overflow
        extra_context['printer_status_summary'] = {
            'attention_total': attention_total,
            'snmp_fault_total': snmp_fault_total,
        }
        return super().index(request, extra_context=extra_context)

# Swap out the default admin site for the custom one
admin.site.__class__ = CustomAdminSite
# ---------- InventoryItem Admin ----------
@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    form = InventoryItemAdminForm
    list_display = (
        'name', 'category', 'quantity_on_hand', 'reorder_threshold', 'shelf_location',
    )
    list_filter = ('category', 'shelf_row')
    search_fields = ('name', 'model_number', 'shelf_row')
    ordering = ('shelf_row', 'shelf_column', 'name')

    def shelf_location(self, obj):
        return obj.shelf_code or '-'
    shelf_location.short_description = 'Shelf'

    class Media:
        js = ('tickets/js/inventory_item_admin.js',)


@admin.register(PrinterGroup)
class PrinterGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'member_count')
    search_fields = ('name', 'building')
    filter_horizontal = ('managers',)

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
    # Use default change_form layout; we inject the status panel
    # as a readonly fieldset to keep the sidebar layout intact.
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
    # Expose custom HTML panel as a readonly field
    readonly_fields = ("_live_device_status",)

    def get_fieldsets(self, request, obj=None):
        # Ensure a list so we can append regardless of Django's return type
        fieldsets = list(super().get_fieldsets(request, obj) or [])
        # Append our status panel after main field groups, before inlines
        extra = (
            "Live Device Status",
            {
                "fields": ("_live_device_status",),
                "classes": ("wide",),
            },
        )
        fieldsets.append(extra)
        return fieldsets

    def _live_device_status(self, obj):
        if not obj:
            return "Save the printer to view live status."
        # Build initial payload from cached status; JS will refresh async
        from .models import PrinterStatus
        status = PrinterStatus.objects.filter(printer=obj).first()
        payload = build_status_payload(obj, status)
        endpoint = reverse('admin:tickets_printer_status', args=[obj.pk])

        # Safely JSON-encode for inline script tag
        data_json = json.dumps(payload)
        # Render the panel and inline JS (scoped by unique IDs)
        html = f'''
<div style="padding:1rem;border:1px solid #ddd;border-radius:8px;background:#f9fafb;">
  <p id="admin-status-updated" style="margin:0 0 .75rem;color:#555;">Preparing live status...</p>
  <div id="admin-status-render"></div>
  <p style="margin-top:.75rem;"><a href="#" id="admin-status-refresh" class="button">Refresh</a></p>
</div>
<script id="printer-status-data" type="application/json">{data_json}</script>
<script>(function(){{
  const dataEl = document.getElementById('printer-status-data');
  const renderTarget = document.getElementById('admin-status-render');
  const updated = document.getElementById('admin-status-updated');
  const refreshBtn = document.getElementById('admin-status-refresh');
  const endpoint = {json.dumps(endpoint)};

  function fmt(ts){{
    if(!ts) return 'Last checked: just now';
    try{{ return 'Last checked: ' + new Date(ts).toLocaleString(); }}catch(e){{return 'Last checked: unknown';}}
  }}

  function render(payload){{
    if(!payload || !payload.status){{ renderTarget.innerHTML = '<div class="muted">No SNMP data returned.</div>'; return; }}
    const s = payload.status;
    updated.textContent = fmt(s.fetched_at || s.updated_at);
    const lines = [];
    lines.push('<div style="display:flex;gap:1rem;flex-wrap:wrap">');
    lines.push('<div style="padding:.35rem .75rem;border-radius:999px;background:#fde2e2;color:#9b2c2c;">' + (s.snmp_ok? (s.status_label || 'Unknown') : 'Unavailable') + '</div>');
    lines.push('<div style="padding:.35rem .75rem;border-radius:999px;background:#f0f4ff;color:#1e3a8a;">' + (s.device_status_label || 'Device status unavailable') + '</div>');
    lines.push('</div>');
    if(s.snmp_message){{ lines.push('<p style="color:#9b2c2c;">' + s.snmp_message + '</p>'); }}
    lines.push('<h4 style="margin:.75rem 0 .25rem">Active Alerts</h4>');
    if(s.alerts && s.alerts.length){{
      lines.push('<ul>');
      s.alerts.forEach(a=> lines.push('<li>' + (a.severity||'Alert') + ' - ' + (a.description||'Details unavailable') + '</li>'));
      lines.push('</ul>');
    }} else {{
      lines.push('<div class="muted">No active alerts reported.</div>');
    }}
    lines.push('<h4 style="margin:.75rem 0 .25rem">Error Flags</h4>');
    if(s.error_flags && s.error_flags.length){{
      lines.push('<ul>');
      s.error_flags.forEach(f=> lines.push('<li>' + (f.label||f.code||'Unknown') + '</li>'));
      lines.push('</ul>');
    }} else {{
      lines.push('<div class="muted">No error flags are active.</div>');
    }}
    lines.push('<h4 style="margin:.75rem 0 .25rem">Supplies</h4>');
    if(s.supplies && s.supplies.length){{
      lines.push('<ul>');
      s.supplies.forEach(sp=> lines.push('<li>' + (sp.description||'Supply') + (sp.percent!=null? (' - ' + Math.round(sp.percent) + '%') : (sp.level!=null? (' - Level ' + sp.level) : '')) + '</li>'));
      lines.push('</ul>');
    }} else {{
      lines.push('<div class="muted">No consumable readings were returned.</div>');
    }}
    renderTarget.innerHTML = lines.join('');
  }}

  if(dataEl){{
    try{{ const payload = JSON.parse(dataEl.textContent); render(payload); }}
    catch(e){{ /* ignore */ }}
  }}

  async function refresh(force){{
    if(!endpoint) return;
    let url = endpoint;
    if (force) {{ url += (url.indexOf('?')>-1? '&' : '?') + 'force=1'; }}
    url += (url.indexOf('?')>-1? '&' : '?') + 't=' + Date.now();
    try{{
      const r = await fetch(url, {{ headers:{{'Accept':'application/json'}} }});
      if(!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      if(Array.isArray(data.printers) && data.printers.length){{ render(data.printers[0]); }}
      else if(data.status){{ render(data); }}
      updated.textContent = 'Last sync: ' + new Date().toLocaleString();
    }}catch(err){{ updated.textContent = 'Unable to refresh device status: ' + err.message; }}
  }}

  if(refreshBtn){{ refreshBtn.addEventListener('click', function(ev){{ ev.preventDefault(); refresh(true); }}); }}
  try {{ setTimeout(function(){{ refresh(true); }}, 50); }} catch(e) {{ /* ignore */ }}
}})();</script>
        '''
        return mark_safe(html)
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<path:object_id>/status/', self.admin_site.admin_view(self.printer_status_view), name='tickets_printer_status'),
        ]
        return custom + urls

    def printer_status_view(self, request, object_id):
        printer = self.get_object(request, object_id)
        if printer is None:
            from django.http import Http404
            raise Http404('Printer not found')
        force_flag = request.GET.get('force') or request.GET.get('refresh')
        force = bool(force_flag and force_flag.strip().lower() in _ADMIN_TRUTHY_VALUES)
        status = ensure_latest_status(printer, force=force)
        payload = build_status_payload(printer, status)
        resp = JsonResponse(payload)
        resp['Cache-Control'] = 'no-store'
        return resp

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        status_payload = None
        status_endpoint = None
        if object_id:
            printer = self.get_object(request, object_id)
            if printer is not None:
                # Do not block page load with live SNMP polling.
                # Use cached status (if any) and let JS refresh asynchronously.
                from .models import PrinterStatus
                status = (
                    PrinterStatus.objects.filter(printer=printer).first()
                )
                status_payload = build_status_payload(printer, status)
                status_endpoint = reverse('admin:tickets_printer_status', args=[object_id])
        extra_context.update({
            'printer_status_payload': status_payload,
            'poll_interval_seconds': POLL_INTERVAL_SECONDS,
            'printer_status_endpoint': status_endpoint,
        })
        return super().changeform_view(request, object_id, form_url, extra_context)

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



class IssueSummaryUserAdmin(DjangoUserAdmin):
    inlines = [IssueSummaryRecipientInline]

    def get_inline_instances(self, request, obj=None):
        if not request.user.is_superuser or obj is None:
            return []
        return super().get_inline_instances(request, obj)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:  # pragma: no cover
    pass

admin.site.register(User, IssueSummaryUserAdmin)

# ---- Custom Admin Branding ----
admin.site.site_header = "Berea College Printing Services"
admin.site.site_title = "Berea College Admin Portal"
admin.site.index_title = "Welcome to Berea College Printing Services Admin"



