from __future__ import annotations

import os
import time
from datetime import datetime

from django.conf import settings

from .summary import maybe_send_daily_issue_summary


class IssueSummaryMiddleware:
    """Trigger a once-per-day issue summary email on incoming requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        maybe_send_daily_issue_summary()
        return self.get_response(request)


class SlowRequestLoggingMiddleware:
    """Log requests slower than a threshold to data/slow_requests.log.

    Threshold can be overridden via SLOW_REQUEST_THRESHOLD_SECONDS env var.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        try:
            self.threshold = float(os.getenv('SLOW_REQUEST_THRESHOLD_SECONDS', '1.0'))
        except Exception:
            self.threshold = 1.0
        self.log_path = settings.BASE_DIR / 'data' / 'slow_requests.log'
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - start
        if duration >= self.threshold:
            try:
                user = getattr(request, 'user', None)
                user_repr = user.get_username() if getattr(user, 'is_authenticated', False) else 'anon'
            except Exception:
                user_repr = 'anon'
            line = f"{datetime.now().isoformat()} {duration:.3f}s {request.method} {request.path} {response.status_code} user={user_repr}\n"
            try:
                with open(self.log_path, 'a', encoding='utf-8') as fh:
                    fh.write(line)
            except Exception:
                pass
        return response
