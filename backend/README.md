# DocuMind AI — Backend

A FastAPI backend implementing a Retrieval-Augmented Generation (RAG) pipeline for PDF question-answering. See the [root README](../README.md) for the full project overview, architecture diagram, and API reference.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`

## Run the tests

```bash
pytest -q
```

## Project structure

```
app/
├── main.py       # FastAPI app wiring: CORS, exception handlers, routers, lifespan
├── routes/       # HTTP layer only - documents, chat, health
├── services/     # Business logic - pdf, chunking, embedding, vector store, llm, rag, document
├── models/       # SQLAlchemy ORM models + Pydantic request/response schemas
├── utils/        # Logging, custom exceptions, upload validation
└── config/       # Typed settings (pydantic-settings)
tests/            # Unit + API integration tests (pytest)
```

Every service module has a module-level docstring explaining *why* its approach was chosen (which library, which algorithm, which trade-offs) — read those first if you're learning RAG/backend development from this codebase.
