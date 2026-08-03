import { useState } from "react";

/**
 * Displays the source chunks an assistant answer was grounded in.
 *
 * WHY SHOW SOURCES AT ALL?
 * ------------------------------
 * This is arguably the most important trust-building feature of a RAG
 * system: it lets the user *verify* an answer against the original text,
 * rather than taking the LLM's word for it. Showing the document name,
 * page number, and the exact retrieved passage (plus its similarity score)
 * turns the assistant from a black box into something a user can audit.
 */
function SourceList({ sources }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="source-list">
      <button
        type="button"
        className="source-list__toggle"
        onClick={() => setIsExpanded((value) => !value)}
      >
        {isExpanded ? "▾" : "▸"} {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>

      {isExpanded && (
        <ul className="source-list__items">
          {sources.map((source, index) => (
            <li key={`${source.document_id}-${index}`} className="source-item">
              <div className="source-item__header">
                <span className="source-item__document">📄 {source.document_name}</span>
                {source.page_number != null && (
                  <span className="source-item__page">page {source.page_number}</span>
                )}
                <span className="source-item__score">
                  {Math.round(source.relevance_score * 100)}% match
                </span>
              </div>
              <p className="source-item__snippet">{source.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SourceList;
