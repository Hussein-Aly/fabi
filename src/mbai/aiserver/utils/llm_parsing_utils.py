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
import json
from typing import Any

import json5
import re
import unicodedata


class LLMStrParsingUtils:
    @staticmethod
    def _cleanup_llm_json_str(
        llm_output: str,
    ) -> str:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", llm_output)

        if match:
            text = match.group(1)
        else:
            start = llm_output.find("{")
            end = llm_output.rfind("}") + 1
            text = llm_output[start:end]

        return text

    @staticmethod
    def cleanup_value_for_prompt(value: Any) -> str:
        value = str(value)
        value = re.sub(r'["""„‟❝❞〝〞]', "'", value)  # double quote variants → '
        value = re.sub(r"['''‚‛❛❜`]", "'", value)  # single quote variants → '
        value = value.replace("\xa0", " ")
        value = unicodedata.normalize("NFKC", value)

        # Remove other common problematic chars ( especially for json parsing )
        value = value.replace("\u200b", "")  # zero-width space
        value = value.replace("\ufeff", "")  # BOM
        return value

    @staticmethod
    def extract_json_obj_from_llm_output(llm_output: str) -> list[dict] | dict:
        """Robustly extract JSON from potentially messy LLM output.
        does not work for lists -> only {...}
        """
        # Step 1: Extract from code blocks if present
        text = LLMStrParsingUtils._cleanup_llm_json_str(llm_output)
        # Step 2: Clean problematic characters
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[\xa0\u200b\ufeff]", " ", text)
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

        # Step 4: Try strict parsing first, fall back to lenient
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return json5.loads(text)
