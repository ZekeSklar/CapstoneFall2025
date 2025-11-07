# URL configuration for the project.
# Routes admin, auth, manager endpoints, and QR-driven printer flows.
from django.contrib import admin
from django.urls import include, path
from tickets.views import (
    manager_dashboard,
    manager_group_order,
    manager_group_quick_paper,
    manager_printer_issue,
    manager_printer_order,
    manager_status_feed,
    manager_printer_status,
    inventory_scanner,
    inventory_scan,
    printer_issue,
    printer_order,
    printer_paper_order,
    printer_portal,
    ticket_thanks,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('manager/', manager_dashboard, name='manager_dashboard'),
    path('manager/groups/<int:group_id>/order/', manager_group_order, name='manager_group_order'),
    path('manager/groups/<int:group_id>/quick-paper/', manager_group_quick_paper, name='manager_group_quick_paper'),
    path('manager/status/', manager_status_feed, name='manager_status_feed'),
    path('manager/printers/<int:printer_id>/order/', manager_printer_order, name='manager_printer_order'),
    path('manager/printers/<int:printer_id>/status/', manager_printer_status, name='manager_printer_status'),
    path('manager/printers/<int:printer_id>/issue/', manager_printer_issue, name='manager_printer_issue'),
    path('p/<str:qr_token>/', printer_portal, name='printer_portal'),
    path('p/<str:qr_token>/order/', printer_order, name='printer_order'),
    path('p/<str:qr_token>/paper/', printer_paper_order, name='printer_paper_order'),
    path('p/<str:qr_token>/issue/', printer_issue, name='printer_issue'),
    path('thanks/', ticket_thanks, name='ticket_thanks'),
    # Inventory scanner
    path('scanner/', inventory_scanner, name='inventory_scanner'),
    path('scanner/scan/', inventory_scan, name='inventory_scan'),
]
