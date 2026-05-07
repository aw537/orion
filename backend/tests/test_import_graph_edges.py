"""Tests for co-chunk and wikilink stardust graph edge creation during import."""
import uuid
import tempfile
from collections import defaultdict
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.brain import StardustRelationship
from app.schemas.stardust import WriteReceipt
from app.services.import_service import (
    _bulk_insert_stardust_relationships,
    import_markdown_folder,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Long enough paragraph to force chunk_by_paragraph to split (> 2000 chars per paragraph)
# chunk_by_paragraph splits when len(current) + len(new_para) > max_tokens * 4 (default 2000)
_LONG = "This is a long test paragraph with many words to force chunking. " * 35  # ~2275 chars


def _receipt(stardust_id: str) -> WriteReceipt:
    return WriteReceipt(
        status="success", stardust_id=stardust_id,
        biome_id="b-test", planet_id="p-test",
    )


def _make_write_mock():
    """Returns an async write_stardust mock that assigns IDs based on filename + call order.

    IDs are <stem>-c0, <stem>-c1, ... so they're predictable regardless of file processing order.
    """
    counters: dict[str, int] = defaultdict(int)

    async def _mock(content, galaxy_id, filename=None, **kwargs):
        stem = Path(filename).stem if filename else "unknown"
        sid = f"{stem}-c{counters[stem]}"
        counters[stem] += 1
        return _receipt(sid)

    return _mock


@pytest_asyncio.fixture
async def import_db():
    """Full-schema in-memory SQLite DB for import tests."""
    engine = create_async_engine(
        TEST_DB_URL, echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(import_db):
    """import_db factory + pre-inserted Galaxy + Planet."""
    galaxy_id = str(uuid.uuid4())
    planet_id = str(uuid.uuid4())
    async with import_db() as db:
        from app.models.galaxy import Galaxy
        from app.models.planet import Planet
        db.add(Galaxy(
            id=galaxy_id, name="Test Galaxy",
            strength_score=0.5, total_nodes=0, schema_version="0.1.0",
        ))
        db.add(Planet(
            id=planet_id, galaxy_id=galaxy_id, name="Test Planet",
            stardust_count=0, health_status="healthy",
        ))
        await db.commit()
    return import_db, galaxy_id, planet_id


async def _rows(factory, rel_type=None):
    """Fetch all StardustRelationship rows, optionally filtered by type."""
    async with factory() as db:
        stmt = select(StardustRelationship)
        if rel_type:
            stmt = stmt.where(StardustRelationship.relationship_type == rel_type)
        return (await db.execute(stmt)).scalars().all()


# ── _bulk_insert_stardust_relationships ──────────────────────────────────────

class TestBulkInsertStardustRelationships:

    @pytest.mark.asyncio
    async def test_creates_expected_rows(self, import_db):
        pairs = [("s1", "t1"), ("s2", "t2"), ("s3", "t3")]
        with patch("app.services.import_service.async_session", import_db):
            await _bulk_insert_stardust_relationships("gid", pairs, "co_chunk")
        assert len(await _rows(import_db)) == 3

    @pytest.mark.asyncio
    async def test_correct_fields(self, import_db):
        with patch("app.services.import_service.async_session", import_db):
            await _bulk_insert_stardust_relationships("g1", [("src", "tgt")], "wikilink")
        row = (await _rows(import_db))[0]
        assert row.galaxy_id == "g1"
        assert row.source_stardust_id == "src"
        assert row.target_stardust_id == "tgt"
        assert row.relationship_type == "wikilink"
        assert row.created_by == "importer"

    @pytest.mark.asyncio
    async def test_empty_pairs_inserts_nothing(self, import_db):
        with patch("app.services.import_service.async_session", import_db):
            await _bulk_insert_stardust_relationships("gid", [], "co_chunk")
        assert len(await _rows(import_db)) == 0


# ── Co-chunk edges ───────────────────────────────────────────────────────────

class TestCoChunkEdges:

    @pytest.mark.asyncio
    async def test_two_chunks_produce_one_edge(self, seeded):
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc.md").write_text(f"{_LONG}\n\n{_LONG}")

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        rows = await _rows(factory, "co_chunk")
        assert len(rows) == 1
        assert {rows[0].source_stardust_id, rows[0].target_stardust_id} == {"doc-c0", "doc-c1"}

    @pytest.mark.asyncio
    async def test_three_chunks_produce_three_edges(self, seeded):
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc.md").write_text(f"{_LONG}\n\n{_LONG}\n\n{_LONG}")

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        rows = await _rows(factory, "co_chunk")
        assert len(rows) == 3  # C(3,2) = 3
        pairs = {frozenset([r.source_stardust_id, r.target_stardust_id]) for r in rows}
        assert pairs == {
            frozenset(["doc-c0", "doc-c1"]),
            frozenset(["doc-c0", "doc-c2"]),
            frozenset(["doc-c1", "doc-c2"]),
        }

    @pytest.mark.asyncio
    async def test_single_chunk_no_edges(self, seeded):
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc.md").write_text("Short single paragraph.")

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        assert len(await _rows(factory, "co_chunk")) == 0

    @pytest.mark.asyncio
    async def test_no_cross_file_co_chunk_edges(self, seeded):
        """Co-chunk edges must not cross file boundaries."""
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "alpha.md").write_text(f"{_LONG}\n\n{_LONG}")
            (Path(tmpdir) / "beta.md").write_text(f"{_LONG}\n\n{_LONG}")

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        rows = await _rows(factory, "co_chunk")
        # 1 edge within alpha + 1 edge within beta = 2 total, no cross-file edges
        assert len(rows) == 2
        for r in rows:
            pair = {r.source_stardust_id, r.target_stardust_id}
            is_alpha = pair == {"alpha-c0", "alpha-c1"}
            is_beta = pair == {"beta-c0", "beta-c1"}
            assert is_alpha or is_beta, f"Unexpected cross-file edge: {pair}"


# ── Wikilink edges ───────────────────────────────────────────────────────────

class TestWikilinkEdges:

    @pytest.mark.asyncio
    async def test_referenced_chunks_link_to_referencing_chunks(self, seeded):
        """wiki.md has 2 chunks; filea.md has [[wiki]] and 1 chunk.
        Expected wikilink edges: wiki-c0 → filea-c0, wiki-c1 → filea-c0."""
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "wiki.md").write_text(f"{_LONG}\n\n{_LONG}")
            (Path(tmpdir) / "filea.md").write_text(
                f"This file references [[wiki]] for more info. {_LONG}"
            )

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        rows = await _rows(factory, "wikilink")
        assert len(rows) == 2
        pairs = {(r.source_stardust_id, r.target_stardust_id) for r in rows}
        # wiki.md chunks → filea.md chunk (referenced → referencing)
        assert pairs == {("wiki-c0", "filea-c0"), ("wiki-c1", "filea-c0")}

    @pytest.mark.asyncio
    async def test_dangling_wikilink_creates_no_edges(self, seeded):
        """[[nonexistent]] in a file not imported → 0 wikilink edges."""
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "filea.md").write_text(
                f"This references [[nonexistent]] which is not here. {_LONG}"
            )

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        assert len(await _rows(factory, "wikilink")) == 0

    @pytest.mark.asyncio
    async def test_wikilinks_extracted_for_plain_format(self, seeded):
        """Wikilinks are extracted for plain (non-obsidian) format too."""
        factory, galaxy_id, planet_id = seeded

        with tempfile.TemporaryDirectory() as tmpdir:
            # No .obsidian dir → plain format
            (Path(tmpdir) / "source.md").write_text(
                f"References [[target]] for context. {_LONG}"
            )
            (Path(tmpdir) / "target.md").write_text(f"Target file content. {_LONG}")

            with (
                patch("app.services.import_service.async_session", factory),
                patch("app.services.import_service.stardust_service.write_stardust",
                      side_effect=_make_write_mock()),
                patch("app.services.import_service.nebula_service.log_event",
                      new=AsyncMock()),
            ):
                await import_markdown_folder(tmpdir, planet_id, galaxy_id)

        wikilink_rows = await _rows(factory, "wikilink")
        assert len(wikilink_rows) == 1
        edge = wikilink_rows[0]
        # target.md chunk (referenced) → source.md chunk (referencing)
        assert edge.source_stardust_id == "target-c0"
        assert edge.target_stardust_id == "source-c0"
