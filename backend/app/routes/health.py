"""
Health check endpoint.

WHY HAVE A DEDICATED /health ROUTE?
-----------------------------------------
Deployment platforms (Render, Kubernetes, load balancers, uptime monitors)
periodically ping a lightweight endpoint to decide whether an instance is
alive and should keep receiving traffic. It must respond instantly and
without side effects - it should NOT touch the database, FAISS, or the LLM,
because we want it to report the *process* is up even if a downstream
dependency is temporarily degraded (those get their own, more detailed
checks if needed later).
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Simple liveness probe used by deployment platforms and monitoring."""
    return {"status": "ok"}
