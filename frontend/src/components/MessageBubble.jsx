import SourceList from "./SourceList";

/**
 * Renders a single chat message - either the user's question or the
 * assistant's grounded answer (with its supporting sources, if any).
 */
function MessageBubble({ role, content, sources }) {
  const isUser = role === "user";

  return (
    <div className={`message ${isUser ? "message--user" : "message--assistant"}`}>
      <div className="message__avatar" aria-hidden="true">
        {isUser ? "🧑" : "🤖"}
      </div>
      <div className="message__body">
        <p className="message__content">{content}</p>
        {!isUser && <SourceList sources={sources} />}
      </div>
    </div>
  );
}

export default MessageBubble;
