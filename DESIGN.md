# Design Document — Architecture Decisions & Trade-offs

## Why Microsoft Agent Framework

Semantic Kernel and AutoGen are in maintenance mode since October 2025. Microsoft Agent Framework 1.0 (GA April 2026) is the unified successor — same team, same concepts, production-grade APIs.

For this project specifically:
- **Workflow API** with `WorkflowBuilder`, typed `Executor` nodes, and conditional `Edges` provides graph-based orchestration — not prompt chaining.
- **`@tool` decorator** auto-generates JSON schemas from type annotations, letting the LLM decide when to call tools autonomously.
- **`Agent` abstraction** with `OpenAIChatClient` provides a clean interface for LLM-powered reasoning.
- **C#/.NET parity** — every Python component maps to a C# equivalent. This prototype can be ported to a .NET codebase without architectural changes.

## Agent Architecture — Why 2 LLM Agents

The system has 7 executors but only 2 use LLMs. Every other step is deterministic.

**Triage Agent**: Classifies free-text into categories. This requires semantic understanding — "nothing works anymore" could be licensing or installation depending on context. No tools (prevents retrieval bias during classification).

**Resolution Agent**: Reasons across retrieved documents and generates grounded solutions. Has `search_knowledge_base` as a `@tool` for autonomous re-retrieval when initial context is insufficient.

**Why not more agents?** Every LLM call adds latency (~1-3s), cost, and non-determinism. Adding a third agent would mean splitting a task that doesn't need splitting. The Rule Engine handles known patterns at zero cost. In production, Triage could be replaced by a fine-tuned classifier (~10ms).

## Hybrid Rule Engine + LLM

**Rule Engine** handles known, deterministic patterns: Error 504 → licensing reactivation. These resolve with confidence 0.95, zero LLM cost, sub-second latency. Rules require both a pattern match AND retrieval confirmation (similarity ≥ 0.75) to prevent stale rules from producing wrong answers.

**LLM** handles everything else — ambiguous symptoms, multi-issue tickets, novel problems.

In an engineering CAD context, this is the natural split: electrical standards and wiring rules are deterministic constraints (Rule Engine); understanding design intent from a schematic description requires an LLM.

## RAG Strategy

**Chunking**: Document-level. The 3 KB files are 1-3 sentences each — sub-document splitting would destroy context. At scale, switch to semantic chunking (split on headers, preserve paragraphs, 50-token overlap).

**Retrieval**: Top-3 by cosine similarity against ChromaDB, filtered at threshold 0.3. Retrieval runs in parallel with triage for lower latency, using ticket text and error codes as the query.

**Hallucination mitigation**: Source-only constraint in system prompt, citation requirement, retrieval evidence weighted into confidence score, empty-retrieval short-circuits to clarification.

**Production path**: Azure AI Search with hybrid retrieval (BM25 keyword + vector + semantic reranking). Critical for exact error code matching combined with fuzzy symptom search. The `KnowledgeStore` abstraction makes this a configuration swap.

## Security

The Intake Executor is the security boundary. All validation runs before any LLM call:

- **Input sanitization**: HTML stripping, length limits, Unicode normalization, null byte removal
- **Prompt injection detection**: 10 regex patterns for known injection vectors. Detected text is wrapped in data boundaries, not rejected (could be legitimate content about injection).
- **Output validation**: Source grounding (filenames must match real KB files), confidence clamping, PII detection and redaction.
- **Cost control**: Max 4 LLM calls per ticket, 30s timeout, circuit breaker after 3 consecutive failures.

Production upgrade: Azure Content Safety API for ML-based injection detection, Microsoft Defender for advanced threat analysis.

## Confidence Calibration

Confidence is not a single LLM-generated number. It is a weighted blend of two signals:

```
confidence = 0.6 × base + 0.4 × retrieval_factor
```

- `base`: Resolution Agent's self-assessed certainty
- `retrieval_factor`: max similarity score from retrieved documents
- Halved for unknown-category tickets (genuine ambiguity)

The weighted blend (60% LLM confidence, 40% retrieval evidence) keeps the two signals balanced. A pure product collapses confidence too aggressively with small knowledge bases where retrieval scores are naturally moderate.

## Declarative YAML Agents

Agent instructions live in `agents/*.yaml`, not in Python code. This means:
- Instructions are version-controlled and reviewable in PRs
- Non-developers (support team leads, domain experts) can review prompt changes
- No prompt drift — changes go through the same review process as code
- Agent configuration is separate from orchestration logic

## Deployment Architecture

Three entry points, one core function:

```
python -m src.main          →  CLI (Rich output, challenge review)
uvicorn src.api:app         →  FastAPI (Swagger UI at /docs)
func start                  →  Azure Functions (production)
            ↓   ↓   ↓
      resolve_tickets()     →  single core, three hosting layers
```

### CI/CD (Azure DevOps)

| Stage | What | Trigger |
|---|---|---|
| Lint | `ruff check src/ tests/ function_app.py` | Every commit |
| Unit Tests | `pytest tests/ -m "not integration"` | Every commit |
| Integration Tests | `pytest tests/ -m integration` | PR to main |
| Build | `pip install .` + validation | PR to main |
| Deploy | Container Registry → Container Apps or Functions | Merge to main |

## Production Scaling Path

| Current (Challenge) | Production (WSCAD) |
|---|---|
| ChromaDB in-memory | Azure AI Search (hybrid retrieval) |
| Azure OpenAI (gpt-5-mini) | Azure OpenAI (managed, VNET-integrated) |
| FastAPI local | Azure Functions Premium or Container Apps |
| stdout logging | Azure Monitor + Application Insights |
| No auth | Azure Entra ID + API key |
| 3 KB documents | Thousands of articles, manuals, release notes |
| Python | C#/.NET port (AF has identical APIs) |

## Engineering Domain Extension

This support ticket system is a proxy for WSCAD's larger vision. The architecture maps directly:

| This Challenge | WSCAD Engineering Platform |
|---|---|
| Ticket text | Engineering task or design intent |
| Knowledge base | Engineering standards (IEC 61346), component databases, wiring rules |
| Triage Agent | Intent recognition from schematic descriptions |
| Rule Engine | Electrical constraints: wire sizing, breaker ratings, safety interlocks |
| RAG retrieval | Component lookup from wscaduniverse.com (1.6M+ parts) |
| Resolution Agent | Design recommendations based on specifications |
| Clarification logic | "Schematic shows 3-phase motor but only 2 phases connected — intentional?" |
| Workflow graph | Engineering workflow: design → validate → verify → approve → output |
