# DocuMind AI — Frontend

A React (Vite) single-page app for the DocuMind AI RAG system. See the [root README](../README.md) for the full project overview, architecture, and setup instructions.

## Quick start

```bash
npm install
cp .env.example .env   # set VITE_API_BASE_URL to your backend's URL
npm run dev
```

## Project structure

```
src/
├── api/client.js       # Thin fetch() wrapper around the backend REST API
├── components/
│   ├── Sidebar.jsx          # Document upload + document list
│   ├── DocumentUpload.jsx   # Drag-and-drop / click-to-browse PDF upload zone
│   ├── DocumentList.jsx     # Uploaded documents with status, delete, re-index
│   ├── ChatPanel.jsx        # Message history + question input
│   ├── MessageBubble.jsx    # A single user/assistant chat message
│   ├── SourceList.jsx       # Expandable list of source chunks for an answer
│   ├── LoadingIndicator.jsx # Reusable "thinking…" animation
│   └── ErrorBanner.jsx      # Dismissible error banner
└── App.jsx              # Top-level state and orchestration
```

## Scripts

- `npm run dev` — start the Vite dev server with hot module reloading.
- `npm run build` — production build, output to `dist/`.
- `npm run preview` — preview the production build locally.
- `npm run lint` — run Oxlint.
