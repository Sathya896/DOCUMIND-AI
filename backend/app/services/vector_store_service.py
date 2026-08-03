"""
Managing the FAISS vector index: adding, searching, deleting, and
persisting embeddings to disk.

WHAT IS FAISS?
------------------
FAISS ("Facebook AI Similarity Search") is a library for efficient nearest
-neighbour search over vectors. Given a query vector, it quickly finds the
`k` stored vectors most similar to it - far faster than comparing the query
to every vector one-by-one in pure Python once you have more than a
trivial number of vectors.

WHY `IndexFlatIP` WRAPPED IN `IndexIDMap`?
------------------------------------------------
* `IndexFlatIP` performs an *exact* (not approximate) search using the
  inner product between vectors. Because we store L2-normalized
  embeddings (see `embedding_service.py`), inner product == cosine
  similarity. "Flat" means it does a brute-force scan - perfectly fine
  and simplest-to-reason-about at the scale of a personal/portfolio
  project (thousands of chunks); larger-scale systems would swap in an
  approximate index type (e.g. `IndexIVFFlat` or `IndexHNSW`) for
  sub-linear search time, at a small accuracy cost.
* Plain FAISS indexes only support sequential positional IDs. Wrapping
  the flat index in `IndexIDMap` lets us assign our *own* IDs (we reuse
  each chunk's SQLite primary key - see `document.py`'s docstring) when
  adding vectors, and lets us delete specific vectors by that same ID
  later (`remove_ids`) without needing to track position shifts ourselves.

WHY PERSIST THE INDEX TO DISK?
------------------------------------
FAISS indexes live in memory. Without persistence, restarting the backend
process would silently lose every embedding we'd computed, forcing a full
re-index of every document. `faiss.write_index` / `faiss.read_index`
serialise the index to/from a single file in `VECTORSTORE_DIR`, so the
index survives restarts - this is the "Persistent FAISS index" feature
from the project's Phase 5.

THREAD SAFETY
------------------
Uvicorn can handle requests concurrently (e.g. via a thread pool for sync
route handlers). FAISS's Python bindings are not guaranteed thread-safe for
concurrent writes, so all mutating operations (add/remove/save) go through
a single `threading.Lock` held by this module's singleton instance.
"""

import threading
from pathlib import Path

import faiss
import numpy as np

from app.config.settings import settings
from app.utils.exceptions import VectorStoreError
from app.utils.logger import get_logger

logger = get_logger(__name__)

INDEX_FILE_NAME = "documind.index"


class VectorStore:
    """A thin, persistence-aware wrapper around a FAISS index."""

    def __init__(self, dimension: int, index_path: Path) -> None:
        self._dimension = dimension
        self._index_path = index_path
        self._lock = threading.Lock()
        self._index: faiss.IndexIDMap = self._load_or_create_index()

    def _load_or_create_index(self) -> faiss.IndexIDMap:
        if self._index_path.exists():
            logger.info("Loading existing FAISS index from '%s'", self._index_path)
            try:
                return faiss.read_index(str(self._index_path))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to load FAISS index, creating a new one")
                raise VectorStoreError("Failed to load the existing vector index.") from exc

        logger.info("No existing FAISS index found - creating a new one.")
        flat_index = faiss.IndexFlatIP(self._dimension)
        return faiss.IndexIDMap(flat_index)

    def save(self) -> None:
        """Persist the current index state to disk."""
        with self._lock:
            faiss.write_index(self._index, str(self._index_path))
        logger.info("FAISS index saved to '%s' (%d vectors)", self._index_path, self.count)

    def add(self, ids: list[int], embeddings: np.ndarray) -> None:
        """Add a batch of embeddings, tagged with the given chunk IDs."""
        if len(ids) != embeddings.shape[0]:
            raise VectorStoreError("Number of IDs must match number of embeddings.")
        if not ids:
            return

        id_array = np.asarray(ids, dtype=np.int64)
        with self._lock:
            self._index.add_with_ids(embeddings, id_array)

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        """Return up to `top_k` (chunk_id, similarity_score) pairs, best first.

        FAISS returns `-1` as a placeholder ID when there are fewer than
        `top_k` vectors in the index - we filter those out.
        """
        if self.count == 0:
            return []

        query_vector = np.expand_dims(query_embedding, axis=0)
        with self._lock:
            scores, ids = self._index.search(query_vector, min(top_k, self.count))

        results = []
        for chunk_id, score in zip(ids[0], scores[0], strict=True):
            if chunk_id == -1:
                continue
            results.append((int(chunk_id), float(score)))
        return results

    def remove(self, ids: list[int]) -> None:
        """Remove vectors by chunk ID (used when deleting/re-indexing a document)."""
        if not ids:
            return
        id_selector = faiss.IDSelectorBatch(np.asarray(ids, dtype=np.int64))
        with self._lock:
            self._index.remove_ids(id_selector)

    @property
    def count(self) -> int:
        return int(self._index.ntotal)


# Module-level singleton, mirroring the embedding model singleton pattern:
# a FAISS index is expensive to load from disk and must be shared (not
# recreated) across requests so writes from one request are visible to the
# next search.
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the process-wide `VectorStore`, creating it on first use.

    The index path is resolved from `settings.VECTORSTORE_DIR` *at call
    time* (not cached at import time) so that tests which monkeypatch
    `settings.VECTORSTORE_DIR` and reset this singleton (see
    `tests/conftest.py`) reliably get an index scoped to their own
    temporary directory instead of ever touching the real project folder.
    """
    global _vector_store
    if _vector_store is None:
        index_path = settings.VECTORSTORE_DIR / INDEX_FILE_NAME
        _vector_store = VectorStore(dimension=settings.EMBEDDING_DIMENSION, index_path=index_path)
    return _vector_store
