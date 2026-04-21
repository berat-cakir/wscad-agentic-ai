"""FastAPI entry point — REST API with auto-generated OpenAPI/Swagger documentation.

Usage:
    uvicorn src.api:app --host 0.0.0.0 --port 8000
    Then open http://localhost:8000/docs for Swagger UI

Production deployment: Azure Functions adapter (func/function_app.py)
or Azure Container Apps with this FastAPI app directly.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.models.output import TicketRequest, TicketResponse
from src.models.ticket import TicketInput
from src.workflow.graph import initialize_knowledge_store, resolve_tickets

load_dotenv()

logger = logging.getLogger("src")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize knowledge store on startup."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Initializing knowledge store...")
    initialize_knowledge_store()
    logger.info("API ready")
    yield


app = FastAPI(
    title="WSCAD Agentic AI — Support Ticket Resolution",
    description=(
        "Agentic AI system that processes technical support tickets using "
        "Microsoft Agent Framework with RAG, rule-based resolution, and LLM reasoning. "
        "Built for the WSCAD AI Technology Lead coding challenge."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


class HealthResponse(BaseModel):
    status: str
    knowledge_base_documents: int
    model: str
    api_version: str


class KnowledgeStatusResponse(BaseModel):
    document_count: int
    embedding_model: str
    vector_store: str
    collection_name: str


@app.post(
    "/api/v1/tickets/resolve",
    response_model=TicketResponse,
    summary="Resolve support tickets",
    description="Process one or more support tickets through the agentic AI pipeline. "
    "Returns structured results with classification, proposed solutions, confidence scores, "
    "and reasoning traces.",
)
async def resolve(request: TicketRequest) -> TicketResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        tickets = [TicketInput(**t) for t in request.tickets]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ticket format: {e}")

    start = time.perf_counter()
    results = await resolve_tickets(tickets)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return TicketResponse(
        results=results,
        processing_time_ms=elapsed_ms,
        model_version=settings.azure_openai_deployment if settings.use_azure else settings.openai_model,
    )


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verify the API is running, the knowledge base is indexed, and the LLM is configured.",
)
async def health() -> HealthResponse:
    from src.workflow.graph import _knowledge_store

    doc_count = _knowledge_store.document_count if _knowledge_store else 0

    return HealthResponse(
        status="healthy" if doc_count > 0 else "degraded",
        knowledge_base_documents=doc_count,
        model=settings.azure_openai_deployment if settings.use_azure else settings.openai_model,
        api_version="1.0.0",
    )


@app.get(
    "/api/v1/knowledge/status",
    response_model=KnowledgeStatusResponse,
    summary="Knowledge base status",
    description="Return metadata about the indexed knowledge base.",
)
async def knowledge_status() -> KnowledgeStatusResponse:
    from src.workflow.graph import _knowledge_store

    return KnowledgeStatusResponse(
        document_count=_knowledge_store.document_count if _knowledge_store else 0,
        embedding_model=settings.openai_embedding_model,
        vector_store="ChromaDB (in-memory)",
        collection_name=settings.chromadb_collection_name,
    )
