"""
Converting text into embedding vectors.

WHAT IS AN EMBEDDING?
--------------------------
An embedding is a fixed-length list of numbers (a vector) that represents
the *meaning* of a piece of text. Texts with similar meaning end up close
together in this vector space, even if they don't share any exact words
(e.g. "car" and "automobile" land near each other). This is what makes
*semantic* search possible - we're comparing meaning, not just keywords.

WHY `sentence-transformers` + `BAAI/bge-small-en-v1.5`?
-------------------------------------------------------------
`sentence-transformers` is a library built on top of HuggingFace
`transformers` that adds pooling layers specifically trained so a whole
sentence/paragraph maps to one good vector (raw BERT-style models are
trained per-*token*, not per-sentence).

`BAAI/bge-small-en-v1.5` ("BGE" = BAAI General Embedding) is a strong,
compact (~130MB) English embedding model that ranks well on retrieval
benchmarks (MTEB) relative to its size, and - critically for a portfolio
project meant to run locally/on modest cloud hardware - it's fast enough to
run on CPU with no GPU required.

WHY A SEPARATE PREFIX FOR QUERIES?
---------------------------------------
BGE models are trained asymmetrically for retrieval: the *documents* being
searched are embedded as-is, but *queries* should be embedded with a fixed
instruction prefix ("Represent this sentence for searching relevant
passages: "). This tells the model "this text is a search query, not a
passage to be found" and measurably improves retrieval quality. This is a
model-specific quirk documented on the model's HuggingFace card - always
check a model's docs for this kind of detail rather than assuming all
embedding models behave identically.

WHY NORMALIZE EMBEDDINGS?
------------------------------
We L2-normalize every vector (scale it to length 1). Once normalized, the
*inner product* (dot product) between two vectors is mathematically
equivalent to their *cosine similarity* - a value between -1 and 1
measuring the angle between them, ignoring magnitude. This lets us use
FAISS's simplest, fastest index type (`IndexFlatIP`) to get cosine-based
semantic similarity, rather than needing a more complex distance metric.

WHY A MODULE-LEVEL SINGLETON?
----------------------------------
Loading a transformer model from disk into memory takes real time (usually
a few seconds) and RAM. We must not reload it on every single request -
instead we load it once, the first time it's needed, and reuse that one
instance for the lifetime of the process.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config.settings import settings
from app.utils.exceptions import EmbeddingGenerationError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# BGE's documented instruction prefix for *query* embeddings (retrieval
# tasks only - not needed for the passages/documents being indexed).
QUERY_INSTRUCTION_PREFIX = "Represent this sentence for searching relevant passages: "

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model."""
    global _model
    if _model is None:
        logger.info("Loading embedding model '%s' ...", settings.EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _model


def embed_documents(texts: list[str]) -> np.ndarray:
    """Embed a batch of document chunks for storage in the vector index.

    Returns a 2D float32 array of shape (len(texts), EMBEDDING_DIMENSION).
    """
    if not texts:
        return np.empty((0, settings.EMBEDDING_DIMENSION), dtype=np.float32)

    try:
        model = _get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to embed %d document chunk(s)", len(texts))
        raise EmbeddingGenerationError("Failed to generate embeddings for document chunks.") from exc


def embed_query(query: str) -> np.ndarray:
    """Embed a single user question for similarity search.

    Applies the BGE-specific query instruction prefix (see module docstring).
    """
    try:
        model = _get_model()
        prefixed_query = f"{QUERY_INSTRUCTION_PREFIX}{query}"
        embedding = model.encode(
            prefixed_query,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding.astype(np.float32)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to embed query")
        raise EmbeddingGenerationError("Failed to generate an embedding for the question.") from exc
