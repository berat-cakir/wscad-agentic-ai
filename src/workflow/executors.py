"""AF Workflow Executor wrappers.

Wraps our business logic functions as Microsoft Agent Framework @executor nodes.
Each executor receives typed messages via WorkflowContext and forwards results
to the next node in the graph.

This separation keeps business logic (src/executors/) framework-agnostic and testable,
while this module handles the AF workflow integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_framework import Executor, WorkflowContext, handler

from src.config import settings
from src.executors.clarification import format_early_clarification, format_post_resolution_clarification
from src.executors.intake import process_ticket
from src.executors.output import format_resolved_output
from src.executors.resolution import resolve_ticket
from src.executors.retrieval import retrieve_context
from src.executors.rule_engine import try_rule_resolution
from src.executors.triage import triage_ticket
from src.knowledge.store import KnowledgeStore
from src.models.output import AgentOutput
from src.models.resolution import ResolutionResult
from src.models.retrieval import RetrievalResult
from src.models.ticket import TicketContext, TicketInput
from src.models.triage import TriageResult


@dataclass
class TicketState:
    """Accumulated state for a ticket moving through the workflow."""

    ticket: TicketContext
    triage: TriageResult | None = None
    retrieval: RetrievalResult | None = None
    resolution: ResolutionResult | None = None

    def require_triage(self) -> TriageResult:
        """Return triage result or raise if not yet set."""
        if self.triage is None:
            raise RuntimeError(f"Triage not completed for ticket {self.ticket.ticket_id}")
        return self.triage

    def require_retrieval(self) -> RetrievalResult:
        """Return retrieval result or raise if not yet set."""
        if self.retrieval is None:
            raise RuntimeError(f"Retrieval not completed for ticket {self.ticket.ticket_id}")
        return self.retrieval


class IntakeNode(Executor):
    """Parses and sanitizes raw ticket input. Security boundary."""

    def __init__(self) -> None:
        super().__init__(id="intake")

    @handler
    async def handle(self, ticket_input: TicketInput, ctx: WorkflowContext[Any]) -> None:
        ticket_context = process_ticket(ticket_input)
        state = TicketState(ticket=ticket_context)
        await ctx.send_message(state)


class TriageNode(Executor):
    """LLM-powered classification. Decides if info is sufficient."""

    def __init__(self) -> None:
        super().__init__(id="triage")

    @handler
    async def handle(self, state: TicketState, ctx: WorkflowContext[Any, AgentOutput]) -> None:
        triage_result = await triage_ticket(state.ticket)
        state.triage = triage_result

        if not triage_result.info_sufficient and triage_result.category.value == "unknown":
            output = format_early_clarification(triage_result)
            await ctx.yield_output(output)
        else:
            await ctx.send_message(state)


class RetrievalNode(Executor):
    """Deterministic RAG retrieval from vector store."""

    def __init__(self, store: KnowledgeStore) -> None:
        super().__init__(id="retrieval")
        self._store = store

    @handler
    async def handle(self, state: TicketState, ctx: WorkflowContext[Any]) -> None:
        triage = state.require_triage()
        retrieval_result = retrieve_context(state.ticket, triage, self._store)
        state.retrieval = retrieval_result
        await ctx.send_message(state)


class RuleEngineNode(Executor):
    """Deterministic fast path. Routes to output if rule matches, else forwards to LLM."""

    def __init__(self) -> None:
        super().__init__(id="rule_engine")

    @handler
    async def handle(self, state: TicketState, ctx: WorkflowContext[Any, AgentOutput]) -> None:
        triage = state.require_triage()
        retrieval = state.require_retrieval()
        rule_result = try_rule_resolution(state.ticket, triage, retrieval)

        if rule_result is not None:
            state.resolution = rule_result
            output = format_resolved_output(
                triage=triage,
                retrieval=retrieval,
                resolution=rule_result,
                injection_detected=state.ticket.injection_detected,
            )
            await ctx.yield_output(output)
        else:
            await ctx.send_message(state)


class ResolutionNode(Executor):
    """LLM-powered reasoning with retrieved context. Only reached for ambiguous cases."""

    def __init__(self) -> None:
        super().__init__(id="resolution")

    @handler
    async def handle(self, state: TicketState, ctx: WorkflowContext[Any, AgentOutput]) -> None:
        triage = state.require_triage()
        retrieval = state.require_retrieval()
        resolution_result = await resolve_ticket(state.ticket, triage, retrieval)
        state.resolution = resolution_result

        calibrated_confidence = _estimate_calibrated_confidence(resolution_result, retrieval)

        if calibrated_confidence >= settings.confidence_threshold:
            output = format_resolved_output(
                triage=triage,
                retrieval=retrieval,
                resolution=resolution_result,
                injection_detected=state.ticket.injection_detected,
            )
        else:
            output = format_post_resolution_clarification(
                triage=triage,
                retrieval=retrieval,
                resolution=resolution_result,
                injection_detected=state.ticket.injection_detected,
            )

        await ctx.yield_output(output)


def _estimate_calibrated_confidence(resolution: ResolutionResult, retrieval: RetrievalResult) -> float:
    """Quick pre-check of calibrated confidence to decide routing.

    Uses a weighted blend (60% LLM confidence, 40% retrieval evidence)
    instead of a product, which is too aggressive with small knowledge bases
    where retrieval scores are naturally moderate.
    """
    raw = resolution.raw_confidence
    retrieval_factor = retrieval.max_similarity if retrieval.max_similarity > 0 else 0.3
    return 0.6 * raw + 0.4 * retrieval_factor
