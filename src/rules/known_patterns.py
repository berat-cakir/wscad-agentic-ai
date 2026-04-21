"""Known pattern rules for deterministic ticket resolution.

Maps error codes and high-confidence signal combinations to
deterministic solutions. The Rule Engine Executor uses these
to bypass the LLM when a match is found.

In WSCAD's engineering context, this is the same pattern that
would handle electrical standards: wire gauge rules, breaker
ratings, and safety interlocks are deterministic constraints.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleMatch:
    """A deterministic resolution from the rule engine."""

    rule_id: str
    solution: str
    reasoning: list[str]
    expected_sources: list[str]
    confidence: float = 0.95


KNOWN_RULES: list[dict] = [
    {
        "rule_id": "ERR_504_LICENSE",
        "trigger_error_codes": ["504"],
        "trigger_categories": ["licensing"],
        "solution": (
            "Error code 504 indicates missing or expired licensing information, "
            "commonly occurring after application updates. Open the License Manager "
            "and re-activate your license. If using an offline license, ensure the "
            "license file matches the current application version."
        ),
        "reasoning": [
            "Error code 504 detected in ticket text",
            "Error 504 is a known licensing validation failure (rule: ERR_504_LICENSE)",
            "Standard resolution: License Manager re-activation",
        ],
        "expected_sources": ["Common_Errors.md", "Licensing_Offline_Activation.md"],
    },
    {
        "rule_id": "OFFLINE_LICENSE_ACTIVATION",
        "trigger_keywords": ["offline", "license"],
        "trigger_categories": ["licensing"],
        "require_no_error_codes": True,
        "solution": (
            "Offline licenses must be activated using the License Manager. "
            "Open the License Manager, select 'Offline Activation', and follow "
            "the guided process. Ensure the license file is not expired and matches "
            "the installed application version."
        ),
        "reasoning": [
            "Ticket mentions offline license activation",
            "No error code present — likely an informational/how-to request",
            "Standard resolution: License Manager offline activation procedure",
        ],
        "expected_sources": ["Licensing_Offline_Activation.md"],
    },
]


def match_rule(
    error_codes: list[str],
    keywords: list[str],
    category: str,
) -> RuleMatch | None:
    """Attempt to match a ticket against known deterministic rules.

    Returns a RuleMatch if a rule fires, None otherwise.
    Rules are evaluated in order; first match wins.
    """
    for rule in KNOWN_RULES:
        if _rule_matches(rule, error_codes, keywords, category):
            return RuleMatch(
                rule_id=rule["rule_id"],
                solution=rule["solution"],
                reasoning=rule["reasoning"],
                expected_sources=rule["expected_sources"],
            )
    return None


def _rule_matches(
    rule: dict,
    error_codes: list[str],
    keywords: list[str],
    category: str,
) -> bool:
    """Check if a single rule's trigger conditions are met."""
    if "trigger_categories" in rule:
        if category not in rule["trigger_categories"]:
            return False

    if "trigger_error_codes" in rule:
        if not any(code in error_codes for code in rule["trigger_error_codes"]):
            return False

    if "trigger_keywords" in rule:
        if not all(kw in keywords for kw in rule["trigger_keywords"]):
            return False

    if rule.get("require_no_error_codes") and error_codes:
        return False

    return True
