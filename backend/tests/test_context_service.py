"""Unit tests for context_service — token estimation."""
import pytest
from app.services.context_service import _estimate_tokens, CHARS_PER_TOKEN


class TestTokenEstimation:
    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_string(self):
        # "hello" = 5 chars / 4 = 1 token
        assert _estimate_tokens("hello") == 1

    def test_exact_multiple(self):
        # 20 chars / 4 = 5 tokens
        assert _estimate_tokens("a" * 20) == 5

    def test_not_exact_multiple(self):
        # 7 chars / 4 = 1 (integer division)
        assert _estimate_tokens("abcdefg") == 1

    def test_longer_text(self):
        text = "This is a longer piece of text that should estimate to roughly the right number of tokens."
        tokens = _estimate_tokens(text)
        assert tokens == len(text) // CHARS_PER_TOKEN

    def test_chars_per_token_constant(self):
        assert CHARS_PER_TOKEN == 4

    def test_1000_char_text(self):
        text = "x" * 1000
        assert _estimate_tokens(text) == 250

    def test_realistic_paragraph(self):
        text = "We decided to use FastAPI for the backend because it provides async support out of the box and has excellent OpenAPI documentation generation."
        tokens = _estimate_tokens(text)
        # ~142 chars / 4 = 35 tokens
        assert 30 <= tokens <= 40
