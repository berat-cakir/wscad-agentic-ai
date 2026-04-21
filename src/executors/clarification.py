"""Clarification Executor — produces clarification-needed outputs.

Used when:
1. Triage detects critically insufficient information (early clarification)
2. Resolution confidence is below threshold (post-resolution clarification)

No LLM call. Fully deterministic.
"""

from __future__ import annotations

import logging

from src.models.output import AgentOutput
from src.models.resolution import ResolutionResult
from src.models.retrieval import RetrievalResult
from src.models.triage import TriageResult
from src.security.output_validator import clamp_confidence

logger = logging.getLogger(__name__)


def format_early_clarification(triage: TriageResult) -> AgentOutput:
    """Build a clarification output when triage determines info is critically insufficient."""
    follow_ups = _generate_triage_follow_ups(triage)

    return AgentOutput(
        ticket_id=triage.ticket_id,
        status="clarification_needed",
        category=triage.category,
        priority=triage.priority,
        proposed_solution=None,
        confidence=0.1,
        reasoning_trace=[
            f"Classified as '{triage.category.value}': {triage.category_reasoning}",
            f"Information insufficient: missing {triage.missing_fields}",
            "Routing to early clarification — resolution not attempted",
        ],
        retrieved_sources=[],
        follow_up_questions=follow_ups,
        preliminary_assessment=(
            f"The ticket appears to be a {triage.category.value} issue, "
            f"but critical information is missing: {', '.join(triage.missing_fields)}. "
            f"Please provide the requested details so we can investigate further."
        ),
        resolved_by="clarification",
    )


def format_post_resolution_clarification(
    triage: TriageResult,
    retrieval: RetrievalResult,
    resolution: ResolutionResult,
    injection_detected: bool = False,
) -> AgentOutput:
    """Build a clarification output when resolution confidence is too low."""
    confidence = clamp_confidence(resolution.raw_confidence)

    return AgentOutput(
        ticket_id=triage.ticket_id,
        status="clarification_needed",
        category=triage.category,
        priority=triage.priority,
        proposed_solution=None,
        confidence=round(confidence, 2),
        reasoning_trace=resolution.reasoning_trace,
        retrieved_sources=[c.source for c in retrieval.chunks],
        follow_up_questions=resolution.follow_up_questions,
        preliminary_assessment=resolution.proposed_solution,
        resolved_by="clarification",
    )


def _generate_triage_follow_ups(triage: TriageResult) -> list[str]:
    """Generate specific follow-up questions from missing fields."""
    field_to_question = {
        "os_version": "Which operating system and version is WSCAD Suite installed on?",
        "product_version": "Which version of WSCAD Suite is installed?",
        "error_code": "Does the issue produce any error code or error message?",
        "error_message": "Does the application display any error message or log output?",
        "license_type": "Is the system using an online or offline license?",
        "steps_to_reproduce": "What steps lead to this issue? Please describe what you were doing when it occurred.",
        "dotnet_version": "Is .NET Runtime 6.0 or newer installed on the system?",
        "setting_name": "Which specific setting or configuration option is affected?",
        "expected_behavior": "What behavior did you expect versus what actually happened?",
    }

    questions = []
    for field in triage.missing_fields:
        question = field_to_question.get(field)
        if question:
            questions.append(question)
        else:
            questions.append(f"Please provide details about: {field}")

    if not questions:
        questions.append("Could you provide more details about the issue you are experiencing?")

    return questions
