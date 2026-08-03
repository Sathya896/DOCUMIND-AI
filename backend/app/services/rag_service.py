"""
The Retrieval-Augmented Generation (RAG) pipeline.

WHAT IS RAG, AND WHY DO WE NEED IT?
-----------------------------------------
LLMs only "know" what was in their training data - they have never seen
the PDFs a user uploads, and by default they'll either refuse to answer or
(worse) confidently hallucinate an answer based on unrelated training
knowledge. RAG fixes this by *retrieving* the most relevant pieces of the
user's own documents at question time and *inserting them directly into
the prompt*, so the LLM answers using text it can literally see, right
now, in its input - not from memory. This is why the system can answer
questions about documents the LLM was never trained on, and why answers
can be traced back to a specific source passage.

THE PIPELINE, STEP BY STEP:
--------------------------------
1. Embed the user's question (`embedding_service.embed_query`).
2. Search FAISS for the `TOP_K_RESULTS` most similar chunk vectors.
3. Look up the matching `Chunk` rows in SQLite to get their actual text,
   page number, and parent document.
4. Build a prompt that instructs the LLM to answer *only* using that
   retrieved text.
5. Send the prompt to Ollama and get a grounded answer back.
6. Persist both the question and answer (with sources) to chat history.

WHY INSTRUCT THE LLM TO SAY "I DON'T KNOW" WHEN CONTEXT IS INSUFFICIENT?
-------------------------------------------------------------------------------
Without an explicit instruction, LLMs default to being "helpful" even when
that means inventing an answer not actually supported by the given context
(a well-known failure mode called *hallucination*). Explicitly telling the
model to admit uncertainty when the retrieved context doesn't contain the
answer is one of the most effective and cheapest ways to make a RAG system
trustworthy.
"""

import json

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.chat import Conversation, Message
from app.models.document import Chunk, Document
from app.models.schemas import SourceChunk
from app.services import embedding_service, llm_service
from app.services.vector_store_service import get_vector_store
from app.utils.exceptions import NoRelevantContextError
from app.utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE = """You are DocuMind AI, a careful assistant that answers questions \
using ONLY the context provided below, which was extracted from the user's own documents.

Rules:
- Base your answer strictly on the context. Do not use outside knowledge.
- If the context does not contain enough information to answer, say so \
honestly instead of guessing.
- Be concise and directly answer the question.
- When helpful, mention which part of the context supports your answer.

Context:
{context}

Question: {question}

Answer:"""


def _retrieve_relevant_chunks(
    db: Session, question: str, document_ids: list[int] | None
) -> list[tuple[Chunk, float]]:
    """Embed the question and return the top-k most similar (Chunk, score) pairs.

    `document_ids`, when provided, restricts results to chunks belonging to
    those documents (e.g. "only search within this one PDF"). We over
    -fetch from FAISS and filter in Python because FAISS's flat index has
    no native concept of metadata filtering - a reasonable trade-off at
    this scale; a production system with millions of vectors might instead
    use a vector database with built-in filtered search (e.g. Qdrant,
    Pinecone, pgvector).
    """
    query_embedding = embedding_service.embed_query(question)

    fetch_count = settings.TOP_K_RESULTS * 5 if document_ids else settings.TOP_K_RESULTS
    raw_results = get_vector_store().search(query_embedding, top_k=fetch_count)

    if not raw_results:
        return []

    chunk_ids = [chunk_id for chunk_id, _ in raw_results]
    chunks_by_id = {chunk.id: chunk for chunk in db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()}

    results: list[tuple[Chunk, float]] = []
    for chunk_id, score in raw_results:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue  # vector exists in FAISS but its row was deleted - skip defensively
        if document_ids is not None and chunk.document_id not in document_ids:
            continue
        results.append((chunk, score))
        if len(results) >= settings.TOP_K_RESULTS:
            break

    return results


def _build_prompt(question: str, chunks_with_scores: list[tuple[Chunk, float]]) -> str:
    context_blocks = []
    for chunk, _score in chunks_with_scores:
        context_blocks.append(
            f"[Source: {chunk.document.filename}, page {chunk.page_number}]\n{chunk.content}"
        )
    context = "\n\n---\n\n".join(context_blocks)
    return PROMPT_TEMPLATE.format(context=context, question=question)


def _to_source_chunks(chunks_with_scores: list[tuple[Chunk, float]]) -> list[SourceChunk]:
    return [
        SourceChunk(
            document_id=chunk.document_id,
            document_name=chunk.document.filename,
            page_number=chunk.page_number,
            snippet=chunk.content,
            relevance_score=round(score, 4),
        )
        for chunk, score in chunks_with_scores
    ]


async def answer_question(
    db: Session,
    question: str,
    conversation_id: int | None,
    document_ids: list[int] | None,
) -> tuple[Conversation, str, list[SourceChunk]]:
    """Run the full RAG pipeline for one question and persist the exchange.

    Returns the (possibly newly-created) conversation, the answer text, and
    the list of sources used, ready to be serialised as an `AskResponse`.
    """
    conversation = _get_or_create_conversation(db, conversation_id, question)

    chunks_with_scores = _retrieve_relevant_chunks(db, question, document_ids)
    if not chunks_with_scores:
        raise NoRelevantContextError(
            "No indexed documents match this question yet. "
            "Upload a document first, or try rephrasing your question."
        )

    prompt = _build_prompt(question, chunks_with_scores)
    answer = await llm_service.generate_answer(prompt)
    sources = _to_source_chunks(chunks_with_scores)

    _save_message(db, conversation.id, role="user", content=question, sources=None)
    _save_message(db, conversation.id, role="assistant", content=answer, sources=sources)
    db.commit()

    return conversation, answer, sources


def _get_or_create_conversation(
    db: Session, conversation_id: int | None, first_question: str
) -> Conversation:
    if conversation_id is not None:
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None:
            return conversation
        logger.warning("conversation_id=%d not found; starting a new conversation", conversation_id)

    # Use the first ~50 characters of the opening question as a human
    # -readable title, similar to how ChatGPT titles new conversations.
    title = first_question.strip()[:50]
    conversation = Conversation(title=title or "New conversation")
    db.add(conversation)
    db.flush()
    return conversation


def _save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    sources: list[SourceChunk] | None,
) -> Message:
    sources_json = (
        json.dumps([source.model_dump() for source in sources]) if sources else None
    )
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources_json=sources_json,
    )
    db.add(message)
    return message
