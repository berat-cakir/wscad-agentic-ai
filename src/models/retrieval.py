from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A single document chunk retrieved from the knowledge base."""

    source: str = Field(description="Filename of the KB document, e.g. 'Common_Errors.md'")
    content: str = Field(description="Full text content of the chunk")
    similarity_score: float = Field(ge=0.0, le=1.0, description="Cosine similarity to the query")


class RetrievalResult(BaseModel):
    """Output of the Retrieval Executor: ranked KB chunks with relevance metadata."""

    ticket_id: str
    query_used: str = Field(description="The search query sent to the vector store")
    chunks: list[RetrievedChunk] = Field(default_factory=list, description="Retrieved chunks, ranked by similarity")
    retrieval_empty: bool = Field(default=False, description="True if no chunks passed the similarity threshold")
    max_similarity: float = Field(default=0.0, description="Highest similarity score among retrieved chunks")
