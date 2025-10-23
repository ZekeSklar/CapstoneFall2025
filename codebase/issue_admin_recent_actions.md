Summary
- Visiting /admin/ raised TemplateDoesNotExist for admin/includes/recent_actions.html.
- Root cause: Our custom admin index template includes a partial that Django 5.2 removed.

Steps to Reproduce
1) Log in to the Django admin.
2) Navigate to /admin/.
3) Error occurs during tickets.admin.index while rendering tickets/templates/admin/index.html.

Expected
- Admin dashboard renders with app list, device alerts, inventory alerts, and recent actions.

Actual
- 500 error: TemplateDoesNotExist admin/includes/recent_actions.html
- In template tickets/templates/admin/index.html at line 71: {% include "admin/includes/recent_actions.html" %}

Environment
- Django 5.2.5
- Python 3.11.0
- OS: Windows 10 (local dev)
- View: tickets.admin.index

Traceback (key lines)
- TemplateDoesNotExist at /admin/
- printer_system/.venv/Lib/site-packages/django/template/engine.py: select_template()
- Raised during: tickets.admin.index

Fix Applied
- Commit e666e2c adds an app-level fallback template: tickets/templates/admin/includes/recent_actions.html
- This restores the "Recent actions" panel include on Django 5.2.

Follow-ups (optional)
- Update dashboard to use the current Django admin patterns for recent actions.
- If the panel is not needed, remove the include and the get_admin_log call.
