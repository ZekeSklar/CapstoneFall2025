from django.core.management.base import BaseCommand

from tickets.models import Printer
from tickets.printer_status import ensure_latest_status


class Command(BaseCommand):
    help = "Pre-warm SNMP status cache for all printers (optionally force)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh for each printer, ignoring cache window.",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        printers = list(Printer.objects.all().order_by("campus_label"))
        total = 0
        for p in printers:
            ensure_latest_status(p, force=force)
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Prewarmed {total} printers (force={force})"))

