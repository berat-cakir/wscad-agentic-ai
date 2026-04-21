"""LLM client factory — returns the correct client based on configuration.

Supports both OpenAI (direct) and Azure OpenAI via Microsoft Foundry.
Used by Triage Agent, Resolution Agent, and the embedding pipeline.

The AF OpenAIChatClient auto-detects Azure vs OpenAI routing from environment
variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, etc.), so we only
need to pass explicit overrides when the env vars don't cover it.
"""

from __future__ import annotations

import openai
from agent_framework.openai import OpenAIChatClient

from src.config import settings


def create_chat_client() -> OpenAIChatClient:
    """Create a chat client for AF Agent.

    Uses AF's built-in env-var detection:
    - Azure: reads AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_MODEL
    - OpenAI: reads OPENAI_API_KEY, OPENAI_MODEL
    """
    if settings.use_azure:
        return OpenAIChatClient(
            model=settings.azure_openai_deployment,
            api_key=settings.openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
        )
    return OpenAIChatClient(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )


def create_openai_client() -> openai.OpenAI:
    """Create a raw OpenAI client for embeddings."""
    if settings.use_azure:
        return openai.AzureOpenAI(
            api_key=settings.openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    return openai.OpenAI(api_key=settings.openai_api_key)
