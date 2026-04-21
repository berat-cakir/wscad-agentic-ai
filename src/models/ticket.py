from __future__ import annotations

from pydantic import BaseModel, Field


class TicketMetadata(BaseModel):
    product: str | None = Field(default=None, description="Product name, e.g. 'WSCAD Suite'")
    version: str | None = Field(default=None, description="Product version, e.g. '2.3'")
    os: str | None = Field(default=None, description="Operating system, e.g. 'Windows 11'")
    urgency: str | None = Field(default=None, description="User-reported urgency level")


class TicketInput(BaseModel):
    """Raw ticket as received from the JSON input file."""

    ticket_id: str
    text: str
    metadata: TicketMetadata = Field(default_factory=TicketMetadata)


class TicketContext(BaseModel):
    """Enriched ticket after intake processing: sanitized text, extracted signals, and validation flags."""

    ticket_id: str
    original_text: str = Field(description="Original ticket text (preserved for audit)")
    sanitized_text: str = Field(description="Cleaned text after sanitization")
    metadata: TicketMetadata

    extracted_error_codes: list[str] = Field(default_factory=list, description="Error codes found in text")
    extracted_keywords: list[str] = Field(default_factory=list, description="Domain-relevant keywords detected")

    injection_detected: bool = Field(default=False, description="Whether prompt injection patterns were found")
    validation_warnings: list[str] = Field(default_factory=list, description="Any warnings from input validation")
