"""Date-gating logic determining statutory applicability (BNS vs IPC)."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context.case_context import CaseContext
    from .legal_rules import LegalReference

BNS_IN_FORCE_DATE = date(2024, 7, 1)


def select_law(offence_date: date | None) -> str | None:
    """Return applicable statutory code based on offence date.
    
    Returns:
        "BNS" if offence_date >= 2024-07-01
        "IPC" if offence_date < 2024-07-01
        None if offence_date is None (missing or ambiguous; forces officer review)
    """
    if offence_date is None:
        return None
    return "BNS" if offence_date >= BNS_IN_FORCE_DATE else "IPC"


def filter_references_by_date(
    references: tuple[LegalReference, ...],
    offence_date: date | None,
) -> tuple[LegalReference, ...]:
    """Filter legal references by statutory effective date range."""
    if offence_date is None:
        return ()
    max_date = date.max
    return tuple(
        ref for ref in references
        if ref.effective_from <= offence_date < (ref.effective_to or max_date)
    )


def extract_offence_date(context: CaseContext) -> tuple[date | None, bool]:
    """Extract and validate the date of occurrence from the case context.
    
    Returns:
        (extracted_date, is_ambiguous_or_missing)
    """
    dates: list[date] = []
    
    # Check occurrence timeline events
    for event in context.occurrence_details:
        if event.timestamp and event.timestamp.value is not None:
            val = event.timestamp.value
            if isinstance(val, datetime):
                dates.append(val.date())
            elif isinstance(val, date):
                dates.append(val)
            elif isinstance(val, str):
                try:
                    dates.append(datetime.fromisoformat(val.replace("Z", "+00:00")).date())
                except ValueError:
                    pass

    # Check FIR details (e.g. occurrence_datetime or registration_date)
    for fact in context.fir_details:
        if fact.value is not None:
            val = fact.value
            if isinstance(val, datetime):
                dates.append(val.date())
            elif isinstance(val, date):
                dates.append(val)
            elif isinstance(val, str):
                try:
                    dates.append(datetime.fromisoformat(val.replace("Z", "+00:00")).date())
                except ValueError:
                    try:
                        dates.append(date.fromisoformat(val))
                    except ValueError:
                        pass

    # Fallback to document attributes if no FIR/occurrence date
    if not dates:
        for doc in context.documents:
            for attr_name, fact in doc.attributes.items():
                if "date" in attr_name.casefold() and fact.value is not None:
                    val = fact.value
                    if isinstance(val, datetime):
                        dates.append(val.date())
                    elif isinstance(val, date):
                        dates.append(val)
                    elif isinstance(val, str):
                        try:
                            dates.append(datetime.fromisoformat(val.replace("Z", "+00:00")).date())
                        except ValueError:
                            try:
                                dates.append(date.fromisoformat(val))
                            except ValueError:
                                pass

    unique_dates = list(dict.fromkeys(dates))
    if not unique_dates:
        return None, True
    if len(unique_dates) > 1:
        # Ambiguous multiple occurrence dates
        return unique_dates[0], True
    return unique_dates[0], False
