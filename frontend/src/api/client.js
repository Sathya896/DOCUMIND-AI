/**
 * A small, dependency-free wrapper around the browser's built-in `fetch`.
 *
 * WHY NOT USE A LIBRARY LIKE AXIOS?
 * -------------------------------------
 * `fetch` is available natively in every modern browser - no extra
 * dependency to install, audit, or keep updated. For a project this size,
 * a thin wrapper that adds JSON parsing and consistent error handling gets
 * us everything axios would give us, with zero added bundle size. This is
 * a deliberate "avoid unnecessary complexity" choice.
 *
 * WHY CENTRALISE THE BASE URL AND ERROR HANDLING HERE?
 * ------------------------------------------------------------
 * Every component that needs to talk to the backend imports functions from
 * this module instead of calling `fetch` directly. That means:
 * - The API's base URL (which differs between local dev and the deployed
 *   Vercel + Render setup) is configured in exactly one place, via the
 *   `VITE_API_BASE_URL` environment variable (see `.env.example`).
 * - Every caller gets the same error shape (an `Error` whose `.message` is
 *   the backend's human-readable `detail` field) instead of each component
 *   re-implementing response-checking and JSON-parsing logic.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_V1_PREFIX = "/api/v1";

/**
 * Perform a fetch call against the backend API and return parsed JSON.
 *
 * Throws an `Error` with a user-friendly message when the response is not
 * OK (status >= 400), extracting FastAPI's standard `{"detail": "..."}`
 * error shape when present.
 */
async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${API_V1_PREFIX}${path}`, {
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    });
  } catch {
    // A network-level failure (backend unreachable, CORS misconfiguration,
    // no internet) never reaches the `.ok` check below - fetch itself
    // throws. We convert that into the same user-facing error shape as an
    // HTTP error response, so calling components only need one code path.
    throw new Error("Could not reach the DocuMind AI server. Is the backend running?");
  }

  // A 204 No Content response (e.g. DELETE) has no body to parse.
  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message = data?.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return data;
}

// --- Documents ---

export function uploadDocument(file, { signal } = {}) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/documents/upload", { method: "POST", body: formData, signal });
}

export function listDocuments() {
  return request("/documents/");
}

export function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, { method: "DELETE" });
}

export function reindexDocument(documentId) {
  return request(`/documents/${documentId}/reindex`, { method: "POST" });
}

// --- Chat ---

export function askQuestion({ question, conversationId, documentIds }) {
  return request("/chat/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
      document_ids: documentIds ?? null,
    }),
  });
}

export function getConversation(conversationId) {
  return request(`/chat/conversations/${conversationId}`);
}
