"""Azure Functions HTTP trigger adapter.

Thin wrapper that exposes the same resolve_tickets() core logic
as an Azure Function. Deploy via Azure DevOps pipeline or `func azure functionapp publish`.

Local testing: func start
Production: Azure Functions Premium (EP1+) for VNET integration and no cold-start.
"""

import json
import logging
import time

import azure.functions as func  # provided by Azure Functions runtime; install via `pip install azure-functions` for local dev

from src.models.ticket import TicketInput
from src.workflow.graph import resolve_tickets

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="tickets/resolve", methods=["POST"])
async def resolve(req: func.HttpRequest) -> func.HttpResponse:
    start = time.perf_counter()

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400, mimetype="application/json")

    raw_tickets = body.get("tickets", [])
    if not raw_tickets or len(raw_tickets) > 10:
        return func.HttpResponse(
            json.dumps({"error": "Provide 1-10 tickets"}), status_code=400, mimetype="application/json"
        )

    try:
        tickets = [TicketInput(**t) for t in raw_tickets]
        results = await resolve_tickets(tickets)

        response = {
            "results": [r.model_dump() for r in results],
            "processing_time_ms": int((time.perf_counter() - start) * 1000),
            "api_version": "1.0.0",
        }
        return func.HttpResponse(json.dumps(response, default=str), status_code=200, mimetype="application/json")

    except Exception as e:
        logging.exception("Ticket resolution failed")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json")
