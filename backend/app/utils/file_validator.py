"""
Upload validation helpers.

WHY VALIDATE UPLOADS EXPLICITLY?
----------------------------------
Never trust client input. A malicious or careless client could send:
* A file with a `.pdf` extension that isn't actually a PDF.
* An empty file.
* A huge file that exhausts disk space or memory.

We defend against these with three checks, applied in `pdf_service.py`
before anything is written to disk:

1. Extension check   - cheap, first line of defense.
2. Magic-byte check   - every real PDF file starts with the bytes `%PDF-`.
   Checking this catches files that were merely *renamed* to `.pdf`.
3. Size check         - enforced against `MAX_UPLOAD_SIZE_MB` from settings.

This is a common real-world security practice: never rely on a file
extension alone to determine file type.
"""

from app.config.settings import settings
from app.utils.exceptions import InvalidFileError

PDF_MAGIC_BYTES = b"%PDF-"


def validate_filename(filename: str | None) -> str:
    """Ensure the uploaded file has an allowed extension.

    Returns the validated filename so callers can use it without re-checking
    for `None`.
    """
    if not filename:
        raise InvalidFileError("Uploaded file is missing a filename.")

    lowered = filename.lower()
    if not any(lowered.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        raise InvalidFileError(f"Unsupported file type. Allowed types: {allowed}")

    return filename


def validate_file_size(size_in_bytes: int) -> None:
    """Ensure the file does not exceed the configured maximum size."""
    if size_in_bytes <= 0:
        raise InvalidFileError("Uploaded file is empty.")

    if size_in_bytes > settings.max_upload_size_bytes:
        raise InvalidFileError(
            f"File exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )


def validate_pdf_signature(file_bytes: bytes) -> None:
    """Ensure the file actually starts with the PDF magic bytes.

    This protects against files that were renamed to `.pdf` but are not
    real PDFs (e.g. a `.txt` file renamed to `document.pdf`).
    """
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise InvalidFileError("File content does not match a valid PDF file.")
