from django.core.management.base import BaseCommand

from tickets.summary import send_issue_summary


class Command(BaseCommand):
    """Send a single issue summary email."""

    help = "Send a summary email of printer issues, including how long each has been open."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-closed",
            action="store_true",
            help="Include closed issues in the summary report.",
        )
        parser.add_argument(
            "--lookback-hours",
            type=int,
            default=None,
            help="Only include issues created within the last N hours (default: no limit).",
        )

    def handle(self, *args, **options):
        include_closed = options["include_closed"]
        lookback_hours = options["lookback_hours"]

        success, info = send_issue_summary(include_closed=include_closed, lookback_hours=lookback_hours)

        if not success:
            reason = info.get("reason") if isinstance(info, dict) else info
            if reason == "missing-recipient":
                self.stdout.write(self.style.WARNING("No ISSUE_SUMMARY_RECIPIENT configured; skipping email."))
            else:
                self.stdout.write(self.style.ERROR(f"Issue summary email not sent ({reason})."))
            return

        recipients = info.get("recipients", [])
        count = info.get("count")
        subject = info.get("subject")

        detail_notes = []
        if lookback_hours:
            detail_notes.append(f"last {lookback_hours} hours")
        if include_closed:
            detail_notes.append("includes closed issues")
        detail_suffix = f" ({'; '.join(detail_notes)})" if detail_notes else ""
        recipients_display = ', '.join(recipients) if recipients else 'no recipients'

        self.stdout.write(
            self.style.SUCCESS(
                f"Issue summary '{subject}' sent to {recipients_display} ({count} issues){detail_suffix}."
            )
        )
