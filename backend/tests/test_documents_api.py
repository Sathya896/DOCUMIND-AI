"""Integration tests for the /api/v1/documents endpoints.

These exercise the full stack (FastAPI route -> service -> SQLite -> FAISS)
using a real, tiny PDF, but with the embedding model and LLM faked (see
`conftest.py`) so tests run in milliseconds without any ML dependencies.
"""

from tests.conftest import make_test_pdf_bytes


def test_upload_document_success(client):
    pdf_bytes = make_test_pdf_bytes(["Hello, this is page one of a test document."])

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document"]["filename"] == "sample.pdf"
    assert body["document"]["status"] == "indexed"
    assert body["document"]["page_count"] == 1
    assert body["document"]["chunk_count"] >= 1


def test_upload_rejects_non_pdf_extension(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_fake_pdf_content(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", b"not really a pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_rejects_pdf_with_no_extractable_text(client):
    pdf_bytes = make_test_pdf_bytes([""])  # a PDF with one blank page / no text
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 422


def test_list_documents_returns_uploaded_files(client):
    pdf_bytes = make_test_pdf_bytes(["Some content."])
    client.post("/api/v1/documents/upload", files={"file": ("a.pdf", pdf_bytes, "application/pdf")})
    client.post("/api/v1/documents/upload", files={"file": ("b.pdf", pdf_bytes, "application/pdf")})

    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {doc["filename"] for doc in body["documents"]} == {"a.pdf", "b.pdf"}


def test_get_document_not_found_returns_404(client):
    response = client.get("/api/v1/documents/999")
    assert response.status_code == 404


def test_delete_document_removes_it(client):
    pdf_bytes = make_test_pdf_bytes(["Some content."])
    upload_response = client.post(
        "/api/v1/documents/upload", files={"file": ("a.pdf", pdf_bytes, "application/pdf")}
    )
    document_id = upload_response.json()["document"]["id"]

    delete_response = client.delete(f"/api/v1/documents/{document_id}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/documents/{document_id}")
    assert get_response.status_code == 404


def test_reindex_document_recomputes_chunks(client):
    pdf_bytes = make_test_pdf_bytes(["Some content to be chunked and embedded again."])
    upload_response = client.post(
        "/api/v1/documents/upload", files={"file": ("a.pdf", pdf_bytes, "application/pdf")}
    )
    document_id = upload_response.json()["document"]["id"]

    reindex_response = client.post(f"/api/v1/documents/{document_id}/reindex")
    assert reindex_response.status_code == 200
    assert reindex_response.json()["status"] == "indexed"
