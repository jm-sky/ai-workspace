"""Text chunkers for RAG ingest: character-based and structure-aware markdown."""

import re

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_MARKER_RE = re.compile(r"^(```|~~~)")
_MARKDOWN_HINT_RE = re.compile(r"^#{1,6}\s|^```|^~~~|^\s*[-*]\s|^\s*\d+\.\s", re.MULTILINE)


def looks_like_markdown(text: str) -> bool:
    """Heuristic: ATX headings, fences, or list markers anywhere in the text."""
    return bool(_MARKDOWN_HINT_RE.search(text))


def split_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
    max_chunks: int = 200,
) -> list[str]:
    """Split text into overlapping character windows.

    Skips empty / whitespace-only segments. Hard-caps at ``max_chunks``.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")
    if max_chunks < 1:
        raise ValueError("max_chunks must be >= 1")

    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    step = chunk_size - overlap

    while start < length and len(chunks) < max_chunks:
        end = min(start + chunk_size, length)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start += step

    return chunks


def _parse_markdown_blocks(text: str) -> list[tuple[tuple[str, ...], str]]:
    """Split into (heading_path, block_text) pairs.

    A block is either a paragraph or a whole fenced code block (```/~~~ —
    never split mid-fence). Blank lines separate paragraphs.
    """
    lines = text.splitlines()
    heading_stack: list[tuple[int, str]] = []
    blocks: list[tuple[tuple[str, ...], str]] = []
    buffer: list[str] = []

    def flush() -> None:
        joined = "\n".join(buffer).strip()
        buffer.clear()
        if joined:
            blocks.append((tuple(title for _, title in heading_stack), joined))

    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_MARKER_RE.match(line.strip())

        if fence_match:
            flush()
            marker = fence_match.group(1)
            fence_lines = [line]
            index += 1
            while index < len(lines):
                fence_lines.append(lines[index])
                closed = lines[index].strip().startswith(marker)
                index += 1
                if closed:
                    break
            blocks.append((tuple(title for _, title in heading_stack), "\n".join(fence_lines)))
            continue

        heading_match = _ATX_HEADING_RE.match(line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            index += 1
            continue

        if line.strip() == "":
            flush()
        else:
            buffer.append(line)
        index += 1

    flush()
    return blocks


def _with_heading_prefix(path: tuple[str, ...], body: str) -> str:
    if not path:
        return body
    return f"{' > '.join(path)}\n\n{body}"


def split_markdown(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
    max_chunks: int = 200,
) -> list[str]:
    """Structure-aware chunker: splits on ATX headings / paragraphs, never
    breaking a fenced code block, and prefixes each chunk with its heading
    path (``"A > B"``). A single block longer than ``chunk_size`` falls back
    to :func:`split_text` for just that block.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")
    if max_chunks < 1:
        raise ValueError("max_chunks must be >= 1")

    cleaned = text.strip()
    if not cleaned:
        return []

    blocks = _parse_markdown_blocks(cleaned)
    chunks: list[str] = []
    current_path: tuple[str, ...] | None = None
    current_parts: list[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_parts, current_len, current_path
        if current_parts and current_path is not None and len(chunks) < max_chunks:
            chunks.append(_with_heading_prefix(current_path, "\n\n".join(current_parts)))
        current_parts = []
        current_len = 0

    for path, body in blocks:
        if len(chunks) >= max_chunks:
            break

        prefix_len = len(" > ".join(path)) + 2 if path else 0
        available = max(1, chunk_size - prefix_len)

        if len(body) > available:
            flush_current()
            current_path = None
            for piece in split_text(body, chunk_size=available, overlap=min(overlap, available - 1), max_chunks=max_chunks - len(chunks)):
                if len(chunks) >= max_chunks:
                    break
                chunks.append(_with_heading_prefix(path, piece))
            continue

        if current_path != path or current_len + len(body) + 2 > chunk_size:
            flush_current()
            current_path = path

        current_parts.append(body)
        current_len += len(body) + 2

    flush_current()
    return chunks[:max_chunks]
