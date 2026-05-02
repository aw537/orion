"""TDD tests for format-aware markdown import.

Tests the new pure functions: format detection, Obsidian wikilink extraction,
CLAUDE.md parsing, and GBrain frontmatter mapping.
"""
import os
import pytest
import tempfile
from pathlib import Path
from app.services.import_service import (
    detect_import_format,
    extract_wikilinks,
    parse_claude_md,
    parse_gbrain_frontmatter,
    parse_frontmatter,
)


# ── Format detection ────────────────────────────────────────────────────────

class TestDetectImportFormat:
    def test_obsidian_vault(self, tmp_path):
        (tmp_path / ".obsidian").mkdir()
        (tmp_path / "note.md").write_text("# Hello")
        assert detect_import_format(str(tmp_path)) == "obsidian"

    def test_claude_md_file(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\n- Do this")
        assert detect_import_format(str(tmp_path)) == "claude"

    def test_gbrain_markers(self, tmp_path):
        (tmp_path / "note.md").write_text("---\ncognitive_mode: analytical\nconfidence: 0.9\n---\nContent")
        assert detect_import_format(str(tmp_path)) == "gbrain"

    def test_plain_folder(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Just a readme")
        assert detect_import_format(str(tmp_path)) == "plain"

    def test_empty_folder(self, tmp_path):
        assert detect_import_format(str(tmp_path)) == "plain"

    def test_obsidian_takes_priority_over_claude(self, tmp_path):
        """If both .obsidian/ and CLAUDE.md exist, Obsidian wins."""
        (tmp_path / ".obsidian").mkdir()
        (tmp_path / "CLAUDE.md").write_text("rules")
        assert detect_import_format(str(tmp_path)) == "obsidian"


# ── Obsidian wikilink extraction ────────────────────────────────────────────

class TestExtractWikilinks:
    def test_basic_wikilink(self):
        links = extract_wikilinks("See [[FastAPI]] for details.")
        assert links == ["FastAPI"]

    def test_multiple_wikilinks(self):
        links = extract_wikilinks("Uses [[FastAPI]] and [[PostgreSQL]] with [[Redis]].")
        assert set(links) == {"FastAPI", "PostgreSQL", "Redis"}

    def test_aliased_wikilink(self):
        links = extract_wikilinks("See [[FastAPI|the framework]] for details.")
        assert links == ["FastAPI"]

    def test_no_wikilinks(self):
        links = extract_wikilinks("No links here.")
        assert links == []

    def test_wikilink_with_heading(self):
        links = extract_wikilinks("See [[Architecture#Auth]] section.")
        assert links == ["Architecture"]

    def test_deduplicates(self):
        links = extract_wikilinks("[[FastAPI]] is great. I love [[FastAPI]].")
        assert links == ["FastAPI"]

    def test_ignores_code_blocks(self):
        text = "```\n[[not a link]]\n```\nBut [[real link]] is."
        links = extract_wikilinks(text)
        assert links == ["real link"]


# ── CLAUDE.md parsing ───────────────────────────────────────────────────────

class TestParseClaudeMd:
    def test_basic_rules(self):
        content = "# CLAUDE.md\n\n- Always use TypeScript\n- Never use var\n- Prefer const over let"
        records = parse_claude_md(content)
        assert len(records) >= 3
        assert all(r["gravity"] == "GALAXY" for r in records)
        assert all(r["confidence"] >= 0.9 for r in records)

    def test_sections_become_tags(self):
        content = "# Code Style\n\n- Use 2-space indent\n\n# Architecture\n\n- Use hexagonal architecture"
        records = parse_claude_md(content)
        style_records = [r for r in records if "Code Style" in r.get("tags", [])]
        arch_records = [r for r in records if "Architecture" in r.get("tags", [])]
        assert len(style_records) >= 1
        assert len(arch_records) >= 1

    def test_empty_content(self):
        assert parse_claude_md("") == []

    def test_paragraph_rules(self):
        content = "# Rules\n\nWe use FastAPI for all backend services.\nThis is a firm decision."
        records = parse_claude_md(content)
        assert len(records) >= 1
        assert any("FastAPI" in r["content"] for r in records)


# ── GBrain frontmatter mapping ─────────────────────────────────────────────

class TestParseGbrainFrontmatter:
    def test_maps_cognitive_mode(self):
        meta = {"cognitive_mode": "analytical", "confidence": "0.85", "tags": ["auth", "security"]}
        result = parse_gbrain_frontmatter(meta, "Auth uses JWT tokens")
        assert result["region"] == "analytical"
        assert result["confidence"] == 0.85
        assert result["tags"] == ["auth", "security"]

    def test_maps_gravity(self):
        meta = {"gravity": "PLANET", "cognitive_mode": "procedural"}
        result = parse_gbrain_frontmatter(meta, "Deploy process")
        assert result["gravity"] == "PLANET"

    def test_defaults_without_gbrain_fields(self):
        meta = {"title": "Just a note"}
        result = parse_gbrain_frontmatter(meta, "Regular content")
        assert result["region"] == "contextual"
        assert result["confidence"] == 0.5
        assert result["gravity"] == "BIOME"

    def test_maps_reasoning(self):
        meta = {"cognitive_mode": "analytical", "reasoning": "Evaluated 3 options"}
        result = parse_gbrain_frontmatter(meta, "Chose FastAPI")
        assert result["reasoning"] == "Evaluated 3 options"
