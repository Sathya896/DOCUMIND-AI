"""
Shared pytest fixtures.

WHY MOCK THE EMBEDDING MODEL AND THE LLM IN MOST TESTS?
---------------------------------------------------------------
Loading the real `BAAI/bge-small-en-v1.5` model takes several seconds and
downloads ~130MB on first use; calling a real Ollama server requires a
separate local process to be running. Neither is appropriate for a fast,
deterministic, CI-friendly test suite. So most tests replace:

* `embedding_service.embed_documents` / `embed_query` with a fast fake that
  returns random-but-deterministic vectors of the correct dimension.
* `llm_service.generate_answer` with a fake that returns a canned string.

This tests everything *around* those calls (validation, chunking, FAISS
indexing, DB writes, API contracts, error handling) without depending on
heavyweight ML infrastructure. A separate, explicitly-marked integration
test (`test_embedding_service_integration.py`) exercises the *real* model
to prove the wiring works end-to-end.
"""

import shutil
import tempfile
from pathlib import Path

import fitz  # PyMuPDF - used here only to generate a real, tiny PDF for tests
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def temp_runtime_dirs(monkeypatch: pytest.MonkeyPatch):
    """Redirect uploads/vectorstore/data to a fresh temp directory per test.

    This guarantees tests never touch the real `backend/uploads`,
    `backend/vectorstore`, or `backend/data` folders, and that tests don't
    leak state into one another.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="documind_test_"))
    upload_dir = temp_dir / "uploads"
    vectorstore_dir = temp_dir / "vectorstore"
    data_dir = temp_dir / "data"
    for directory in (upload_dir, vectorstore_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    from app.config.settings import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(settings, "VECTORSTORE_DIR", vectorstore_dir)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{data_dir / 'test.db'}")

    yield {"upload_dir": upload_dir, "vectorstore_dir": vectorstore_dir, "data_dir": data_dir}

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture()
def fake_embeddings(monkeypatch: pytest.MonkeyPatch):
    """Replace the real embedding model with a deterministic fake.

    Uses a hash of each text so identical text always produces the same
    vector (needed for the search-relevance assertions in the API tests),
    without loading any actual ML model.
    """
    from app.config.settings import settings
    from app.services import embedding_service

    def _fake_vector(text: str) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        vector = rng.standard_normal(settings.EMBEDDING_DIMENSION).astype(np.float32)
        return vector / np.linalg.norm(vector)

    def fake_embed_documents(texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, settings.EMBEDDING_DIMENSION), dtype=np.float32)
        return np.stack([_fake_vector(t) for t in texts])

    def fake_embed_query(query: str) -> np.ndarray:
        return _fake_vector(query)

    monkeypatch.setattr(embedding_service, "embed_documents", fake_embed_documents)
    monkeypatch.setattr(embedding_service, "embed_query", fake_embed_query)


@pytest.fixture()
def fake_llm(monkeypatch: pytest.MonkeyPatch):
    """Replace the Ollama-backed LLM call with a canned async response."""
    from app.services import llm_service

    async def fake_generate_answer(prompt: str) -> str:
        return "This is a fake grounded answer based on the provided context."

    monkeypatch.setattr(llm_service, "generate_answer", fake_generate_answer)


@pytest.fixture()
def reset_vector_store_singleton(monkeypatch: pytest.MonkeyPatch):
    """Force `get_vector_store()` to build a brand-new store for this test.

    The real module caches a single `VectorStore` instance at import time.
    Without resetting it, tests would share (and pollute) each other's
    FAISS index in memory even though `temp_runtime_dirs` gives each test
    its own directory on disk.
    """
    from app.services import vector_store_service

    monkeypatch.setattr(vector_store_service, "_vector_store", None)


@pytest.fixture()
def client(
    temp_runtime_dirs, fake_embeddings, fake_llm, reset_vector_store_singleton, monkeypatch
):
    """A FastAPI TestClient wired to an isolated DB/filesystem and fake ML calls.

    WHY OVERRIDE `get_db` INSTEAD OF JUST MONKEYPATCHING `settings.DATABASE_URL`?
    -----------------------------------------------------------------------------------
    `app/models/database.py` creates its SQLAlchemy `engine` exactly once, at
    *module import time* (a deliberate singleton - see that file's
    docstring). By the time a test tries to change `settings.DATABASE_URL`,
    that engine object already exists and is cached in `sys.modules`; it
    would keep pointing at whichever database URL was in effect the first
    time the module was ever imported in this test process, silently
    reusing the *same* engine/connection across every test that came after.

    FastAPI's `dependency_overrides` is the standard, recommended way to
    swap out a dependency like `get_db` in tests: we build a brand-new
    engine + session factory pointing at this test's isolated SQLite file,
    create fresh tables on it, and hand out sessions from *that* factory
    instead of the app's shared one. This guarantees complete isolation
    between tests without needing to fight module-level caching.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.main import app
    from app.models import chat, document  # noqa: F401 - registers tables on Base
    from app.models.database import Base, get_db

    test_engine = create_engine(
        f"sqlite:///{temp_runtime_dirs['data_dir'] / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # The real `init_db()` (called from the app's lifespan) would otherwise
    # touch the *shared* global engine's database file - a no-op here since
    # we manage table creation ourselves against `test_engine` above.
    monkeypatch.setattr("app.main.init_db", lambda: None)

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        test_engine.dispose()


def make_test_pdf_bytes(pages_text: list[str]) -> bytes:
    """Generate a minimal, real PDF file (in-memory) containing the given
    per-page text, using PyMuPDF itself.

    Building a real PDF (rather than hand-crafting fake bytes) means our
    tests exercise the actual PyMuPDF parsing code path, catching real
    extraction bugs instead of just testing against a mock.
    """
    document = fitz.open()
    for text in pages_text:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes
