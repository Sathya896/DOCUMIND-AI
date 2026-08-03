"""
ORM models for chat history.

WHY STORE CHAT HISTORY AT ALL?
----------------------------------
Without persistence, refreshing the browser would wipe out a user's
conversation. Storing messages also enables features expected of any real
chat product: showing past conversations, and (in a future iteration)
using earlier turns as extra context for follow-up questions.

DESIGN: `Conversation` -> many `Message`s
--------------------------------------------
A `Conversation` groups a sequence of question/answer turns together (think
of it as one "chat session"). Each `Message` is either from the "user" or
the "assistant", mirroring the shape most chat APIs (including Ollama's and
OpenAI's) already use - which makes it trivial to serialise this history
back into a prompt later if we add multi-turn context.

`sources_json` stores which chunks were used to answer an assistant
message, serialised as JSON text. We use JSON-in-a-text-column rather than
a separate join table because sources are read-only, denormalised
"receipt" data - they are never queried individually, only ever displayed
alongside their message. This is a deliberate, pragmatic simplification.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database import Base


class Conversation(Base):
    """A chat session, grouping related question/answer turns."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """A single message within a conversation - either the user's question
    or the assistant's grounded answer."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON-serialised list of {"document_name", "page_number", "snippet"}.
    # Nullable because user messages have no sources.
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
