import { useCallback, useRef, useState } from "react";

/**
 * Drag-and-drop (and click-to-browse) PDF upload zone.
 *
 * WHY IS THIS COMPONENT "DUMB" (NO API CALLS OF ITS OWN)?
 * ----------------------------------------------------------------
 * This component's only responsibility is turning user interaction (drag,
 * drop, or file-picker selection) into a plain list of `File` objects and
 * handing them to `onFilesSelected`. It has no idea *what* happens to
 * those files next (uploading them, showing progress, updating a document
 * list). That logic lives in `App.jsx`. This separation - "presentational"
 * components vs. components that own state/side effects - keeps each
 * piece easy to reason about and reuse independently.
 *
 * Supports selecting multiple files at once, satisfying the project's
 * "multiple document support" requirement directly at the upload step.
 */
function DocumentUpload({ onFilesSelected, disabled }) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFiles = useCallback(
    (fileList) => {
      const files = Array.from(fileList).filter((file) =>
        file.name.toLowerCase().endsWith(".pdf")
      );
      if (files.length > 0) {
        onFilesSelected(files);
      }
    },
    [onFilesSelected]
  );

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDraggingOver(false);
    if (disabled) return;
    handleFiles(event.dataTransfer.files);
  };

  return (
    <div
      className={`upload-zone ${isDraggingOver ? "upload-zone--active" : ""} ${
        disabled ? "upload-zone--disabled" : ""
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDraggingOver(true);
      }}
      onDragLeave={() => setIsDraggingOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && fileInputRef.current?.click()}
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        multiple
        hidden
        disabled={disabled}
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = ""; // allow re-selecting the same file later
        }}
      />
      <span className="upload-zone__icon" aria-hidden="true">
        📄
      </span>
      <p className="upload-zone__title">Drop PDF files here or click to browse</p>
      <p className="upload-zone__hint">You can select multiple documents at once</p>
    </div>
  );
}

export default DocumentUpload;
