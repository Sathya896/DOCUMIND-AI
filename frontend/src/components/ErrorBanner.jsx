/**
 * A dismissible banner for surfacing user-facing errors.
 *
 * WHY SURFACE ERRORS IN THE UI INSTEAD OF ONLY LOGGING TO THE CONSOLE?
 * -------------------------------------------------------------------------
 * A user uploading a corrupted PDF, or asking a question while the backend
 * (or Ollama) is down, needs to know *something went wrong and why* -
 * silently failing or only logging to the browser console (which most
 * users never open) makes the app feel broken rather than informative.
 * The backend already returns clean, human-readable error messages (see
 * `app/utils/exceptions.py`); this component's only job is to display them.
 */
function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;

  return (
    <div className="error-banner" role="alert">
      <span className="error-banner__icon" aria-hidden="true">
        ⚠
      </span>
      <span className="error-banner__message">{message}</span>
      <button
        type="button"
        className="error-banner__dismiss"
        onClick={onDismiss}
        aria-label="Dismiss error"
      >
        ×
      </button>
    </div>
  );
}

export default ErrorBanner;
