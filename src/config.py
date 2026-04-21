from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_embedding_deployment: str = ""
    azure_openai_api_version: str = "2025-03-01-preview"

    knowledge_base_path: Path = Path("knowledge_base")
    agents_path: Path = Path("agents")
    tickets_path: Path = Path("tickets/tickets.json")
    extra_tickets_path: Path = Path("tickets/extra_tickets.json")

    chromadb_collection_name: str = "wscad_knowledge_base"
    retrieval_top_k: int = 3
    retrieval_similarity_threshold: float = 0.3
    rule_engine_similarity_threshold: float = 0.75
    confidence_threshold: float = 0.5

    max_ticket_text_length: int = 2000
    max_tickets_per_request: int = 10
    max_llm_calls_per_ticket: int = 4
    ticket_timeout_seconds: int = 30

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def use_azure(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_deployment)


settings = Settings()
