from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.models.triage import IssueCategory, Priority


class AgentOutput(BaseModel):
    """Final structured output for a single ticket — the deliverable of the agentic pipeline."""

    ticket_id: str
    status: Literal["resolved", "clarification_needed"]

    category: IssueCategory
    priority: Priority

    proposed_solution: str | None = Field(default=None, description="Resolution text; None if clarification_needed")
    confidence: float = Field(ge=0.0, le=1.0, description="Calibrated confidence score")

    reasoning_trace: list[str] = Field(default_factory=list, description="Step-by-step reasoning chain")
    retrieved_sources: list[str] = Field(default_factory=list, description="KB documents cited")
    follow_up_questions: list[str] = Field(default_factory=list, description="Questions for the user")
    preliminary_assessment: str | None = Field(default=None, description="Partial analysis when clarification_needed")

    resolved_by: str = Field(default="llm", description="'rule_engine' or 'llm'")


# --- API Models ---


class TicketRequest(BaseModel):
    """API request body for POST /api/v1/tickets/resolve."""

    tickets: list[dict] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of ticket objects (ticket_id, text, optional metadata)",
    )


class TicketResponse(BaseModel):
    """API response body."""

    results: list[AgentOutput]
    processing_time_ms: int
    model_version: str
    api_version: str = "1.0.0"
