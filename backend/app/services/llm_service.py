"""
Talking to the LLM via Ollama.

WHAT IS OLLAMA?
--------------------
Ollama is a tool that runs open-weight large language models (Llama,
Qwen, Mistral, etc.) locally on your own machine and exposes them through a
simple REST API on `localhost:11434`. For a learning/portfolio project,
this is preferable to a paid cloud LLM API during development: it's free,
works offline, and keeps document contents on your own machine - no data
leaves your computer. The same `LLMService` abstraction below would work
unchanged against a cloud provider later; only `settings.OLLAMA_BASE_URL`
and the request/response shape would need to change.

WHY `httpx` INSTEAD OF `requests`?
----------------------------------------
`httpx` supports `async`/`await` natively. FastAPI route handlers are
`async def`, and calling a *blocking* HTTP library like `requests` from an
async function would freeze the entire event loop for every other
concurrent request while waiting on the LLM (which can take many seconds).
`httpx.AsyncClient` lets other requests keep being served while we wait for
Ollama to respond.

WHY WRAP FAILURES IN `LLMGenerationError`?
------------------------------------------------
Ollama might not be running, the model might not be pulled yet, or the
request might time out. Each of these should surface to the user as a
clear "the AI service is unavailable" message - not a raw connection-reset
stack trace. Catching specific `httpx` exceptions here and re-raising our
own domain exception keeps that translation logic in one place.
"""

import httpx

from app.config.settings import settings
from app.utils.exceptions import LLMGenerationError
from app.utils.logger import get_logger

logger = get_logger(__name__)

OLLAMA_GENERATE_ENDPOINT = "/api/generate"


async def generate_answer(prompt: str) -> str:
    """Send a prompt to the local Ollama server and return the model's reply.

    We use Ollama's `/api/generate` endpoint with `stream=False`, which
    waits for the full response and returns it as a single JSON object.
    Streaming (token-by-token) is a natural future enhancement for a more
    responsive UI, but a single blocking call is simpler to reason about
    for a first implementation - and the frontend's loading indicator
    covers the wait.
    """
    request_payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        # Lower temperature = more deterministic, factual answers - what we
        # want for a document Q&A system, as opposed to creative writing.
        "options": {"temperature": 0.2},
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.OLLAMA_BASE_URL,
            timeout=settings.OLLAMA_REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(OLLAMA_GENERATE_ENDPOINT, json=request_payload)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError as exc:
        logger.error("Could not connect to Ollama at %s", settings.OLLAMA_BASE_URL)
        raise LLMGenerationError(
            "Could not connect to the local LLM server (Ollama). "
            "Make sure Ollama is running (`ollama serve`) and the model is pulled "
            f"(`ollama pull {settings.OLLAMA_MODEL}`)."
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama returned an error status: %s", exc.response.text)
        raise LLMGenerationError("The LLM server returned an error while generating a response.") from exc
    except httpx.TimeoutException as exc:
        logger.error("Ollama request timed out after %s seconds", settings.OLLAMA_REQUEST_TIMEOUT_SECONDS)
        raise LLMGenerationError("The LLM took too long to respond. Try a shorter question or a smaller model.") from exc

    answer = data.get("response", "").strip()
    if not answer:
        raise LLMGenerationError("The LLM returned an empty response.")

    return answer
