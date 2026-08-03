"""
Document management endpoints: upload, list, retrieve, delete, re-index.

WHY IS THIS FILE "THIN"?
------------------------------
Notice every handler below is short: parse the request, call a service
function, shape the response. All real logic (validation, extraction,
chunking, embedding, DB writes) lives in `services/`. This split matters
because:

* Routes can be unit-tested by mocking the service layer, without needing
  a real PDF, a real embedding model, or a real database.
* The same ingestion logic could be reused by a future CLI script or a
  background worker, since it doesn't depend on FastAPI's `Request`/
  `UploadFile` objects at all past this file.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.document import Document
from app.models.schemas import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from app.services import document_service
from app.utils.exceptions import DocumentNotFoundError, DocuMindError, InvalidFileError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(..., description="A PDF file to upload and index."),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a single PDF, extract its text, chunk it, embed it, and index it.

    Uploading multiple documents is done by calling this endpoint once per
    file - each upload is independent, so one failing file (e.g. corrupted
    PDF) never blocks the others from succeeding. The frontend's upload
    component loops over the files a user selects and calls this endpoint
    for each one (see Phase 4/5).
    """
    file_bytes = await file.read()

    try:
        document: Document = document_service.ingest_document(
            db=db, filename=file.filename or "unnamed.pdf", file_bytes=file_bytes
        )
    except InvalidFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except DocuMindError as exc:
        logger.error("Failed to ingest document '%s': %s", file.filename, exc.message)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    return DocumentUploadResponse(document=DocumentResponse.model_validate(document))


@router.get("/", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)) -> DocumentListResponse:
    """List every uploaded document and its indexing status."""
    documents = document_service.list_documents(db)
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    """Retrieve metadata for a single document by ID."""
    try:
        document = document_service.get_document_or_raise(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a document: removes its file, its vectors, and its metadata.

    Returns HTTP 204 (No Content) on success, following the REST convention
    that a successful DELETE has nothing meaningful to return in the body.
    """
    try:
        document_service.delete_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    """Re-run chunking and embedding for a document already stored on disk.

    Useful after tuning `CHUNK_SIZE`/`CHUNK_OVERLAP` or upgrading the
    embedding model, without requiring the user to re-upload the file.
    """
    try:
        document = document_service.reindex_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except DocuMindError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    return DocumentResponse.model_validate(document)
