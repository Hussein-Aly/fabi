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
import base64
from io import BytesIO

from mbai.aiserver.exceptions import InvalidBase64FileException


def get_file_stream_from_encoded_str(excel_content_encoded: str) -> BytesIO:
    try:
        excel_content_decoded = base64.b64decode(excel_content_encoded)
        excel_file_stream = BytesIO(excel_content_decoded)
    except Exception as e:
        raise InvalidBase64FileException.from_exception(e, "could not decode file content")

    return excel_file_stream
