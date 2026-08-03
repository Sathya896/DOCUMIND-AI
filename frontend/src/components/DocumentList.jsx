import LoadingIndicator from "./LoadingIndicator";

/**
 * Renders the list of uploaded documents with their indexing status and
 * per-document actions (delete, re-index) plus a checkbox to restrict the
 * chat's search scope to specific documents.
 *
 * WHY LET USERS RESTRICT WHICH DOCUMENTS ARE SEARCHED?
 * ------------------------------------------------------------
 * With several unrelated PDFs uploaded (e.g. a resume and a research
 * paper), a user often wants to ask a question about just *one* of them.
 * Passing `document_ids` through to `POST /chat/ask` (see
 * `rag_service.py`'s `_retrieve_relevant_chunks`) lets semantic search
 * ignore irrelevant documents entirely, which both improves answer
 * relevance and lets the UI show "asking within: report.pdf" for clarity.
 */
function DocumentList({
  documents,
  isLoading,
  selectedDocumentIds,
  onToggleSelected,
  onDelete,
  onReindex,
  pendingActionDocumentId,
}) {
  if (isLoading) {
    return (
      <div className="document-list__empty">
        <LoadingIndicator label="Loading documents" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="document-list__empty">
        <p>No documents uploaded yet.</p>
        <p className="document-list__empty-hint">Upload a PDF above to get started.</p>
      </div>
    );
  }

  return (
    <ul className="document-list">
      {documents.map((document) => {
        const isSelected = selectedDocumentIds.includes(document.id);
        const isBusy = pendingActionDocumentId === document.id;

        return (
          <li key={document.id} className="document-item">
            <label className="document-item__select" title="Restrict chat to this document">
              <input
                type="checkbox"
                checked={isSelected}
                disabled={document.status !== "indexed"}
                onChange={() => onToggleSelected(document.id)}
              />
            </label>

            <div className="document-item__info">
              <span className="document-item__name" title={document.filename}>
                {document.filename}
              </span>
              <span className="document-item__meta">
                <StatusBadge status={document.status} />
                {document.status === "indexed" && (
                  <span className="document-item__stats">
                    {document.page_count} pages · {document.chunk_count} chunks
                  </span>
                )}
              </span>
            </div>

            <div className="document-item__actions">
              <button
                type="button"
                className="icon-button"
                title="Re-index this document"
                disabled={isBusy}
                onClick={() => onReindex(document.id)}
              >
                ↻
              </button>
              <button
                type="button"
                className="icon-button icon-button--danger"
                title="Delete this document"
                disabled={isBusy}
                onClick={() => onDelete(document.id)}
              >
                🗑
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

const STATUS_LABELS = {
  pending: "Pending",
  processing: "Processing…",
  indexed: "Indexed",
  failed: "Failed",
};

function StatusBadge({ status }) {
  return <span className={`status-badge status-badge--${status}`}>{STATUS_LABELS[status] || status}</span>;
}

export default DocumentList;
