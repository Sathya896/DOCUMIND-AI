"""Unit tests for the text-splitting logic."""

from app.services.chunking_service import chunk_pages


def test_chunk_pages_preserves_page_numbers():
    pages = ["Page one content.", "Page two content."]
    chunks = chunk_pages(pages)

    assert [c.page_number for c in chunks] == [1, 2]
    assert chunks[0].content == "Page one content."
    assert chunks[1].content == "Page two content."


def test_chunk_pages_skips_blank_pages():
    pages = ["Real content here.", "   ", ""]
    chunks = chunk_pages(pages)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1


def test_chunk_pages_splits_long_text_into_multiple_chunks(monkeypatch):
    from app.config import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "CHUNK_SIZE", 50)
    monkeypatch.setattr(settings_module.settings, "CHUNK_OVERLAP", 10)

    long_paragraph = "This is a sentence. " * 20  # ~400 characters
    chunks = chunk_pages([long_paragraph])

    assert len(chunks) > 1
    assert all(chunk.page_number == 1 for chunk in chunks)
    # No chunk should wildly exceed the configured size.
    assert all(len(chunk.content) <= 60 for chunk in chunks)


def test_chunk_pages_empty_input_returns_empty_list():
    assert chunk_pages([]) == []
