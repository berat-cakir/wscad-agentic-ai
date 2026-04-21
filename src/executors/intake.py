"""Intake Executor — the security boundary of the pipeline.

Parses raw ticket JSON, sanitizes text, detects injection attempts,
extracts signals (error codes, keywords), and produces a validated TicketContext.
No LLM call. Fully deterministic.
"""

from __future__ import annotations

import logging

from src.models.ticket import TicketContext, TicketInput, TicketMetadata
from src.security.injection_detector import scan_for_injection
from src.security.sanitizer import (
    extract_error_codes,
    extract_keywords,
    sanitize_metadata_value,
    sanitize_text,
)

logger = logging.getLogger(__name__)


def process_ticket(ticket: TicketInput) -> TicketContext:
    """Transform a raw TicketInput into a validated, enriched TicketContext."""
    warnings: list[str] = []

    sanitized, text_warnings = sanitize_text(ticket.text)
    warnings.extend(text_warnings)

    injection_result = scan_for_injection(sanitized)
    if injection_result.detected:
        warnings.append(f"Prompt injection patterns detected: {injection_result.matched_patterns}")
        logger.warning("Injection detected in %s: %s", ticket.ticket_id, injection_result.matched_patterns)

    metadata = TicketMetadata(
        product=sanitize_metadata_value(ticket.metadata.product),
        version=sanitize_metadata_value(ticket.metadata.version),
        os=sanitize_metadata_value(ticket.metadata.os),
        urgency=sanitize_metadata_value(ticket.metadata.urgency),
    )

    error_codes = extract_error_codes(sanitized)
    keywords = extract_keywords(sanitized)

    context = TicketContext(
        ticket_id=ticket.ticket_id,
        original_text=ticket.text,
        sanitized_text=injection_result.wrapped_text,
        metadata=metadata,
        extracted_error_codes=error_codes,
        extracted_keywords=keywords,
        injection_detected=injection_result.detected,
        validation_warnings=warnings,
    )

    logger.info(
        "Intake complete for %s: errors=%s, keywords=%s, injection=%s",
        ticket.ticket_id,
        error_codes,
        keywords,
        injection_result.detected,
    )
    return context
