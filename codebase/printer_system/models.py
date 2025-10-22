"""
Project-level models shim.

This Django project keeps all database models in the `tickets` app
(`tickets/models.py`). The project package (`printer_system`) is not an
installed app and should not declare its own models. To avoid confusion and
support imports like `from printer_system.models import Printer`, this module
re-exports the real models from `tickets.models`.

Do not add new model classes here — put them in `tickets/models.py` instead.
"""

from tickets.models import (
    InventoryItem,
    IssueSummaryRecipient,
    IssueSummaryState,
    Printer,
    PrinterComment,
    PrinterGroup,
    PrinterStatus,
    RequestTicket,
)

__all__ = [
    "InventoryItem",
    "IssueSummaryRecipient",
    "IssueSummaryState",
    "Printer",
    "PrinterComment",
    "PrinterGroup",
    "PrinterStatus",
    "RequestTicket",
]
