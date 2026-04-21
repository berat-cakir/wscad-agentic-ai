"""Rule Engine Executor — deterministic fast path for known patterns.

When a ticket matches a known rule AND retrieval confirms the KB supports it,
this executor resolves the ticket without any LLM call.

Returns None if no rule matches — the workflow then routes to the Resolution Agent.
"""

from __future__ import annotations

import logging

from src.config import settings
from src.models.resolution import ResolutionResult
from src.models.retrieval import RetrievalResult
from src.models.ticket import TicketContext
from src.models.triage import TriageResult
from src.rules.known_patterns import match_rule

logger = logging.getLogger(__name__)


def try_rule_resolution(
    ticket: TicketContext,
    triage: TriageResult,
    retrieval: RetrievalResult,
) -> ResolutionResult | None:
    """Attempt deterministic resolution via known pattern matching.

    Returns a ResolutionResult if a rule fires AND retrieval confirms it.
    Returns None if no rule matches or retrieval evidence is too weak.
    """
    rule_match = match_rule(
        error_codes=ticket.extracted_error_codes,
        keywords=ticket.extracted_keywords,
        category=triage.category.value,
    )

    if rule_match is None:
        logger.info("Rule engine: no match for %s", ticket.ticket_id)
        return None

    if retrieval.max_similarity < settings.rule_engine_similarity_threshold:
        logger.info(
            "Rule engine: rule %s matched for %s but retrieval score %.3f < threshold %.3f — deferring to LLM",
            rule_match.rule_id,
            ticket.ticket_id,
            retrieval.max_similarity,
            settings.rule_engine_similarity_threshold,
        )
        return None

    retrieved_sources = [c.source for c in retrieval.chunks]
    reasoning = list(rule_match.reasoning)
    reasoning.append(
        f"Rule engine match confirmed by retrieval (max similarity: {retrieval.max_similarity:.2f})"
    )

    logger.info(
        "Rule engine: resolved %s via rule %s (confidence: %.2f)",
        ticket.ticket_id,
        rule_match.rule_id,
        rule_match.confidence,
    )

    return ResolutionResult(
        ticket_id=ticket.ticket_id,
        proposed_solution=rule_match.solution,
        raw_confidence=rule_match.confidence,
        reasoning_trace=reasoning,
        retrieved_sources=retrieved_sources,
        follow_up_questions=[],
        resolved_by="rule_engine",
    )
