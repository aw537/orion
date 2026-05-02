"""Unit tests for import_service pure functions — frontmatter parsing, biome inference, chunking."""
import pytest
from app.services.import_service import parse_frontmatter, infer_biome_from_path, chunk_by_paragraph


# --- Frontmatter parsing ---

class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        content = "---\ntitle: My Doc\nauthor: Alice\n---\n\nBody content here."
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "My Doc"
        assert meta["author"] == "Alice"
        assert "Body content here." in body

    def test_tags_as_list(self):
        content = "---\ntags: [python, backend, api]\n---\n\nBody."
        meta, body = parse_frontmatter(content)
        assert meta["tags"] == ["python", "backend", "api"]

    def test_tags_as_single_value(self):
        content = "---\ntags: python\n---\n\nBody."
        meta, body = parse_frontmatter(content)
        assert meta["tags"] == ["python"]

    def test_tags_with_quotes(self):
        content = '---\ntags: ["python", "backend"]\n---\n\nBody.'
        meta, body = parse_frontmatter(content)
        assert "python" in meta["tags"]
        assert "backend" in meta["tags"]

    def test_empty_tags(self):
        content = "---\ntags: \n---\n\nBody."
        meta, body = parse_frontmatter(content)
        assert meta["tags"] == []

    def test_no_frontmatter(self):
        content = "Just a regular markdown file.\n\nWith paragraphs."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_unclosed_frontmatter(self):
        content = "---\ntitle: Broken\nNo closing delimiter"
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_empty_content(self):
        meta, body = parse_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_frontmatter_only(self):
        content = "---\ntitle: Only Meta\n---\n"
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "Only Meta"
        assert body == ""

    def test_quoted_values(self):
        content = '---\ntitle: "My Title"\nauthor: \'Bob\'\n---\n\nBody.'
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "My Title"
        assert meta["author"] == "Bob"

    def test_colon_in_value(self):
        content = "---\ntitle: My Doc: A Subtitle\n---\n\nBody."
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "My Doc: A Subtitle"


# --- Biome inference from path ---

class TestInferBiomeFromPath:
    def test_subfolder_becomes_biome(self):
        assert infer_biome_from_path("/root/project/notes/file.md", "/root/project") == "Notes"

    def test_nested_uses_first_folder(self):
        assert infer_biome_from_path("/root/project/backend/services/auth.md", "/root/project") == "Backend"

    def test_root_file_is_general(self):
        assert infer_biome_from_path("/root/project/README.md", "/root/project") == "General"

    def test_underscores_to_spaces(self):
        assert infer_biome_from_path("/root/my_project/file.md", "/root") == "My Project"

    def test_hyphens_to_spaces(self):
        assert infer_biome_from_path("/root/side-projects/file.md", "/root") == "Side Projects"

    def test_title_case(self):
        assert infer_biome_from_path("/root/engineering/file.md", "/root") == "Engineering"


# --- Paragraph chunking ---

class TestChunkByParagraph:
    def test_single_paragraph(self):
        text = "A short paragraph."
        chunks = chunk_by_paragraph(text)
        assert len(chunks) == 1
        assert chunks[0] == "A short paragraph."

    def test_multiple_paragraphs_fit(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_by_paragraph(text, max_tokens=500)
        assert len(chunks) == 1  # All fit in one chunk
        assert "Paragraph one." in chunks[0]
        assert "Paragraph three." in chunks[0]

    def test_paragraphs_split_at_boundary(self):
        # Each paragraph ~20 chars, max_tokens=5 means ~20 chars limit
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."
        chunks = chunk_by_paragraph(text, max_tokens=5)
        assert len(chunks) >= 2

    def test_empty_string(self):
        assert chunk_by_paragraph("") == []

    def test_whitespace_only(self):
        assert chunk_by_paragraph("   \n\n   ") == []

    def test_single_long_paragraph(self):
        text = "A" * 3000
        chunks = chunk_by_paragraph(text, max_tokens=500)
        assert len(chunks) >= 1
        # First chunk should contain the content
        assert len(chunks[0]) > 0

    def test_preserves_content(self):
        text = "Alpha content.\n\nBeta content.\n\nGamma content."
        chunks = chunk_by_paragraph(text, max_tokens=500)
        combined = " ".join(chunks)
        assert "Alpha" in combined
        assert "Beta" in combined
        assert "Gamma" in combined

    def test_strips_empty_paragraphs(self):
        text = "Content.\n\n\n\n\n\nMore content."
        chunks = chunk_by_paragraph(text)
        assert len(chunks) == 1
        assert "Content." in chunks[0]
        assert "More content." in chunks[0]

    def test_respects_token_limit(self):
        # 10 tokens * 4 chars = 40 chars max per chunk
        paras = [f"Paragraph {i} with some text." for i in range(10)]
        text = "\n\n".join(paras)
        chunks = chunk_by_paragraph(text, max_tokens=10)
        for chunk in chunks:
            # Each chunk should be roughly within limit (may exceed slightly due to paragraph boundaries)
            assert len(chunk) < 200  # generous upper bound
