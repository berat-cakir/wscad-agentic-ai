"""Prompt injection detection for ticket text.

Scans for known injection patterns before any text reaches an LLM agent.
Detection does NOT reject the ticket — it flags it and wraps the content
in a data boundary to reduce injection effectiveness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("instruction_override", re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE)),
    ("role_hijack", re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE)),
    ("system_prompt_leak", re.compile(r"system\s*prompt\s*:", re.IGNORECASE)),
    ("system_tag", re.compile(r"<\s*system\s*>", re.IGNORECASE)),
    ("override_directive", re.compile(r"IMPORTANT:\s*override", re.IGNORECASE)),
    ("forget_instructions", re.compile(r"forget\s+(everything|your\s+instructions)", re.IGNORECASE)),
    ("inst_tag", re.compile(r"\[INST\]", re.IGNORECASE)),
    ("code_block_system", re.compile(r"```system", re.IGNORECASE)),
    ("delimiter_injection", re.compile(r"---\s*(?:system|assistant|user)\s*---", re.IGNORECASE)),
    ("base64_payload", re.compile(r"base64[:\s]+[A-Za-z0-9+/]{50,}", re.IGNORECASE)),
]

DATA_BOUNDARY_OPEN = "<user_ticket_content>"
DATA_BOUNDARY_CLOSE = "</user_ticket_content>"

CONFIDENCE_PENALTY = 0.1


@dataclass
class InjectionScanResult:
    detected: bool
    matched_patterns: list[str]
    wrapped_text: str


def scan_for_injection(text: str) -> InjectionScanResult:
    """Scan text for prompt injection patterns.

    Returns an InjectionScanResult with:
    - detected: whether any pattern matched
    - matched_patterns: names of matched patterns
    - wrapped_text: text wrapped in data boundaries if injection detected, original text otherwise
    """
    matched = []
    for name, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(name)

    if matched:
        wrapped = f"{DATA_BOUNDARY_OPEN}\n{text}\n{DATA_BOUNDARY_CLOSE}"
        return InjectionScanResult(detected=True, matched_patterns=matched, wrapped_text=wrapped)

    return InjectionScanResult(detected=False, matched_patterns=[], wrapped_text=text)
