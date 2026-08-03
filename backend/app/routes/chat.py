"""
Chat / question-answering endpoints - the RAG pipeline's HTTP surface.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.chat import Conversation
from app.models.database import get_db
from app.models.schemas import (
    AskRequest,
    AskResponse,
    ConversationResponse,
    MessageResponse,
    SourceChunk,
)
from app.services import rag_service
from app.utils.exceptions import DocuMindError, LLMGenerationError, NoRelevantContextError
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    """Answer a natural-language question using only the uploaded documents.

    Runs the full RAG pipeline (retrieve -> build prompt -> generate) and
    persists the exchange to chat history under `request.conversation_id`
    (or a newly created conversation if omitted).
    """
    try:
        conversation, answer, sources = await rag_service.answer_question(
            db=db,
            question=request.question,
            conversation_id=request.conversation_id,
            document_ids=request.document_ids,
        )
    except NoRelevantContextError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except LLMGenerationError as exc:
        # 503 (Service Unavailable) signals "the LLM backend is down", which
        # is a different, actionable situation from a client input error.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc
    except DocuMindError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc

    return AskResponse(conversation_id=conversation.id, answer=answer, sources=sources)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Session = Depends(get_db)) -> list[ConversationResponse]:
    """List all chat conversations, most recent first."""
    conversations = db.query(Conversation).order_by(Conversation.created_at.desc()).all()
    return [_to_conversation_response(c) for c in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)) -> ConversationResponse:
    """Retrieve one conversation's full message history, in chronological order."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return _to_conversation_response(conversation)


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Convert a Conversation ORM object into its API schema, deserialising
    each message's stored `sources_json` back into `SourceChunk` objects."""
    messages = [
        MessageResponse(
            role=message.role,
            content=message.content,
            sources=[SourceChunk(**s) for s in json.loads(message.sources_json)]
            if message.sources_json
            else [],
            created_at=message.created_at,
        )
        for message in conversation.messages
    ]
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=messages,
    )
