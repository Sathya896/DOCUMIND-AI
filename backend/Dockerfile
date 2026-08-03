# --- DocuMind AI backend container image ---
#
# WHY DOCKERIZE THE BACKEND?
# ------------------------------
# Render (and most modern cloud platforms) can build and run a plain
# Dockerfile directly, which guarantees the exact same Python version,
# system libraries, and dependency versions run in production as were
# tested locally - eliminating "works on my machine" surprises.
#
# WHY `python:3.12-slim` AS THE BASE IMAGE?
# ----------------------------------------------
# `slim` variants strip out documentation, compilers, and other build-time
# -only tooling that a running application doesn't need, keeping the final
# image smaller and reducing its attack surface, while still being a full
# Debian-based Python environment (unlike `alpine`, which uses musl libc
# and can cause subtle incompatibilities with compiled Python packages
# like `torch` and `faiss-cpu`).

FROM python:3.12-slim

# Prevents Python from buffering stdout/stderr, so log lines from Uvicorn
# and our application appear immediately in Render's log viewer instead of
# being held in a buffer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first, separately from application code. Docker
# caches each instruction as a layer; as long as `requirements.txt` doesn't
# change, this (slow, because of torch/faiss) layer is reused on every
# subsequent build, so only code changes trigger a fast rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# These directories are created by `app/config/settings.py` at import time
# too, but declaring them here documents intent and ensures they exist even
# before the app's first import (e.g. if a volume is mounted over them).
RUN mkdir -p uploads vectorstore data

EXPOSE 8000

# Render sets the $PORT environment variable dynamically; we honour it via
# a shell-form CMD so the variable is expanded at container start time.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
