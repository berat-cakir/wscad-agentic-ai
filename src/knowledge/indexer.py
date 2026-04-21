"""Knowledge base loader and indexer.

Reads markdown/text files from the KB directory, embeds them,
and stores them in the vector store. Runs once at startup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".markdown"}


@dataclass
class KBDocument:
    """A single knowledge base document ready for embedding."""

    filename: str
    content: str
    doc_id: str


def load_documents(kb_path: Path | None = None) -> list[KBDocument]:
    """Load all supported documents from the knowledge base directory.

    Documents are treated as single chunks (document-level chunking)
    because the KB files are short (1-3 sentences each).
    """
    path = kb_path or settings.knowledge_base_path

    if not path.exists():
        logger.warning("Knowledge base path does not exist: %s", path)
        return []

    documents = []
    for file_path in sorted(path.iterdir()):
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not file_path.is_file():
            continue

        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            logger.warning("Skipping empty KB file: %s", file_path.name)
            continue

        doc = KBDocument(
            filename=file_path.name,
            content=content,
            doc_id=file_path.stem,
        )
        documents.append(doc)
        logger.info("Loaded KB document: %s (%d chars)", doc.filename, len(doc.content))

    logger.info("Loaded %d KB documents total", len(documents))
    return documents
