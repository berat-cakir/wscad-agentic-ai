"""Output Executor — formats the final AgentOutput from resolved tickets.

Applies confidence calibration, output validation, and PII redaction.
No LLM call. Fully deterministic.
"""

from __future__ import annotations

import logging

from src.models.output import AgentOutput
from src.models.resolution import ResolutionResult
from src.models.retrieval import RetrievalResult
from src.models.triage import TriageResult
from src.security.injection_detector import CONFIDENCE_PENALTY
from src.security.output_validator import (
    clamp_confidence,
    detect_pii,
    redact_pii,
    validate_sources,
)

logger = logging.getLogger(__name__)


def format_resolved_output(
    triage: TriageResult,
    retrieval: RetrievalResult,
    resolution: ResolutionResult,
    injection_detected: bool = False,
) -> AgentOutput:
    """Build a final AgentOutput for a successfully resolved ticket."""
    confidence = _calibrate_confidence(
        raw_confidence=resolution.raw_confidence,
        retrieval=retrieval,
        triage=triage,
        injection_detected=injection_detected,
    )

    valid_sources, invalid_sources = validate_sources(resolution.retrieved_sources)
    if invalid_sources:
        logger.warning("Stripping unverified sources for %s: %s", triage.ticket_id, invalid_sources)
        confidence = max(0.0, confidence - 0.05 * len(invalid_sources))

    solution_text = resolution.proposed_solution
    pii_types = detect_pii(solution_text)
    if pii_types:
        logger.warning("PII detected in output for %s: %s", triage.ticket_id, pii_types)
        solution_text = redact_pii(solution_text)

    confidence = clamp_confidence(confidence)

    return AgentOutput(
        ticket_id=triage.ticket_id,
        status="resolved",
        category=triage.category,
        priority=triage.priority,
        proposed_solution=solution_text,
        confidence=round(confidence, 2),
        reasoning_trace=resolution.reasoning_trace,
        retrieved_sources=valid_sources,
        follow_up_questions=[],
        preliminary_assessment=None,
        resolved_by=resolution.resolved_by,
    )


def _calibrate_confidence(
    raw_confidence: float,
    retrieval: RetrievalResult,
    triage: TriageResult,
    injection_detected: bool,
) -> float:
    """Confidence calibration via weighted blend of LLM confidence and retrieval evidence.

    Halved for unknown-category tickets. Matches the routing pre-check formula
    so the displayed confidence is consistent with the resolve/clarify decision.
    """
    base = raw_confidence
    retrieval_factor = retrieval.max_similarity if retrieval.max_similarity > 0 else 0.3

    blended = 0.6 * base + 0.4 * retrieval_factor

    if triage.category.value == "unknown":
        blended *= 0.5

    if injection_detected:
        blended -= CONFIDENCE_PENALTY

    return blended
