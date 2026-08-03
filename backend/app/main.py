"""
Application entry point.

WHAT DOES THIS FILE DO?
----------------------------
This is where the FastAPI `app` object is created and wired up:
* CORS middleware (so the React frontend, running on a different origin,
  is allowed to call this API from the browser).
* Global exception handlers (translate our domain exceptions into clean
  JSON error responses, instead of leaking Python tracebacks to clients).
* Route registration (each feature area's router, from `app/routes/`).
* Startup logic (initialise the database).

WHY IS THIS FILE SO SMALL?
-------------------------------
Deliberately so. `main.py` should only ever contain *wiring* - no business
logic. Anyone opening this file for the first time should be able to see,
at a glance, everything the application is made of and where to go look
for the actual implementation of each piece.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.models.database import init_db
from app.models.schemas import ErrorResponse
from app.routes import chat, documents, health
from app.utils.exceptions import DocuMindError
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup/shutdown logic around the app's lifetime.

    `init_db()` creates any missing SQLite tables before the app starts
    accepting requests, so the very first request never races a
    not-yet-created table.
    """
    logger.info("Starting %s (environment=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    init_db()
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "An AI-powered document question-answering system built with "
        "Retrieval-Augmented Generation (RAG). Upload PDFs and ask "
        "questions answered strictly from their contents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (Cross-Origin Resource Sharing): browsers block JavaScript from
# calling an API on a different origin (scheme+host+port) than the page
# that loaded it, unless that API explicitly allows it via these headers.
# Our React app runs on a different origin (e.g. localhost:5173) than this
# API (e.g. localhost:8000), so without this middleware every request from
# the browser would be rejected before it even reaches our route handlers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DocuMindError)
async def documind_error_handler(request: Request, exc: DocuMindError) -> JSONResponse:
    """Catch-all safety net for any DocuMindError raised without being
    translated to an HTTPException by a route handler.

    Individual routes already catch specific exceptions to choose the most
    accurate HTTP status code (400 vs 404 vs 503, etc.) - this handler
    exists so that if a *new* exception subtype is added later and a route
    forgets to catch it, the client still gets a clean JSON error instead
    of an unhandled-exception stack trace (which FastAPI would otherwise
    turn into a generic, unhelpful 500 response).
    """
    logger.error("Unhandled DocuMindError: %s", exc.message)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=type(exc).__name__, detail=exc.message).model_dump(),
    )


app.include_router(health.router)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    """Landing route - points visitors to the interactive API docs."""
    return {"message": f"Welcome to {settings.APP_NAME}. Visit /docs for the API reference."}
