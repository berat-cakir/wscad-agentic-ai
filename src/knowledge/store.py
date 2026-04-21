"""Vector store abstraction backed by ChromaDB.

Handles embedding generation via OpenAI and similarity search.
Designed to be swappable — in production, replace with Azure AI Search
using Semantic Kernel's AzureAISearchCollection bridge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import chromadb
import openai
from chromadb.api import ClientAPI as ChromaClientAPI

from src.config import settings
from src.knowledge.indexer import KBDocument
from src.llm_client import create_openai_client
from src.models.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeStore:
    """ChromaDB-backed vector store for KB document retrieval."""

    _client: ChromaClientAPI
    _collection: chromadb.Collection
    _openai_client: openai.OpenAI
    _indexed_count: int = 0

    @classmethod
    def create(cls) -> KnowledgeStore:
        """Initialize an empty in-memory ChromaDB store."""
        client = chromadb.Client()
        collection = client.get_or_create_collection(
            name=settings.chromadb_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        openai_client = create_openai_client()
        return cls(_client=client, _collection=collection, _openai_client=openai_client)

    def index_documents(self, documents: list[KBDocument]) -> int:
        """Embed and store documents in the vector store. Returns count indexed."""
        if not documents:
            return 0

        texts = [doc.content for doc in documents]
        embeddings = self._embed_texts(texts)

        self._collection.add(
            ids=[doc.doc_id for doc in documents],
            documents=texts,
            embeddings=embeddings,  # type: ignore[arg-type]
            metadatas=[{"filename": doc.filename} for doc in documents],
        )

        self._indexed_count = len(documents)
        logger.info("Indexed %d documents into ChromaDB", self._indexed_count)
        return self._indexed_count

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Search for relevant documents by semantic similarity.

        Returns RetrievedChunk objects sorted by similarity (descending),
        filtered by the configured similarity threshold.
        """
        top_k = top_k or settings.retrieval_top_k

        if self._indexed_count == 0:
            logger.warning("Search called on empty index")
            return []

        query_embedding = self._embed_texts([query])[0]

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._indexed_count),
            include=["documents", "metadatas", "distances"],
        )

        distances = results["distances"]
        documents = results["documents"]
        metadatas = results["metadatas"]
        if distances is None or documents is None or metadatas is None:
            logger.warning("ChromaDB returned None for distances/documents/metadatas")
            return []

        chunks = []
        for i in range(len(results["ids"][0])):
            distance = distances[0][i]
            similarity = 1.0 - distance

            if similarity < settings.retrieval_similarity_threshold:
                continue

            metadata = metadatas[0][i]
            source = metadata["filename"] if metadata else "unknown"

            chunk = RetrievedChunk(
                source=str(source),
                content=str(documents[0][i]),
                similarity_score=round(similarity, 4),
            )
            chunks.append(chunk)

        chunks.sort(key=lambda c: c.similarity_score, reverse=True)
        logger.info("Search returned %d chunks above threshold (query: %.50s...)", len(chunks), query)
        return chunks

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via OpenAI API."""
        model = (
            settings.azure_openai_embedding_deployment
            if settings.use_azure and settings.azure_openai_embedding_deployment
            else settings.openai_embedding_model
        )
        response = self._openai_client.embeddings.create(
            model=model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @property
    def document_count(self) -> int:
        return self._indexed_count
