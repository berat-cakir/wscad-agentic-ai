"""Input sanitization for ticket text and metadata.

This module is the first line of defense — it runs before any LLM call.
All cleaning is deterministic and auditable.
"""

from __future__ import annotations

import re
import unicodedata

from src.config import settings


def sanitize_text(text: str) -> tuple[str, list[str]]:
    """Clean ticket text for safe downstream processing.

    Returns:
        Tuple of (sanitized_text, list of warning messages).
    """
    warnings: list[str] = []

    text = _strip_null_bytes(text)
    text = _normalize_unicode(text)
    text = _strip_html_tags(text)
    text = _strip_control_characters(text)
    text = _collapse_whitespace(text)

    if len(text) > settings.max_ticket_text_length:
        warnings.append(
            f"Text truncated from {len(text)} to {settings.max_ticket_text_length} characters"
        )
        text = text[: settings.max_ticket_text_length]

    if not text.strip():
        warnings.append("Ticket text is empty after sanitization")

    return text.strip(), warnings


def sanitize_metadata_value(value: str | None) -> str | None:
    """Sanitize a single metadata field value."""
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    value = _strip_null_bytes(value)
    value = _strip_html_tags(value)
    value = _collapse_whitespace(value)
    return value.strip()[:200]


def extract_error_codes(text: str) -> list[str]:
    """Extract numeric error codes from ticket text (e.g., 'Error 504', 'code 1234')."""
    pattern = r"(?:error|code|err)\s*[:#]?\s*(\d{3,5})"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return sorted(set(matches))


def extract_keywords(text: str) -> list[str]:
    """Extract domain-relevant keywords for downstream triage hints."""
    keyword_patterns = {
        "license": r"\b(?:licen[cs]e|activation|activate|expired?|license\s*manager)\b",
        "installation": r"\b(?:install(?:ation|ed|ing)?|setup|\.net|runtime)\b",
        "crash": r"\b(?:crash(?:es|ed|ing)?|freeze[sd]?|hang[sd]?|not\s+respond)\b",
        "startup": r"\b(?:start(?:up|s|ed)?|launch|open(?:s|ed|ing)?|boot)\b",
        "update": r"\b(?:updat(?:e[ds]?|ing)|upgrad(?:e[ds]?|ing)|patch)\b",
        "error": r"\b(?:error|fail(?:s|ed|ure|ing)?|broken|not\s+work)\b",
        "offline": r"\b(?:offline|no\s+internet|disconnected|air[- ]?gap)\b",
        "configuration": r"\b(?:setting[s]?|config(?:uration)?|preference[s]?|default[s]?)\b",
    }
    found = []
    text_lower = text.lower()
    for keyword, pattern in keyword_patterns.items():
        if re.search(pattern, text_lower):
            found.append(keyword)
    return found


def _strip_null_bytes(text: str) -> str:
    return text.replace("\x00", "")


def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _strip_control_characters(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t", " "))


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
