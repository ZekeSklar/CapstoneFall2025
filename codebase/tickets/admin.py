from django.contrib import admin
from .models import Printer, RequestTicket

@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = (
        'campus_label', 'asset_tag', 'make', 'model',
        'building', 'location_in_building', 'ip_address', 'mac_address', 'is_active'
    )
    search_fields = (
        'campus_label', 'asset_tag', 'serial_number',
        'make', 'model', 'building', 'location_in_building',
        'ip_address', 'mac_address'
    )
    list_filter = ('is_active', 'make', 'model', 'building')
    autocomplete_fields = ()
    ordering = ('campus_label',)

@admin.register(RequestTicket)
class RequestTicketAdmin(admin.ModelAdmin):
    list_display = ('printer', 'type', 'status', 'created_at')
    list_filter = ('type', 'status', 'created_at', 'printer__building', 'printer__make')
    search_fields = (
        'printer__campus_label',
        'printer__asset_tag',
        'printer__serial_number',
        'printer__building',
        'printer__location_in_building',
        'printer__ip_address',
        'printer__mac_address',
        'requester_email'
    )
    autocomplete_fields = ('printer',)

