"""
ORM models for documents and their chunks.

WHY TWO TABLES (`documents` AND `chunks`) INSTEAD OF ONE?
-------------------------------------------------------------
This follows standard relational database normalisation: a `Document`
(one uploaded PDF) has *many* `Chunk`s (the pieces it was split into for
embedding). Storing them separately avoids repeating document-level data
(filename, upload date, page count) on every single chunk row, and lets us
delete/re-index a document's chunks without touching the document record.

HOW DOES A CHUNK ROW LINK BACK TO ITS VECTOR IN FAISS?
------------------------------------------------------------
FAISS, by default, identifies vectors only by their insertion position
(0, 1, 2, ...) in a flat array - it has no concept of "this vector belongs
to chunk #42". We avoid building a separate position-tracking table by
wrapping the FAISS index in an `IndexIDMap` (see `vector_store_service.py`),
which lets us assign *our own* IDs to vectors when we add them. We simply
reuse each `Chunk` row's primary key (`id`) as its FAISS vector ID. That
means: to go from a FAISS search result back to the source text, we just
look up `Chunk` by `id == <faiss_result_id>` - no extra bridging table, and
IDs remain stable even after other vectors are deleted.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Document(Base):
    """A single uploaded PDF file and its processing status."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    # "pending" -> "processing" -> "indexed" -> "failed"
    # Explicitly modelling status lets the frontend show progress and lets
    # the API reject questions about documents that aren't ready yet.
    status: Mapped[str] = mapped_column(String(32), default="pending")

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # `cascade="all, delete-orphan"` means deleting a Document automatically
    # deletes all of its Chunk rows too - we never want orphaned chunks
    # pointing at a document that no longer exists.
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """A single text chunk extracted from a document, ready for embedding."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
