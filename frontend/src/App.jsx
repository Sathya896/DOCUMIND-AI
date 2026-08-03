import { useCallback, useEffect, useState } from "react";

import {
  askQuestion,
  deleteDocument,
  getConversation,
  listDocuments,
  reindexDocument,
  uploadDocument,
} from "./api/client";
import ChatPanel from "./components/ChatPanel";
import ErrorBanner from "./components/ErrorBanner";
import Sidebar from "./components/Sidebar";

// Persisting the active conversation ID in `localStorage` (rather than only
// in React state) means refreshing the browser tab doesn't lose the
// conversation - we can fetch its full message history back from the
// backend (which already persists it - see `models/chat.py`) and pick up
// right where the user left off. This is a minimal, dependency-free way to
// give a single-page app "memory" across page reloads.
const CONVERSATION_STORAGE_KEY = "documind:conversationId";

/**
 * The top-level component: owns all shared application state and wires the
 * sidebar (document management) to the chat panel (question answering).
 *
 * WHY KEEP STATE HERE INSTEAD OF SPREADING IT ACROSS COMPONENTS?
 * -----------------------------------------------------------------------
 * `documents` and `messages` are needed by more than one component (e.g.
 * the chat panel needs to know if any document is indexed yet; the
 * sidebar's checkboxes need to feed into which documents the chat searches).
 * React's convention for state shared between siblings is to "lift it up"
 * to their closest common ancestor - this component - and pass it down as
 * props. For an app this size, this plain `useState`-based approach is
 * simpler and easier to follow than introducing a state-management library
 * (Redux, Zustand, etc.), which would be unnecessary complexity here.
 */
function App() {
  const [documents, setDocuments] = useState([]);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [pendingActionDocumentId, setPendingActionDocumentId] = useState(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([]);

  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isAsking, setIsAsking] = useState(false);

  const [errorMessage, setErrorMessage] = useState(null);

  const refreshDocuments = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data.documents);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  // On first load, try to restore the previous conversation (if any) from
  // the backend so a page refresh doesn't wipe out the user's chat history.
  useEffect(() => {
    const savedConversationId = localStorage.getItem(CONVERSATION_STORAGE_KEY);
    if (!savedConversationId) return;

    getConversation(Number(savedConversationId))
      .then((conversation) => {
        setConversationId(conversation.id);
        setMessages(
          conversation.messages.map((message) => ({
            id: crypto.randomUUID(),
            role: message.role,
            content: message.content,
            sources: message.sources,
          }))
        );
      })
      .catch(() => {
        // The saved conversation may no longer exist (e.g. after a backend
        // database reset) - silently start fresh instead of showing an
        // error for something the user never directly asked for.
        localStorage.removeItem(CONVERSATION_STORAGE_KEY);
      });
  }, []);

  // Documents take a few seconds to move from "processing" to "indexed".
  // Polling every few seconds (only while something is still processing)
  // keeps the sidebar's status badges up to date without needing
  // WebSockets - a reasonable trade-off for a project at this scale.
  useEffect(() => {
    const hasProcessingDocument = documents.some((doc) => doc.status === "processing");
    if (!hasProcessingDocument) return;

    const intervalId = setInterval(refreshDocuments, 3000);
    return () => clearInterval(intervalId);
  }, [documents, refreshDocuments]);

  const handleFilesSelected = async (files) => {
    setIsUploading(true);
    setErrorMessage(null);

    // Uploading files one at a time (rather than all in parallel) means a
    // failure on one file surfaces a clear, single error message instead
    // of several overlapping ones, and avoids overwhelming the backend
    // with many simultaneous embedding jobs when a user drops in a batch
    // of large PDFs.
    for (const file of files) {
      try {
        await uploadDocument(file);
      } catch (error) {
        setErrorMessage(`Failed to upload "${file.name}": ${error.message}`);
      }
    }

    setIsUploading(false);
    refreshDocuments();
  };

  const handleDelete = async (documentId) => {
    setPendingActionDocumentId(documentId);
    setErrorMessage(null);
    try {
      await deleteDocument(documentId);
      setSelectedDocumentIds((ids) => ids.filter((id) => id !== documentId));
      await refreshDocuments();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setPendingActionDocumentId(null);
    }
  };

  const handleReindex = async (documentId) => {
    setPendingActionDocumentId(documentId);
    setErrorMessage(null);
    try {
      await reindexDocument(documentId);
      await refreshDocuments();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setPendingActionDocumentId(null);
    }
  };

  const handleToggleSelected = (documentId) => {
    setSelectedDocumentIds((ids) =>
      ids.includes(documentId) ? ids.filter((id) => id !== documentId) : [...ids, documentId]
    );
  };

  const handleAsk = async (question) => {
    setErrorMessage(null);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: question }]);
    setIsAsking(true);

    try {
      const response = await askQuestion({
        question,
        conversationId,
        documentIds: selectedDocumentIds.length > 0 ? selectedDocumentIds : null,
      });
      setConversationId(response.conversation_id);
      localStorage.setItem(CONVERSATION_STORAGE_KEY, String(response.conversation_id));
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
        },
      ]);
    } catch (error) {
      setErrorMessage(error.message);
      // Remove the just-added user message's "pending answer" state by
      // showing the error inline too, so the failed question doesn't look
      // like it's still silently loading forever.
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", content: `⚠ ${error.message}`, sources: [] },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([]);
    localStorage.removeItem(CONVERSATION_STORAGE_KEY);
  };

  const hasIndexedDocuments = documents.some((doc) => doc.status === "indexed");

  return (
    <div className="app-layout">
      <Sidebar
        documents={documents}
        isLoadingDocuments={isLoadingDocuments}
        isUploading={isUploading}
        onFilesSelected={handleFilesSelected}
        selectedDocumentIds={selectedDocumentIds}
        onToggleSelected={handleToggleSelected}
        onDelete={handleDelete}
        onReindex={handleReindex}
        pendingActionDocumentId={pendingActionDocumentId}
      />

      <main className="main-panel">
        <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        <ChatPanel
          messages={messages}
          isAsking={isAsking}
          onAsk={handleAsk}
          hasIndexedDocuments={hasIndexedDocuments}
          onNewConversation={handleNewConversation}
        />
      </main>
    </div>
  );
}

export default App;
