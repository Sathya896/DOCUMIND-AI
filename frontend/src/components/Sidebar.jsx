import DocumentList from "./DocumentList";
import DocumentUpload from "./DocumentUpload";

/**
 * Left-hand panel: upload new documents and manage previously uploaded ones.
 */
function Sidebar({
  documents,
  isLoadingDocuments,
  isUploading,
  onFilesSelected,
  selectedDocumentIds,
  onToggleSelected,
  onDelete,
  onReindex,
  pendingActionDocumentId,
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <h1 className="sidebar__title">
          <span aria-hidden="true">🧠</span> DocuMind AI
        </h1>
        <p className="sidebar__subtitle">RAG-powered document Q&amp;A</p>
      </div>

      <DocumentUpload onFilesSelected={onFilesSelected} disabled={isUploading} />

      <div className="sidebar__section-header">
        <h2>Your Documents</h2>
        {selectedDocumentIds.length > 0 && (
          <span className="sidebar__filter-badge">
            Searching {selectedDocumentIds.length} selected
          </span>
        )}
      </div>

      <DocumentList
        documents={documents}
        isLoading={isLoadingDocuments}
        selectedDocumentIds={selectedDocumentIds}
        onToggleSelected={onToggleSelected}
        onDelete={onDelete}
        onReindex={onReindex}
        pendingActionDocumentId={pendingActionDocumentId}
      />
    </aside>
  );
}

export default Sidebar;
