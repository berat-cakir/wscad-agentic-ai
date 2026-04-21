"""CLI entry point — run the agentic pipeline on ticket files and print Rich-formatted results.

Usage:
    python -m src.main                           # Process provided tickets
    python -m src.main --extra                   # Include extra edge-case tickets
    python -m src.main --file tickets/custom.json # Process a custom ticket file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import settings
from src.models.output import AgentOutput
from src.models.ticket import TicketInput
from src.workflow.graph import resolve_tickets

load_dotenv()

console = Console()
logger = logging.getLogger("src")


def load_tickets(path: Path) -> list[TicketInput]:
    """Load tickets from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [TicketInput(**t) for t in raw]


def print_result(result: AgentOutput) -> None:
    """Print a single ticket result as a Rich panel."""
    status_color = "green" if result.status == "resolved" else "yellow"
    confidence_color = "green" if result.confidence >= 0.7 else "yellow" if result.confidence >= 0.4 else "red"
    resolver_map = {"rule_engine": "Rule Engine", "llm": "LLM Agent"}
    resolver_label = resolver_map.get(result.resolved_by, result.resolved_by.title())

    header = Table(show_header=False, box=None, padding=(0, 2))
    header.add_column(style="bold")
    header.add_column()
    header.add_row("Status", f"[{status_color}]{result.status}[/{status_color}]")
    header.add_row("Category", f"[cyan]{result.category.value}[/cyan]")
    header.add_row("Priority", f"[magenta]{result.priority.value}[/magenta]")
    header.add_row("Confidence", f"[{confidence_color}]{result.confidence:.2f}[/{confidence_color}]")
    header.add_row("Resolved By", f"[blue]{resolver_label}[/blue]")
    if result.retrieved_sources:
        header.add_row("Sources", ", ".join(result.retrieved_sources))

    content_parts: list[RenderableType] = [header]

    if result.proposed_solution:
        content_parts.append(Text())
        content_parts.append(Text("Proposed Solution:", style="bold underline"))
        content_parts.append(Text(result.proposed_solution))

    if result.preliminary_assessment:
        content_parts.append(Text())
        content_parts.append(Text("Preliminary Assessment:", style="bold underline"))
        content_parts.append(Text(result.preliminary_assessment))

    if result.reasoning_trace:
        content_parts.append(Text())
        content_parts.append(Text("Reasoning Trace:", style="bold underline"))
        for i, step in enumerate(result.reasoning_trace, 1):
            content_parts.append(Text(f"  {i}. {step}", style="dim"))

    if result.follow_up_questions:
        content_parts.append(Text())
        content_parts.append(Text("Follow-up Questions:", style="bold underline"))
        for q in result.follow_up_questions:
            content_parts.append(Text(f"  - {q}", style="italic"))

    group = "\n".join(str(part) for part in content_parts)

    console.print(Panel(
        group,
        title=f"[bold white]Ticket {result.ticket_id}[/bold white]",
        border_style=status_color,
        box=box.ROUNDED,
        padding=(1, 2),
    ))


def print_summary(results: list[AgentOutput], elapsed_ms: int) -> None:
    """Print a summary table of all results."""
    table = Table(title="Results Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Ticket", style="bold")
    table.add_column("Status")
    table.add_column("Category")
    table.add_column("Priority")
    table.add_column("Confidence", justify="right")
    table.add_column("Resolved By")

    for r in results:
        status_color = "green" if r.status == "resolved" else "yellow"
        conf_color = "green" if r.confidence >= 0.7 else "yellow" if r.confidence >= 0.4 else "red"
        table.add_row(
            r.ticket_id,
            f"[{status_color}]{r.status}[/{status_color}]",
            r.category.value,
            r.priority.value,
            f"[{conf_color}]{r.confidence:.2f}[/{conf_color}]",
            r.resolved_by,
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Processed {len(results)} tickets in {elapsed_ms}ms[/dim]")


async def run(args: argparse.Namespace) -> None:
    """Main async entrypoint."""
    tickets = []

    if args.file:
        tickets = load_tickets(Path(args.file))
    else:
        tickets = load_tickets(settings.tickets_path)
        if args.extra and settings.extra_tickets_path.exists():
            tickets.extend(load_tickets(settings.extra_tickets_path))

    console.print(f"\n[bold]WSCAD Agentic AI — Processing {len(tickets)} tickets[/bold]\n")

    start = time.perf_counter()
    results = await resolve_tickets(tickets)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    for result in results:
        print_result(result)
        console.print()

    print_summary(results, elapsed_ms)

    if args.json:
        output = [r.model_dump(mode="json") for r in results]
        json_path = Path(args.json)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
        console.print(f"\n[dim]JSON output saved to {json_path}[/dim]")

    if args.evaluate:
        from src.evaluation.evaluator import evaluate_all, load_expected_results, print_report

        expected_path = Path("tickets/expected_results.json")
        if expected_path.exists():
            expected = load_expected_results(expected_path)
            report = evaluate_all(results, expected)
            console.print()
            print_report(report)
        else:
            console.print("[yellow]No expected_results.json found — skipping evaluation[/yellow]")


def main() -> None:
    parser = argparse.ArgumentParser(description="WSCAD Agentic AI — Support Ticket Resolution")
    parser.add_argument("--extra", action="store_true", help="Include extra edge-case tickets")
    parser.add_argument("--file", type=str, help="Path to a custom tickets JSON file")
    parser.add_argument("--json", type=str, help="Save results as JSON to this path")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation against expected results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not settings.openai_api_key:
        console.print("[red]Error: OPENAI_API_KEY not set. Copy .env.example to .env and add your key.[/red]")
        sys.exit(1)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
