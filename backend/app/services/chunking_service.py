"""
Splitting extracted text into retrieval-sized chunks.

WHY CHUNK AT ALL?
---------------------
Embedding models (and LLM context windows) work best on small, focused
pieces of text. Embedding an entire 50-page PDF as one vector would blur
together many unrelated topics into a single point in vector space, making
semantic search nearly useless - a query about "page 40's conclusion"
would retrieve the *whole document*, not the relevant paragraph. Splitting
into chunks lets each vector represent one coherent idea, so search can
pinpoint the specific passage that actually answers a question.

WHAT IS `RecursiveCharacterTextSplitter`?
----------------------------------------------
It's a utility from the LangChain ecosystem (`langchain-text-splitters`)
that splits text by trying a list of separators in order of preference:
paragraphs (`\\n\\n`), then lines (`\\n`), then sentences/words, then
individual characters - only falling back to a cruder separator if the
chunk is still too big. This "recursive" strategy keeps chunks as
semantically coherent as possible (e.g. it strongly prefers to cut between
paragraphs rather than mid-sentence).

WHY `CHUNK_OVERLAP`?
-------------------------
If a sentence important to answering a question happens to fall right on
the boundary between two chunks, a hard cut with no overlap could split
that sentence's meaning across two "orphaned" halves - and semantic search
might not retrieve either half well. A small overlap (e.g. 200 of 1000
characters) duplicates the tail of one chunk at the start of the next,
so boundary-spanning ideas remain intact in at least one full chunk.
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.settings import settings


@dataclass(frozen=True)
class TextChunk:
    """A single chunk of text plus the page number it came from."""

    content: str
    page_number: int  # 1-indexed, for user-facing display


def chunk_pages(pages_text: list[str]) -> list[TextChunk]:
    """Split each page's text into overlapping chunks.

    We split page-by-page (rather than joining all pages into one string
    first) so every resulting chunk can be reliably attributed to the page
    it came from. The trade-off is that a chunk will never span two pages -
    an acceptable simplification, since `CHUNK_SIZE` is usually smaller than
    a full page of text anyway.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[TextChunk] = []
    for page_index, page_text in enumerate(pages_text, start=1):
        if not page_text.strip():
            continue  # skip blank pages (e.g. cover pages, dividers)

        for piece in splitter.split_text(page_text):
            cleaned = piece.strip()
            if cleaned:
                chunks.append(TextChunk(content=cleaned, page_number=page_index))

    return chunks
