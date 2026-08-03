/**
 * A small animated "typing" indicator (three bouncing dots).
 *
 * WHY A DEDICATED COMPONENT INSTEAD OF INLINE JSX?
 * ------------------------------------------------------
 * It's reused in two places (while the assistant is "thinking" in the chat,
 * and while a document is being indexed in the document list) - extracting
 * it once keeps both usages visually consistent and avoids duplicating the
 * animation markup/CSS class names.
 */
function LoadingIndicator({ label = "Thinking" }) {
  return (
    <div className="loading-indicator" role="status" aria-live="polite">
      <span className="loading-dots">
        <span />
        <span />
        <span />
      </span>
      <span className="loading-label">{label}</span>
    </div>
  );
}

export default LoadingIndicator;
