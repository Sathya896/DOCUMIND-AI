"""Unit tests for the FAISS wrapper, using small hand-built vectors.

No embedding model is needed here - we test the vector store's mechanics
(add/search/remove/persist) directly with synthetic vectors.
"""

import numpy as np

from app.services.vector_store_service import VectorStore


def _unit_vector(values: list[float]) -> np.ndarray:
    vector = np.array(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def test_add_and_search_returns_closest_vector(tmp_path):
    store = VectorStore(dimension=3, index_path=tmp_path / "index.faiss")

    vector_a = _unit_vector([1.0, 0.0, 0.0])
    vector_b = _unit_vector([0.0, 1.0, 0.0])
    store.add(ids=[10, 20], embeddings=np.stack([vector_a, vector_b]))

    results = store.search(vector_a, top_k=1)

    assert results[0][0] == 10
    assert results[0][1] > 0.99  # cosine similarity of a vector with itself ~= 1


def test_remove_deletes_vector_from_index(tmp_path):
    store = VectorStore(dimension=3, index_path=tmp_path / "index.faiss")
    store.add(ids=[1, 2], embeddings=np.stack([_unit_vector([1, 0, 0]), _unit_vector([0, 1, 0])]))

    store.remove([1])

    assert store.count == 1
    results = store.search(_unit_vector([1, 0, 0]), top_k=2)
    assert all(chunk_id != 1 for chunk_id, _ in results)


def test_save_and_reload_preserves_vectors(tmp_path):
    index_path = tmp_path / "index.faiss"
    store = VectorStore(dimension=3, index_path=index_path)
    store.add(ids=[42], embeddings=np.stack([_unit_vector([1, 2, 3])]))
    store.save()

    reloaded_store = VectorStore(dimension=3, index_path=index_path)

    assert reloaded_store.count == 1
    results = reloaded_store.search(_unit_vector([1, 2, 3]), top_k=1)
    assert results[0][0] == 42


def test_search_on_empty_index_returns_no_results(tmp_path):
    store = VectorStore(dimension=3, index_path=tmp_path / "index.faiss")
    assert store.search(_unit_vector([1, 0, 0]), top_k=5) == []
