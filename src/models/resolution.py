from __future__ import annotations

from pydantic import BaseModel, Field


class ResolutionResult(BaseModel):
    """Output of the Resolution Agent or Rule Engine: proposed solution with reasoning and confidence."""

    ticket_id: str
    proposed_solution: str = Field(description="The proposed resolution or recommendation")
    raw_confidence: float = Field(ge=0.0, le=1.0, description="Confidence from the resolver before calibration")

    reasoning_trace: list[str] = Field(default_factory=list, description="Step-by-step reasoning steps")
    retrieved_sources: list[str] = Field(default_factory=list, description="KB document filenames used")
    follow_up_questions: list[str] = Field(default_factory=list, description="Questions to ask if confidence is low")

    resolved_by: str = Field(default="llm", description="'rule_engine' or 'llm' — which resolver produced this")
