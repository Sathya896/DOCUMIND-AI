"""
Orchestrating the full document ingestion pipeline.

WHY DOES THIS SERVICE EXIST SEPARATELY FROM `pdf_service`, `chunking_service`,
ETC.?
------------------------------------------------------------------------------
Each of those services does exactly one job (single responsibility
principle): extract text, split text, embed text, store vectors. None of
them know about the *database*, and none of them know about each other.
`document_service.py` is the orchestrator - it calls each specialised
service in the right order and wires the results together (e.g. "take the
chunk this text came from, embed it, then store both the chunk row *and*
its embedding using the same ID"). Route handlers call *this* module, not
the lower-level services directly, so the ingestion pipeline's sequencing
lives in exactly one place.

This layering (routes -> orchestrating service -> focused services) is a
standard pattern for keeping backends maintainable as they grow: adding a
7th processing step later means changing this one function, not every
route that triggers ingestion.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import Chunk, Document
from app.services import chunking_service, embedding_service, pdf_service
from app.services.vector_store_service import get_vector_store
from app.utils.exceptions import DocumentNotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def ingest_document(db: Session, filename: str, file_bytes: bytes) -> Document:
    """Run the full pipeline for one uploaded file: save -> extract -> chunk
    -> embed -> index -> persist metadata.

    Returns the fully-indexed `Document` row. Raises one of the
    `DocuMindError` subclasses (from the underlying services) if any step
    fails; the caller (the route handler) is responsible for translating
    that into an HTTP error response.
    """
    stored_path = pdf_service.save_pdf_bytes(filename, file_bytes)

    # Create the Document row immediately in "processing" state. This means
    # that even if a later step fails, we have a record of the attempt
    # (useful for debugging, and could power a "failed uploads" view later).
    document = Document(
        filename=filename,
        stored_path=str(stored_path),
        file_size_bytes=len(file_bytes),
        status="processing",
    )
    db.add(document)
    db.flush()  # assigns document.id without committing yet

    try:
        pages_text = pdf_service.extract_text_by_page(stored_path)
        document.page_count = len(pages_text)

        text_chunks = chunking_service.chunk_pages(pages_text)
        _embed_and_store_chunks(db, document, text_chunks)

        document.chunk_count = len(text_chunks)
        document.status = "indexed"
        db.commit()

        get_vector_store().save()
        logger.info(
            "Indexed document '%s' (id=%d) into %d chunks",
            filename,
            document.id,
            len(text_chunks),
        )
        return document

    except Exception:
        # Roll back the DB (removes the Document + any partially-added
        # Chunk rows) and delete the file we saved, so a failed upload
        # leaves no partial state behind. The original exception is
        # re-raised unchanged so the route layer sees the real error.
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise


def _embed_and_store_chunks(
    db: Session, document: Document, text_chunks: list[chunking_service.TextChunk]
) -> None:
    """Persist chunk rows and their embeddings together, keeping IDs in sync.

    We insert each `Chunk` row first (via `flush`, not `commit`) purely to
    obtain its auto-generated primary key, which we then reuse as the
    vector's ID in FAISS - see the docstring in `models/document.py` for why.
    """
    if not text_chunks:
        return

    chunk_rows: list[Chunk] = []
    for index, text_chunk in enumerate(text_chunks):
        chunk_row = Chunk(
            document_id=document.id,
            chunk_index=index,
            page_number=text_chunk.page_number,
            content=text_chunk.content,
        )
        db.add(chunk_row)
        chunk_rows.append(chunk_row)

    db.flush()  # assigns an `id` to every chunk_row above

    embeddings = embedding_service.embed_documents([chunk.content for chunk in chunk_rows])
    chunk_ids = [chunk.id for chunk in chunk_rows]
    get_vector_store().add(ids=chunk_ids, embeddings=embeddings)


def list_documents(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.uploaded_at.desc()).all()


def get_document_or_raise(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document with id={document_id} was not found.")
    return document


def delete_document(db: Session, document_id: int) -> None:
    """Remove a document: its vectors from FAISS, its rows from SQLite, and
    its file from disk.

    The order matters: we remove vectors from FAISS *before* deleting the
    Chunk rows, because we need those rows to know which chunk IDs to
    remove from the index in the first place.
    """
    document = get_document_or_raise(db, document_id)

    chunk_ids = [chunk.id for chunk in document.chunks]
    get_vector_store().remove(chunk_ids)
    get_vector_store().save()

    file_path = Path(document.stored_path)
    file_path.unlink(missing_ok=True)

    db.delete(document)  # cascades to delete all Chunk rows (see relationship config)
    db.commit()
    logger.info("Deleted document id=%d ('%s')", document_id, document.filename)


def reindex_document(db: Session, document_id: int) -> Document:
    """Re-run chunking + embedding for a document already on disk.

    Useful after changing `CHUNK_SIZE`/`CHUNK_OVERLAP` in settings, or after
    upgrading the embedding model - the raw PDF doesn't need to be
    re-uploaded, just reprocessed.
    """
    document = get_document_or_raise(db, document_id)
    file_path = Path(document.stored_path)

    old_chunk_ids = [chunk.id for chunk in document.chunks]
    get_vector_store().remove(old_chunk_ids)
    for chunk in list(document.chunks):
        db.delete(chunk)
    db.flush()

    pages_text = pdf_service.extract_text_by_page(file_path)
    text_chunks = chunking_service.chunk_pages(pages_text)
    _embed_and_store_chunks(db, document, text_chunks)

    document.page_count = len(pages_text)
    document.chunk_count = len(text_chunks)
    document.status = "indexed"
    db.commit()
    get_vector_store().save()

    logger.info("Re-indexed document id=%d into %d chunks", document_id, len(text_chunks))
    return document
