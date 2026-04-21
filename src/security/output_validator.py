"""LLM output validation — ensures responses are schema-compliant, grounded, and safe.

Runs after every LLM call, before the result is accepted into the workflow.
"""

from __future__ import annotations

import re

from src.config import settings

_KNOWN_KB_FILES: set[str] | None = None

PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,5}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]


def get_known_kb_files() -> set[str]:
    """Load the set of actual KB filenames from disk (cached after first call)."""
    global _KNOWN_KB_FILES
    if _KNOWN_KB_FILES is None:
        kb_path = settings.knowledge_base_path
        if kb_path.exists():
            _KNOWN_KB_FILES = {f.name for f in kb_path.iterdir() if f.is_file()}
        else:
            _KNOWN_KB_FILES = set()
    return _KNOWN_KB_FILES


def validate_sources(claimed_sources: list[str]) -> tuple[list[str], list[str]]:
    """Validate that claimed source filenames match actual KB documents.

    Returns:
        Tuple of (valid_sources, invalid_sources).
    """
    known = get_known_kb_files()
    valid = [s for s in claimed_sources if s in known]
    invalid = [s for s in claimed_sources if s not in known]
    return valid, invalid


def clamp_confidence(value: float) -> float:
    """Ensure confidence is within [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def detect_pii(text: str) -> list[str]:
    """Scan text for common PII patterns. Returns list of pattern types found."""
    found = []
    labels = ["email", "phone_number", "ssn"]
    for pattern, label in zip(PII_PATTERNS, labels):
        if pattern.search(text):
            found.append(label)
    return found


def redact_pii(text: str) -> str:
    """Replace detected PII patterns with redaction markers."""
    for pattern in PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
