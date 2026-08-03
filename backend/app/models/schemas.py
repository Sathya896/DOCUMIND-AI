"""
Pydantic schemas (a.k.a. "DTOs" - Data Transfer Objects).

WHY SEPARATE SCHEMAS FROM ORM MODELS?
------------------------------------------
`app/models/document.py` and `app/models/chat.py` define *database* tables
(SQLAlchemy). The classes below define the *API's* request and response
shapes (Pydantic). These are deliberately different layers:

* We never want to accidentally expose an internal column (e.g. the raw
  `stored_path` on disk) to API clients.
* Request bodies often need fields that don't map 1:1 to a table (e.g. a
  question string has no corresponding column).
* Pydantic validates incoming data (types, required fields, string length)
  *before* it reaches business logic, which is exactly what FastAPI uses
  these classes for automatically.

FastAPI also uses these classes to auto-generate the interactive OpenAPI
docs at `/docs` - so writing a good docstring/description here doubles as
API documentation "for free".
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """Metadata about a single uploaded document, returned to the client."""

    id: int
    filename: str
    status: str
    page_count: int
    chunk_count: int
    file_size_bytes: int
    uploaded_at: datetime

    # Enables creating this schema directly from an ORM object, e.g.
    # `DocumentResponse.model_validate(document_orm_instance)`.
    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response returned immediately after a successful upload + indexing."""

    document: DocumentResponse
    message: str = "Document uploaded and indexed successfully."


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


# ---------------------------------------------------------------------------
# Chat / RAG
# ---------------------------------------------------------------------------


class SourceChunk(BaseModel):
    """One retrieved chunk that was used as evidence for an answer."""

    document_id: int
    document_name: str
    page_number: int | None
    snippet: str = Field(..., description="The chunk text shown to the user as evidence.")
    relevance_score: float = Field(
        ..., description="Similarity score (higher = more relevant)."
    )


class AskRequest(BaseModel):
    """Payload for POST /chat/ask - a user's natural-language question."""

    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: int | None = Field(
        default=None, description="Omit to start a new conversation."
    )
    document_ids: list[int] | None = Field(
        default=None,
        description="Restrict retrieval to these document IDs. Omit to search all documents.",
    )


class AskResponse(BaseModel):
    """The grounded answer returned to the client, with supporting sources."""

    conversation_id: int
    answer: str
    sources: list[SourceChunk]


class MessageResponse(BaseModel):
    role: str
    content: str
    sources: list[SourceChunk] = []
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: list[MessageResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Consistent error shape returned by every failure response."""

    error: str
    detail: str
