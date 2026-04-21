"""Retrieval Executor — deterministic RAG step.

Embeds the ticket text, searches the vector store, ranks results,
and produces a RetrievalResult. No LLM call.
"""

from __future__ import annotations

import logging

from src.knowledge.store import KnowledgeStore
from src.models.retrieval import RetrievalResult
from src.models.ticket import TicketContext
from src.models.triage import TriageResult

logger = logging.getLogger(__name__)


def retrieve_context(
    ticket: TicketContext,
    triage: TriageResult | None,
    store: KnowledgeStore,
) -> RetrievalResult:
    """Search the KB for documents relevant to this ticket.

    The search query combines the ticket text with the triage category
    to narrow the semantic space.
    """
    query = _build_query(ticket, triage)
    chunks = store.search(query)

    max_sim = max((c.similarity_score for c in chunks), default=0.0)

    result = RetrievalResult(
        ticket_id=ticket.ticket_id,
        query_used=query,
        chunks=chunks,
        retrieval_empty=len(chunks) == 0,
        max_similarity=max_sim,
    )

    logger.info(
        "Retrieval for %s: %d chunks, max_similarity=%.3f, empty=%s",
        ticket.ticket_id,
        len(chunks),
        max_sim,
        result.retrieval_empty,
    )
    return result


def _build_query(ticket: TicketContext, triage: TriageResult | None) -> str:
    """Construct a search query from ticket text and triage category."""
    parts = [ticket.sanitized_text]

    if triage and triage.category.value != "unknown":
        parts.append(f"Category: {triage.category.value}")

    if ticket.extracted_error_codes:
        parts.append(f"Error codes: {', '.join(ticket.extracted_error_codes)}")

    return " ".join(parts)
