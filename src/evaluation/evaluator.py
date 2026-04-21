"""Evaluation harness — compares agent outputs against expected results.

Simple scoring to demonstrate evaluation thinking.
Not a benchmark — production evaluation would use LLM-as-judge
and human review in addition to automated metrics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.models.output import AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class ExpectedResult:
    ticket_id: str
    expected_category: str
    expected_priority: str
    expected_status: str
    expected_sources: list[str] = field(default_factory=list)


@dataclass
class TicketScore:
    ticket_id: str
    category_match: bool
    priority_match: bool
    status_match: bool
    source_recall: float
    has_reasoning: bool
    confidence_calibrated: bool


@dataclass
class EvaluationReport:
    scores: list[TicketScore]
    total_tickets: int
    category_accuracy: float
    priority_accuracy: float
    status_accuracy: float
    avg_source_recall: float
    reasoning_coverage: float


def load_expected_results(path: Path) -> list[ExpectedResult]:
    """Load expected results from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [ExpectedResult(**r) for r in raw]


def evaluate_ticket(output: AgentOutput, expected: ExpectedResult) -> TicketScore:
    """Score a single ticket output against expected results."""
    expected_source_set = set(expected.expected_sources)
    actual_source_set = set(output.retrieved_sources)

    if expected_source_set:
        source_recall = len(actual_source_set & expected_source_set) / len(expected_source_set)
    else:
        source_recall = 1.0 if not actual_source_set else 0.0

    return TicketScore(
        ticket_id=output.ticket_id,
        category_match=output.category.value == expected.expected_category,
        priority_match=output.priority.value == expected.expected_priority,
        status_match=output.status == expected.expected_status,
        source_recall=round(source_recall, 2),
        has_reasoning=len(output.reasoning_trace) > 0,
        confidence_calibrated=0.0 <= output.confidence <= 1.0,
    )


def evaluate_all(outputs: list[AgentOutput], expected: list[ExpectedResult]) -> EvaluationReport:
    """Evaluate all outputs against expected results and produce a report."""
    expected_map = {e.ticket_id: e for e in expected}
    scores = []

    for output in outputs:
        exp = expected_map.get(output.ticket_id)
        if exp is None:
            logger.warning("No expected result for ticket %s — skipping evaluation", output.ticket_id)
            continue
        scores.append(evaluate_ticket(output, exp))

    n = len(scores) or 1

    return EvaluationReport(
        scores=scores,
        total_tickets=len(scores),
        category_accuracy=sum(s.category_match for s in scores) / n,
        priority_accuracy=sum(s.priority_match for s in scores) / n,
        status_accuracy=sum(s.status_match for s in scores) / n,
        avg_source_recall=sum(s.source_recall for s in scores) / n,
        reasoning_coverage=sum(s.has_reasoning for s in scores) / n,
    )


def print_report(report: EvaluationReport) -> None:
    """Print evaluation report to console using Rich."""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()

    detail_table = Table(title="Per-Ticket Evaluation", box=box.SIMPLE_HEAVY)
    detail_table.add_column("Ticket", style="bold")
    detail_table.add_column("Category")
    detail_table.add_column("Priority")
    detail_table.add_column("Status")
    detail_table.add_column("Source Recall", justify="right")
    detail_table.add_column("Reasoning")

    for s in report.scores:
        detail_table.add_row(
            s.ticket_id,
            "[green]PASS[/green]" if s.category_match else "[red]FAIL[/red]",
            "[green]PASS[/green]" if s.priority_match else "[red]FAIL[/red]",
            "[green]PASS[/green]" if s.status_match else "[red]FAIL[/red]",
            f"{s.source_recall:.0%}",
            "[green]YES[/green]" if s.has_reasoning else "[red]NO[/red]",
        )

    console.print(detail_table)

    summary = Table(title="Aggregate Metrics", box=box.SIMPLE_HEAVY)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")
    summary.add_row("Total Tickets", str(report.total_tickets))
    summary.add_row("Category Accuracy", f"{report.category_accuracy:.0%}")
    summary.add_row("Priority Accuracy", f"{report.priority_accuracy:.0%}")
    summary.add_row("Status Accuracy", f"{report.status_accuracy:.0%}")
    summary.add_row("Avg Source Recall", f"{report.avg_source_recall:.0%}")
    summary.add_row("Reasoning Coverage", f"{report.reasoning_coverage:.0%}")

    console.print()
    console.print(summary)
