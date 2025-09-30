"""
URL configuration for printer_system project.

The urlpatterns list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from tickets.views import (
    manager_dashboard,
    manager_group_order,
    manager_group_quick_paper,
    manager_printer_issue,
    manager_printer_order,
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
    path('manager/printers/<int:printer_id>/order/', manager_printer_order, name='manager_printer_order'),
    path('manager/printers/<int:printer_id>/issue/', manager_printer_issue, name='manager_printer_issue'),
    path('p/<str:qr_token>/', printer_portal, name='printer_portal'),
    path('p/<str:qr_token>/order/', printer_order, name='printer_order'),
    path('p/<str:qr_token>/paper/', printer_paper_order, name='printer_paper_order'),
    path('p/<str:qr_token>/issue/', printer_issue, name='printer_issue'),
    path('thanks/', ticket_thanks, name='ticket_thanks'),
]
