# WSCAD Agentic AI — Support Ticket Resolution

An agentic AI system that processes technical support tickets through a multi-agent workflow with RAG-based knowledge retrieval, deterministic rule resolution, and LLM-powered reasoning.

Built on **Microsoft Agent Framework 1.0** — the unified successor to Semantic Kernel and AutoGen.

## Quick Start

### Prerequisites

- Python 3.11 or later
- An OpenAI API key or Azure OpenAI deployment

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/berat-cakir/wscad-agentic-ai.git
cd wscad-agentic-ai

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install .

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY (or Azure OpenAI credentials)
```

### Run

```bash
# Process the provided tickets
python -m src.main

# Include additional edge-case tickets
python -m src.main --extra

# Run with evaluation scoring against expected results
python -m src.main --extra --evaluate

# Save results as JSON
python -m src.main --extra --json results.json
```

### API Mode

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/docs for interactive Swagger UI
```

### Azure Functions

```bash
cp local.settings.json.example local.settings.json
# Edit local.settings.json and set your credentials
func start
```

## Architecture

```
                          ┌──────────────────┐
            Ticket JSON → │  Intake Executor  │  parse + sanitize + injection detection
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  Triage Agent    │  LLM: classify + prioritize + detect gaps
                          │  [AF Agent]      │
                          └────────┬─────────┘
                                   │
                      ┌────────────┴──────────────┐
                      │ info sufficient?           │
                 YES  │                       NO   │
                      ▼                            ▼
            ┌──────────────────┐        ┌──────────────────┐
            │ Retrieval        │        │ Early            │
            │ Executor         │        │ Clarification    │ → output
            │ (RAG: ChromaDB)  │        └──────────────────┘
            └────────┬─────────┘
                     │
            ┌────────┴──────────────┐
            │ rule match + high     │
            │ retrieval similarity? │
        YES │                  NO   │
            ▼                       ▼
   ┌──────────────┐     ┌──────────────────┐
   │ Rule Engine  │     │ Resolution Agent │
   │ (deterministic,    │ [AF Agent +      │
   │  conf=0.95)  │     │  @tool search]   │
   └──────┬───────┘     └────────┬─────────┘
          │                      │
          │            ┌─────────┴────────┐
          │            │ confidence ≥ 0.5?│
          │       YES  │             NO   │
          │            ▼                  ▼
          │     ┌────────────┐  ┌──────────────┐
          └────►│ Output     │  │ Clarification│
                │ Executor   │  │ Executor     │ → output
                └────────────┘  └──────────────┘
```

**7 executors, 3 conditional decision points, 2 LLM agents.** The Rule Engine handles known patterns deterministically (zero LLM cost, sub-second). The LLM handles only what rules cannot.

## Project Structure

```
├── agents/                     # Declarative YAML agent definitions
│   ├── triage_agent.yaml       #   Classification instructions
│   └── resolution_agent.yaml   #   Reasoning + grounding rules
├── src/
│   ├── main.py                 # CLI entry point (Rich output)
│   ├── api.py                  # FastAPI entry point (Swagger at /docs)
│   ├── config.py               # Centralized settings (pydantic-settings)
│   ├── llm_client.py           # LLM client factory (OpenAI / Azure OpenAI)
│   ├── models/                 # Pydantic data contracts
│   ├── executors/              # All pipeline nodes (5 deterministic + 2 LLM)
│   ├── security/               # Sanitizer, injection detector, output validator
│   ├── rules/                  # Deterministic known-pattern rules
│   ├── tools/                  # AF @tool-decorated functions
│   ├── knowledge/              # KB loader + ChromaDB vector store
│   ├── workflow/               # AF Executor wrappers + graph assembly
│   └── evaluation/             # Scoring harness
├── function_app.py             # Azure Functions entry point
├── host.json                   # Azure Functions host configuration
├── knowledge_base/             # Provided KB documents
├── tickets/                    # Provided + extra test tickets
├── tests/                      # Unit + integration tests
├── DESIGN.md                   # Architecture decisions + trade-offs
└── pyproject.toml              # Dependencies + tooling config
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Microsoft Agent Framework 1.0** | Unified successor to SK + AutoGen. Maps 1:1 to C#/.NET for production integration. |
| **Hybrid rule engine + LLM** | Known patterns (Error 504 → licensing) resolve deterministically. LLM handles ambiguity. Same pattern as engineering constraints. |
| **YAML agent definitions** | Instructions are version-controlled, reviewable in PRs, separate from code. No prompt drift. |
| **Security boundary at intake** | Input sanitization, prompt injection detection, output validation. Non-negotiable for production. |
| **ChromaDB locally** | Zero-setup for reviewers. Azure AI Search documented as production target (see [DESIGN.md](DESIGN.md)). |
| **Three entry points, one core** | CLI for demo, FastAPI for Swagger, Azure Functions for deployment. All call `resolve_tickets()`. |
| **Weighted confidence** | Not a single LLM number. Blended from LLM self-assessment (60%) and retrieval evidence strength (40%). Halved for unknown-category tickets. |

## Running Tests

```bash
# Unit tests (no API key required)
pytest tests/ -m "not integration"

# Integration tests (requires OPENAI_API_KEY in .env)
pytest tests/ -m integration

# Lint
ruff check src/ tests/ function_app.py
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/tickets/resolve` | POST | Process support tickets |
| `/api/v1/health` | GET | Health check |
| `/api/v1/knowledge/status` | GET | KB index metadata |
| `/docs` | GET | Swagger UI |

## Technology Stack

- **Orchestration**: Microsoft Agent Framework 1.0 (Python)
- **LLM**: Azure OpenAI / OpenAI — `gpt-5-mini` recommended (sufficient for ticket triage and resolution, significantly faster than full-size models)
- **Vector Store**: ChromaDB (swappable to Azure AI Search)
- **API**: FastAPI + uvicorn / Azure Functions
- **Structured Output**: Pydantic v2
- **Observability**: OpenTelemetry (AF built-in) + Python logging + Rich

See [DESIGN.md](DESIGN.md) for architecture decisions, trade-offs, and the production scaling path.
