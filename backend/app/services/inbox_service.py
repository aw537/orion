"""Inbox service — parse files into chunks and route to planets via stardust_service."""

import json
import logging
import re
import uuid
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)

# Minimum chunk size to avoid noise
MIN_CHUNK_LENGTH = 20


@dataclass
class Chunk:
    content: str
    context_tags: list[str]


def parse_file(filename: str, content_bytes: bytes) -> list[Chunk]:
    """Parse a file into chunks based on its extension."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    text = content_bytes.decode("utf-8", errors="ignore")

    if ext in (".md", ".txt"):
        return _chunk_markdown(text)
    elif ext in (".yaml", ".yml"):
        return _chunk_yaml(text)
    elif ext == ".json":
        return _chunk_json(text)
    return []


def _chunk_markdown(text: str) -> list[Chunk]:
    """Split markdown by headings (h1-h3) or double-newline paragraphs."""
    # Try heading-based splitting first
    sections = re.split(r"(?m)^(#{1,3}\s+.+)$", text)
    chunks: list[Chunk] = []

    if len(sections) > 2:
        # sections alternates: [preamble, heading, body, heading, body, ...]
        # Process preamble
        preamble = sections[0].strip()
        if preamble and len(preamble) >= MIN_CHUNK_LENGTH:
            chunks.append(Chunk(content=preamble, context_tags=["inbox-import"]))
        # Process heading+body pairs
        for i in range(1, len(sections) - 1, 2):
            heading = sections[i].strip()
            body = sections[i + 1].strip() if i + 1 < len(sections) else ""
            combined = f"{heading}\n{body}".strip()
            if len(combined) >= MIN_CHUNK_LENGTH:
                chunks.append(Chunk(content=combined, context_tags=["inbox-import"]))
    else:
        # Fallback: paragraph splitting
        paragraphs = re.split(r"\n\s*\n", text)
        for p in paragraphs:
            p = p.strip()
            if len(p) >= MIN_CHUNK_LENGTH:
                chunks.append(Chunk(content=p, context_tags=["inbox-import"]))

    return chunks


def _chunk_yaml(text: str) -> list[Chunk]:
    """Each top-level key becomes a chunk."""
    try:
        data = yaml.safe_load(text)
    except Exception:
        return [Chunk(content=text, context_tags=["inbox-import", "yaml"])] if len(text) >= MIN_CHUNK_LENGTH else []

    if not isinstance(data, dict):
        return [Chunk(content=text, context_tags=["inbox-import", "yaml"])] if len(text) >= MIN_CHUNK_LENGTH else []

    chunks: list[Chunk] = []
    for key, value in data.items():
        serialized = f"{key}: {json.dumps(value, default=str)}" if not isinstance(value, str) else f"{key}: {value}"
        if len(serialized) >= MIN_CHUNK_LENGTH:
            chunks.append(Chunk(content=serialized, context_tags=["inbox-import", "yaml"]))
    return chunks


def _chunk_json(text: str) -> list[Chunk]:
    """Each top-level key becomes a chunk."""
    try:
        data = json.loads(text)
    except Exception:
        return [Chunk(content=text, context_tags=["inbox-import", "json"])] if len(text) >= MIN_CHUNK_LENGTH else []

    if not isinstance(data, dict):
        # Array or scalar — treat as single chunk
        return [Chunk(content=text, context_tags=["inbox-import", "json"])] if len(text) >= MIN_CHUNK_LENGTH else []

    chunks: list[Chunk] = []
    for key, value in data.items():
        serialized = f"{key}: {json.dumps(value, default=str)}"
        if len(serialized) >= MIN_CHUNK_LENGTH:
            chunks.append(Chunk(content=serialized, context_tags=["inbox-import", "json"]))
    return chunks
