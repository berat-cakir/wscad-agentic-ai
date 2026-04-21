from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IssueCategory(StrEnum):
    LICENSING = "licensing"
    INSTALLATION = "installation"
    RUNTIME_ERROR = "runtime_error"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TriageResult(BaseModel):
    """Output of the Triage Agent: classification, priority, and information completeness assessment."""

    ticket_id: str
    category: IssueCategory
    priority: Priority

    info_sufficient: bool = Field(description="Whether enough information exists to attempt resolution")
    missing_fields: list[str] = Field(default_factory=list, description="Critical fields missing for resolution")

    category_reasoning: str = Field(description="Brief explanation of why this category was chosen")
    priority_reasoning: str = Field(description="Brief explanation of why this priority was assigned")
