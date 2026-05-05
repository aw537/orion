"""Tests for Inbox feature — parsing, upload, and history."""
import json
import pytest
import pytest_asyncio
from io import BytesIO

from app.services.inbox_service import parse_file


# ── Unit tests for inbox_service.parse_file ──────────────────────────────────

class TestParseFileMarkdown:
    def test_splits_by_headings(self):
        md = "## Section A\nContent for A.\n\n## Section B\nContent for B."
        chunks = parse_file("notes.md", md.encode())
        assert len(chunks) == 2
        assert "Section A" in chunks[0].content
        assert "Section B" in chunks[1].content

    def test_splits_by_paragraphs_when_no_headings(self):
        md = "First paragraph with enough text.\n\nSecond paragraph with enough text."
        chunks = parse_file("notes.md", md.encode())
        assert len(chunks) == 2

    def test_skips_short_chunks(self):
        md = "## A\nOk.\n\n## B\nThis is a longer paragraph that passes the minimum."
        chunks = parse_file("notes.md", md.encode())
        # "## A\nOk." is too short (< 20 chars)
        assert len(chunks) == 1
        assert "longer paragraph" in chunks[0].content

    def test_txt_treated_as_markdown(self):
        txt = "Paragraph one is long enough.\n\nParagraph two is also long enough."
        chunks = parse_file("file.txt", txt.encode())
        assert len(chunks) == 2

    def test_empty_file_returns_no_chunks(self):
        chunks = parse_file("empty.md", b"")
        assert chunks == []


class TestParseFileYaml:
    def test_splits_top_level_keys(self):
        content = "database: PostgreSQL with async\nframework: FastAPI with Starlette"
        chunks = parse_file("config.yaml", content.encode())
        assert len(chunks) == 2
        assert "database" in chunks[0].content
        assert "framework" in chunks[1].content

    def test_complex_values_serialized(self):
        content = "tools:\n  - docker\n  - kubernetes\nversion: 3"
        chunks = parse_file("stack.yml", content.encode())
        assert any("tools" in c.content for c in chunks)

    def test_invalid_yaml_single_chunk(self):
        content = "this: is: not: valid: yaml: {{{"
        chunks = parse_file("bad.yaml", content.encode())
        # Falls back to single chunk if content is long enough
        assert len(chunks) <= 1


class TestParseFileJson:
    def test_splits_top_level_keys(self):
        data = {"name": "Orion project for AI agents", "version": "0.1.0 beta release"}
        chunks = parse_file("data.json", json.dumps(data).encode())
        assert len(chunks) == 2

    def test_array_as_single_chunk(self):
        data = ["item one that is long enough", "item two that is long enough"]
        chunks = parse_file("list.json", json.dumps(data).encode())
        assert len(chunks) == 1

    def test_invalid_json_single_chunk(self):
        chunks = parse_file("bad.json", b"not json at all but long enough to pass")
        assert len(chunks) == 1


# ── Integration tests for inbox API endpoints ────────────────────────────────

@pytest.mark.asyncio
async def test_upload_unsupported_extension(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("doc.pdf", b"fake pdf content", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_markdown_file(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    md_content = "## Architecture\nOrion uses FastAPI and PostgreSQL.\n\n## Deployment\nDocker Compose orchestrates all services."
    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("notes.md", md_content.encode(), "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["chunks_total"] >= 2
    assert data["chunks_routed"] >= 2
    assert len(data["results"]) >= 2
    for r in data["results"]:
        assert "chunk_preview" in r
        assert "target_planet_name" in r


@pytest.mark.asyncio
async def test_upload_empty_file(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("empty.md", b"", "text/markdown")},
    )
    assert resp.status_code == 200
    assert resp.json()["chunks_total"] == 0


@pytest.mark.asyncio
async def test_inbox_history(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    md = "## Topic\nSome content that is long enough to be a chunk."
    await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("test.md", md.encode(), "text/markdown")},
    )

    resp = await client.get("/api/v1/inbox/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["filename"] == "test.md"


@pytest.mark.asyncio
async def test_inbox_planet_created_on_upload(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    md = "## Notes\nSomething worth remembering for later use."
    await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("notes.md", md.encode(), "text/markdown")},
    )

    resp = await client.get("/api/v1/planets")
    assert resp.status_code == 200
    planets = resp.json()
    inbox_planets = [p for p in planets if p.get("planet_type") == "inbox"]
    assert len(inbox_planets) == 1
    assert inbox_planets[0]["name"] == "Inbox"


@pytest.mark.asyncio
async def test_upload_json_file(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    data = json.dumps({"database": "PostgreSQL is used for persistence", "cache": "Redis handles session caching"})
    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("stack.json", data.encode(), "application/json")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_total"] == 2
    assert body["chunks_routed"] == 2
    assert any("database" in r["chunk_preview"].lower() for r in body["results"])


@pytest.mark.asyncio
async def test_upload_yaml_file(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    yaml_content = "framework: FastAPI with async support\ndatabase: PostgreSQL with SQLAlchemy"
    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("config.yaml", yaml_content.encode(), "text/yaml")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_total"] == 2
    assert body["chunks_routed"] == 2


@pytest.mark.asyncio
async def test_upload_file_too_large(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    # 11MB file exceeds 10MB limit
    big_content = b"x" * (11 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("huge.md", big_content, "text/markdown")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_inbox_history_ordering(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    # Upload two files
    await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("first.md", b"## First\nThis is the first uploaded file content.", "text/markdown")},
    )
    await client.post(
        "/api/v1/inbox/upload",
        files={"file": ("second.md", b"## Second\nThis is the second uploaded file content.", "text/markdown")},
    )

    resp = await client.get("/api/v1/inbox/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2
    filenames = [i["filename"] for i in items]
    assert "first.md" in filenames
    assert "second.md" in filenames


@pytest.mark.asyncio
async def test_inbox_planet_not_duplicated_on_multiple_uploads(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    md = "## Content\nLong enough chunk for the first upload."
    await client.post("/api/v1/inbox/upload", files={"file": ("a.md", md.encode(), "text/markdown")})
    await client.post("/api/v1/inbox/upload", files={"file": ("b.md", md.encode(), "text/markdown")})

    resp = await client.get("/api/v1/planets")
    planets = resp.json()
    inbox_planets = [p for p in planets if p.get("planet_type") == "inbox"]
    assert len(inbox_planets) == 1


@pytest.mark.asyncio
async def test_planet_list_includes_planet_type(client):
    resp = await client.post("/api/v1/onboarding/start", json={"role": "engineer"})
    assert resp.status_code in (200, 201)

    resp = await client.get("/api/v1/planets")
    assert resp.status_code == 200
    planets = resp.json()
    # All planets from onboarding should be "standard"
    for p in planets:
        assert "planet_type" in p
        assert p["planet_type"] == "standard"
