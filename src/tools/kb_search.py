"""Knowledge base search tool for the Resolution Agent.

Uses Microsoft Agent Framework's @tool decorator so the LLM
can autonomously decide to perform additional retrieval during reasoning.
The decorator auto-generates the JSON schema from type annotations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from agent_framework import tool
from pydantic import Field

if TYPE_CHECKING:
    from src.knowledge.store import KnowledgeStore

_store_ref: KnowledgeStore | None = None


def set_store(store: KnowledgeStore) -> None:
    """Inject the KnowledgeStore instance at startup. Called once during initialization."""
    global _store_ref
    _store_ref = store


@tool(
    name="search_knowledge_base",
    description="Search the WSCAD knowledge base for relevant support articles and troubleshooting information.",
)
def search_knowledge_base(
    query: Annotated[str, Field(description="The search query to find relevant KB articles")],
    top_k: Annotated[int, Field(description="Number of results to return", ge=1, le=5)] = 3,
) -> str:
    """Search the WSCAD knowledge base for articles relevant to the query.

    Returns formatted search results with source filenames and similarity scores.
    Use this when the provided context is insufficient and you need additional information.
    """
    if _store_ref is None:
        return "Error: Knowledge store not initialized."

    chunks = _store_ref.search(query, top_k=top_k)

    if not chunks:
        return "No relevant articles found in the knowledge base for this query."

    results = []
    for chunk in chunks:
        results.append(
            f"[Source: {chunk.source} | Similarity: {chunk.similarity_score:.2f}]\n{chunk.content}"
        )
    return "\n\n---\n\n".join(results)
