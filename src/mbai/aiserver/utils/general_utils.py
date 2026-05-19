# ==========================================================================
# Copyright (c) Fabasoft R&D GmbH, A-4020 Linz, 1988-2026.
#
# Alle Rechte vorbehalten. Alle verwendeten Hard- und Softwarenamen sind
# Handelsnamen und/oder Marken der jeweiligen Hersteller.
#
# Der Nutzer des Computerprogramms anerkennt, dass der oben stehende
# Copyright-Vermerk im Sinn des Welturheberrechtsabkommens an der vom
# Urheber festgelegten Stelle in der Funktion des Computerprogramms
# angebracht bleibt, um den Vorbehalt des Urheberrechtes genuegend zum
# Ausdruck zu bringen. Dieser Urheberrechtsvermerk darf weder vom Kunden,
# Nutzer und/oder von Dritten entfernt, veraendert oder disloziert werden.
# ==========================================================================
from datetime import datetime, UTC

from pydantic import validate_call


@validate_call
def safe_item_from_list(lst: list, idx: int, default: int = None) -> list:
    return (lst[idx : idx + 1] or [default])[0]


def get_current_utc_ts_iso_z() -> str:
    """returns the current UTC timestamp as ISO 8601 string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def number_in_range(num: int, lower_bound: int, upper_bound: int) -> bool:

    if any(item is None for item in [num, lower_bound, upper_bound]):
        return False

    return lower_bound <= num <= upper_bound
