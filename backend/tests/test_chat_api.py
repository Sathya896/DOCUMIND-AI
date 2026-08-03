"""Integration tests for the /api/v1/chat endpoints (the RAG pipeline)."""

from tests.conftest import make_test_pdf_bytes


def _upload_sample_document(client) -> int:
    pdf_bytes = make_test_pdf_bytes(["The capital of France is Paris. It is a major city."])
    response = client.post(
        "/api/v1/documents/upload", files={"file": ("geography.pdf", pdf_bytes, "application/pdf")}
    )
    return response.json()["document"]["id"]


def test_ask_question_without_any_documents_returns_404(client):
    response = client.post("/api/v1/chat/ask", json={"question": "What is the capital of France?"})
    assert response.status_code == 404


def test_ask_question_returns_grounded_answer_with_sources(client):
    _upload_sample_document(client)

    response = client.post("/api/v1/chat/ask", json={"question": "What is the capital of France?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["conversation_id"] is not None
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["document_name"] == "geography.pdf"


def test_ask_question_persists_conversation_history(client):
    _upload_sample_document(client)

    first = client.post("/api/v1/chat/ask", json={"question": "What is the capital of France?"})
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/chat/ask",
        json={"question": "Tell me more about it.", "conversation_id": conversation_id},
    )
    assert second.json()["conversation_id"] == conversation_id

    history_response = client.get(f"/api/v1/chat/conversations/{conversation_id}")
    assert history_response.status_code == 200
    messages = history_response.json()["messages"]
    # 2 user questions + 2 assistant answers
    assert len(messages) == 4
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_ask_question_can_be_restricted_to_specific_documents(client):
    doc_id = _upload_sample_document(client)

    response = client.post(
        "/api/v1/chat/ask",
        json={"question": "What is the capital of France?", "document_ids": [doc_id]},
    )
    assert response.status_code == 200

    response_missing_doc = client.post(
        "/api/v1/chat/ask",
        json={"question": "What is the capital of France?", "document_ids": [9999]},
    )
    assert response_missing_doc.status_code == 404


def test_list_conversations_returns_created_conversation(client):
    _upload_sample_document(client)
    ask_response = client.post("/api/v1/chat/ask", json={"question": "What is the capital of France?"})
    conversation_id = ask_response.json()["conversation_id"]

    response = client.get("/api/v1/chat/conversations")
    assert response.status_code == 200
    ids = [c["id"] for c in response.json()]
    assert conversation_id in ids
