"""
Custom exception hierarchy.

WHY CUSTOM EXCEPTIONS INSTEAD OF `HTTPException` EVERYWHERE?
---------------------------------------------------------------
It is tempting to `raise HTTPException(status_code=400, detail="...")`
directly inside a service function. The problem: services then depend on
FastAPI (a *web* concern) even though services should be pure business
logic that could, in theory, be reused by a CLI tool or a background job.

Instead, services raise small, descriptive, framework-agnostic exceptions
defined here. FastAPI's exception handlers (registered in `main.py`) catch
these and translate them into proper HTTP responses. This keeps the layers
cleanly separated:

    routes/      -> HTTP concerns (status codes, request/response models)
    services/    -> business logic, raises DocuMindError subclasses
    utils/       -> shared exception + validation helpers

This mirrors how production backends are structured and is a common talking
point in interviews about "separation of concerns".
"""


class DocuMindError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidFileError(DocuMindError):
    """Raised when an uploaded file fails validation (wrong type, too big, empty)."""


class DocumentNotFoundError(DocuMindError):
    """Raised when a requested document ID does not exist."""


class TextExtractionError(DocuMindError):
    """Raised when text cannot be extracted from a PDF (corrupted/encrypted file)."""


class EmbeddingGenerationError(DocuMindError):
    """Raised when the embedding model fails to encode text."""


class VectorStoreError(DocuMindError):
    """Raised when the FAISS index cannot be read, written, or searched."""


class LLMGenerationError(DocuMindError):
    """Raised when the LLM (Ollama) fails to generate a response."""


class NoRelevantContextError(DocuMindError):
    """Raised when semantic search finds no chunks to answer a question with."""
