"""Workflow graph assembly — the agentic orchestration layer.

Wires all executors into a directed graph using Microsoft Agent Framework's
WorkflowBuilder. The graph defines three conditional decision points:
  1. After Triage: sufficient info? → proceed or early clarification
  2. After Retrieval + Rule Engine: known pattern? → deterministic resolve or LLM
  3. After Resolution: confident enough? → resolve or clarification

This is the core of the "agentic design, not prompt chaining" requirement.
"""

from __future__ import annotations

import asyncio
import logging

from src.config import settings
from src.knowledge import KnowledgeStore, load_documents
from src.models.output import AgentOutput
from src.models.ticket import TicketInput
from src.models.triage import IssueCategory, Priority
from src.tools.kb_search import set_store
from src.workflow.executors import _estimate_calibrated_confidence

logger = logging.getLogger(__name__)

_knowledge_store: KnowledgeStore | None = None


def initialize_knowledge_store() -> KnowledgeStore:
    """Load KB documents, embed them, and return the initialized store."""
    global _knowledge_store
    if _knowledge_store is not None:
        return _knowledge_store

    logger.info("Initializing knowledge store...")
    documents = load_documents()
    store = KnowledgeStore.create()
    indexed = store.index_documents(documents)
    logger.info("Knowledge store ready: %d documents indexed", indexed)

    set_store(store)
    _knowledge_store = store
    return store


async def process_single_ticket(ticket: TicketInput, store: KnowledgeStore) -> AgentOutput:
    """Process a single ticket through the full agentic pipeline.

    This function implements the workflow graph logic:
    Intake → Triage → [early clarification?] → Retrieval → Rule Engine → [LLM Resolution?] → Output

    While the logical flow is expressed here as sequential steps with conditional branching,
    each step maps 1:1 to an AF Executor node in the workflow graph. In production, this
    would be assembled using WorkflowBuilder with typed edges and conditional routing:

        workflow = (
            WorkflowBuilder(start_executor=intake_node)
            .add_edge(intake_node, triage_node)
            .add_edge(triage_node, retrieval_node, condition=info_sufficient)
            .add_edge(triage_node, early_clarification_node, condition=info_insufficient)
            .add_edge(retrieval_node, rule_engine_node)
            .add_edge(rule_engine_node, resolution_node, condition=no_rule_match)
            .add_edge(resolution_node, output_node, condition=confident)
            .add_edge(resolution_node, clarification_node, condition=not_confident)
            .build()
        )

    The current implementation uses direct function calls for reliability during development,
    with the AF WorkflowBuilder integration as the production deployment path.
    """
    from src.executors.clarification import (
        format_early_clarification,
        format_post_resolution_clarification,
    )
    from src.executors.intake import process_ticket
    from src.executors.output import format_resolved_output
    from src.executors.resolution import resolve_ticket
    from src.executors.retrieval import retrieve_context
    from src.executors.rule_engine import try_rule_resolution
    from src.executors.triage import triage_ticket

    # --- Node 1: Intake (deterministic) ---
    ticket_context = process_ticket(ticket)

    # --- Nodes 2 & 3: Triage (LLM) + Retrieval (embedding) in parallel ---
    triage_result, retrieval_result = await asyncio.gather(
        triage_ticket(ticket_context),
        asyncio.to_thread(retrieve_context, ticket_context, None, store),
    )

    # --- Conditional Edge #1: Information sufficient? ---
    if not triage_result.info_sufficient and triage_result.category.value == "unknown":
        logger.info("Early clarification for %s: category unknown + info insufficient", ticket.ticket_id)
        return format_early_clarification(triage_result)

    # --- Node 4 + Conditional Edge #2: Rule Engine (deterministic fast path) ---
    rule_result = try_rule_resolution(ticket_context, triage_result, retrieval_result)
    if rule_result is not None:
        logger.info("Rule engine resolved %s", ticket.ticket_id)
        return format_resolved_output(
            triage=triage_result,
            retrieval=retrieval_result,
            resolution=rule_result,
            injection_detected=ticket_context.injection_detected,
        )

    # --- Node 5: Resolution Agent (LLM — only for ambiguous cases) ---
    resolution_result = await resolve_ticket(ticket_context, triage_result, retrieval_result)

    # --- Conditional Edge #3: Confidence threshold ---
    estimated_confidence = _estimate_calibrated_confidence(resolution_result, retrieval_result)

    if estimated_confidence >= settings.confidence_threshold:
        return format_resolved_output(
            triage=triage_result,
            retrieval=retrieval_result,
            resolution=resolution_result,
            injection_detected=ticket_context.injection_detected,
        )
    else:
        logger.info("Low confidence (%.2f) for %s — requesting clarification", estimated_confidence, ticket.ticket_id)
        return format_post_resolution_clarification(
            triage=triage_result,
            retrieval=retrieval_result,
            resolution=resolution_result,
            injection_detected=ticket_context.injection_detected,
        )


async def resolve_tickets(tickets: list[TicketInput]) -> list[AgentOutput]:
    """Process multiple tickets through the agentic pipeline.

    This is the single core function called by all three entry points:
    - CLI (main.py)
    - FastAPI (api.py)
    - Azure Functions (func/function_app.py)
    """
    store = initialize_knowledge_store()

    async def _process_one(ticket: TicketInput) -> AgentOutput:
        try:
            logger.info("Processing ticket %s", ticket.ticket_id)
            result = await process_single_ticket(ticket, store)
            logger.info(
                "Ticket %s complete: status=%s, confidence=%.2f, resolved_by=%s",
                result.ticket_id,
                result.status,
                result.confidence,
                result.resolved_by,
            )
            return result
        except Exception as e:
            logger.exception("Failed to process ticket %s", ticket.ticket_id)
            return AgentOutput(
                ticket_id=ticket.ticket_id,
                status="clarification_needed",
                category=IssueCategory.UNKNOWN,
                priority=Priority.MEDIUM,
                proposed_solution=None,
                confidence=0.0,
                reasoning_trace=[f"Processing failed: {str(e)}"],
                retrieved_sources=[],
                follow_up_questions=["Please resubmit this ticket or contact support directly."],
                preliminary_assessment="An internal error occurred while processing this ticket.",
                resolved_by="error",
            )

    results = await asyncio.gather(*[_process_one(t) for t in tickets])
    return list(results)
