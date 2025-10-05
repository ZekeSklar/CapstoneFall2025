from __future__ import annotations

from .summary import maybe_send_daily_issue_summary


class IssueSummaryMiddleware:
    """Trigger a once-per-day issue summary email on incoming requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        maybe_send_daily_issue_summary()
        return self.get_response(request)
