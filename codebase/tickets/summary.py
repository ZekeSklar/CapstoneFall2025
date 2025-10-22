from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.timesince import timesince

from .models import IssueSummaryRecipient, IssueSummaryState, RequestTicket

DEFAULT_INTERVAL = getattr(settings, "ISSUE_SUMMARY_INTERVAL", timedelta(hours=24))
DEFAULT_INCLUDE_CLOSED = getattr(settings, "ISSUE_SUMMARY_INCLUDE_CLOSED", False)
DEFAULT_LOOKBACK_HOURS = getattr(settings, "ISSUE_SUMMARY_LOOKBACK_HOURS", None)


def _normalize_emails(addresses: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for addr in addresses:
        email = (addr or "").strip()
        if not email:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(email)
    return normalized


def _flagged_user_emails() -> list[str]:
    try:
        queryset = IssueSummaryRecipient.objects.select_related("user").filter(
            subscribed=True,
            user__is_active=True,
        )
        return [
            recipient.user.email.strip()
            for recipient in queryset
            if recipient.user.email and recipient.user.email.strip()
        ]
    except (ProgrammingError, OperationalError):
        return []



def _resolve_recipients(explicit: str | Iterable[str] | None = None) -> list[str]:
    if explicit:
        if isinstance(explicit, str):
            candidates = [explicit]
        else:
            candidates = list(explicit)
        explicit_emails = _normalize_emails(candidates)
        if explicit_emails:
            return explicit_emails

    flagged = _normalize_emails(_flagged_user_emails())
    if flagged:
        return flagged

    fallback = getattr(settings, "ISSUE_SUMMARY_RECIPIENT", "").strip()
    fallback_emails = _normalize_emails([fallback])
    if fallback_emails:
        return fallback_emails

    email_to = getattr(settings, "EMAIL_TO", [])
    email_to_emails = _normalize_emails(email_to)
    if email_to_emails:
        return [email_to_emails[0]]

    return _normalize_emails(["sklarz@berea.edu"])



def render_issue_summary(*, include_closed: bool | None = None, lookback_hours: int | None = None):
    include_closed = DEFAULT_INCLUDE_CLOSED if include_closed is None else include_closed
    lookback_hours = DEFAULT_LOOKBACK_HOURS if lookback_hours is None else lookback_hours

    queryset = RequestTicket.objects.filter(type=RequestTicket.ISSUE).select_related("printer")
    if not include_closed:
        queryset = queryset.exclude(status=RequestTicket.CLOSED)

    if lookback_hours:
        window_start = timezone.now() - timedelta(hours=lookback_hours)
        queryset = queryset.filter(created_at__gte=window_start)
    else:
        window_start = None

    queryset = queryset.order_by("created_at")
    issues = list(queryset)
    now = timezone.now()

    if not issues:
        if lookback_hours:
            body = f"No printer issues matched the summary window (last {lookback_hours} hours)."
        else:
            body = "There are no printer issues to report at this time."
        subject = "Daily printer issue summary (0 issues)"
        return subject, body, 0

    lines = [
        f"Printer issue summary for {now:%Y-%m-%d %H:%M %Z}",
        "",
        f"Total issues in this report: {len(issues)}",
    ]
    if not include_closed:
        lines.append("Only non-closed issues are listed.")
    if lookback_hours:
        lines.append(f"Window: last {lookback_hours} hours.")
    lines.append("")

    for ticket in issues:
        printer = ticket.printer
        age = timesince(ticket.created_at, now) or "just now"
        status = ticket.get_status_display() if hasattr(ticket, "get_status_display") else ticket.status
        lines.append(f"- {printer.campus_label} ({printer.asset_tag}) | status: {status} | reported {age} ago")
        if ticket.details:
            first_line = ticket.details.strip().splitlines()[0].strip()
            if first_line:
                lines.append(f"  Details: {first_line}")
        lines.append("")

    body = "\n".join(lines).strip() + "\n"
    subject = f"Daily printer issue summary ({len(issues)} issues)"
    return subject, body, len(issues)



def send_issue_summary(*, recipient: str | Iterable[str] | None = None, include_closed: bool | None = None, lookback_hours: int | None = None):
    recipients = _resolve_recipients(recipient)
    if not recipients:
        return False, {"reason": "missing-recipient"}

    subject, body, count = render_issue_summary(include_closed=include_closed, lookback_hours=lookback_hours)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
    return True, {"recipients": recipients, "count": count, "subject": subject}



def maybe_send_daily_issue_summary():
    recipients = _resolve_recipients()
    if not recipients:
        return False

    interval = getattr(settings, "ISSUE_SUMMARY_INTERVAL", DEFAULT_INTERVAL)

    try:
        with transaction.atomic():
            state, _ = IssueSummaryState.objects.select_for_update().get_or_create(pk=1, defaults={"last_sent_at": None})
            now = timezone.now()
            if state.last_sent_at and now - state.last_sent_at < interval:
                return False

            subject, body, _ = render_issue_summary()

            state.last_sent_at = now
            state.save(update_fields=["last_sent_at"])

            transaction.on_commit(
                lambda subj=subject, msg=body, rcpts=recipients: send_mail(subj, msg, settings.DEFAULT_FROM_EMAIL, rcpts)
            )
    except (ProgrammingError, OperationalError):
        return False

    return True

