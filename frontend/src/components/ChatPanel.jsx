import { useEffect, useRef, useState } from "react";

import LoadingIndicator from "./LoadingIndicator";
import MessageBubble from "./MessageBubble";

/**
 * The main chat interface: scrollable message history + a question input.
 *
 * WHY KEEP AN INTERNAL `draft` STATE HERE INSTEAD OF IN `App.jsx`?
 * -------------------------------------------------------------------------
 * The text currently being typed is purely a concern of *this* input box -
 * no other component needs to know about it while the user is still
 * typing. Lifting it up to `App.jsx` would force that component to
 * re-render on every keystroke for no benefit. Only the *submitted*
 * question is reported upward, via `onAsk`.
 */
function ChatPanel({ messages, isAsking, onAsk, hasIndexedDocuments, onNewConversation }) {
  const [draft, setDraft] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAsking]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isAsking) return;
    onAsk(question);
    setDraft("");
  };

  return (
    <div className="chat-panel">
      {messages.length > 0 && (
        <div className="chat-panel__header">
          <button type="button" className="chat-panel__new-conversation" onClick={onNewConversation}>
            + New conversation
          </button>
        </div>
      )}

      <div className="chat-panel__messages">
        {messages.length === 0 ? (
          <EmptyState hasIndexedDocuments={hasIndexedDocuments} />
        ) : (
          messages.map((message) => <MessageBubble key={message.id} {...message} />)
        )}

        {isAsking && (
          <div className="message message--assistant">
            <div className="message__avatar" aria-hidden="true">
              🤖
            </div>
            <div className="message__body">
              <LoadingIndicator label="Searching your documents" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-panel__input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            hasIndexedDocuments
              ? "Ask a question about your documents…"
              : "Upload a document first to start asking questions"
          }
          disabled={!hasIndexedDocuments || isAsking}
          aria-label="Question"
        />
        <button type="submit" disabled={!hasIndexedDocuments || isAsking || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function EmptyState({ hasIndexedDocuments }) {
  return (
    <div className="chat-panel__empty">
      <span className="chat-panel__empty-icon" aria-hidden="true">
        💬
      </span>
      <h2>Ask DocuMind AI anything about your documents</h2>
      <p>
        {hasIndexedDocuments
          ? "Every answer is grounded in your uploaded PDFs, with sources you can verify."
          : "Upload a PDF on the left to get started."}
      </p>
    </div>
  );
}

export default ChatPanel;
