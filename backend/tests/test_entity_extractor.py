"""Unit tests for EntityExtractor — all entity types, deduplication, blocklist, edge cases."""
import pytest
from app.extraction.entity_extractor import EntityExtractor, _deduplicate, ExtractedEntity

GALAXY = "test-galaxy"


@pytest.fixture
def extractor():
    return EntityExtractor()


# --- Person extraction ---

class TestPersonExtraction:
    def test_full_name(self, extractor):
        entities = extractor.extract("John Smith joined the team.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        assert "John Smith" in names

    def test_multiple_people(self, extractor):
        entities = extractor.extract("Alice Johnson works with Bob Williams every day.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        assert "Alice Johnson" in names
        assert "Bob Williams" in names

    def test_action_verb_pattern(self, extractor):
        entities = extractor.extract("Sarah said the deadline is Friday.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        assert "Sarah" in names

    def test_at_mention(self, extractor):
        entities = extractor.extract("Ping @alice_dev for review.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        assert "alice_dev" in names

    def test_short_at_mention_filtered(self, extractor):
        """@mentions under 3 chars should be filtered."""
        entities = extractor.extract("@ab is too short.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        assert "ab" not in names

    def test_two_letter_name_filtered(self, extractor):
        """Names with parts < 3 chars should not match the person pattern."""
        entities = extractor.extract("Jo Li was there.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "person"}
        # Pattern requires [A-Z][a-z]{2,} so "Jo Li" won't match
        assert "Jo Li" not in names


# --- Organization extraction ---

class TestOrganizationExtraction:
    def test_known_orgs(self, extractor):
        entities = extractor.extract("We use AWS and Google Cloud.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "organization"}
        assert "AWS" in names
        assert "Google" in names

    def test_suffix_pattern(self, extractor):
        entities = extractor.extract("Acme Corp signed the deal.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "organization"}
        assert "Acme Corp" in names

    def test_labs_suffix(self, extractor):
        entities = extractor.extract("Stability AI released a new model.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "organization"}
        assert "Stability AI" in names

    def test_all_known_orgs(self, extractor):
        text = "AWS, GCP, Azure, Anthropic, OpenAI, Microsoft, Apple, Meta are all companies."
        entities = extractor.extract(text, GALAXY)
        org_names = {e.name for e in entities if e.entity_type == "organization"}
        for expected in ["AWS", "GCP", "Azure", "Anthropic", "OpenAI", "Microsoft", "Apple", "Meta"]:
            assert expected in org_names, f"Missing org: {expected}"


# --- Tool extraction ---

class TestToolExtraction:
    def test_known_tools(self, extractor):
        entities = extractor.extract("We chose FastAPI and Redis for the stack.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "tool"}
        assert "FastAPI" in names
        assert "Redis" in names

    def test_backtick_tool(self, extractor):
        entities = extractor.extract("Install `my-cool-tool` from npm.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "tool"}
        assert "my-cool-tool" in names

    def test_backtick_short_filtered(self, extractor):
        """Backtick tools under 3 chars should be filtered."""
        entities = extractor.extract("Use `ab` for this.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "tool"}
        assert "ab" not in names

    def test_case_sensitive_tools(self, extractor):
        """Tool names like 'fastapi' (lowercase) should NOT match — pattern is case-sensitive."""
        entities = extractor.extract("We use fastapi for the backend.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "tool"}
        assert "fastapi" not in names

    def test_chromadb_variant(self, extractor):
        entities = extractor.extract("ChromaDB is our vector store.", GALAXY)
        names = {e.name for e in entities if e.entity_type == "tool"}
        assert "ChromaDB" in names

    def test_all_known_tools(self, extractor):
        tools = ["FastAPI", "Redis", "SQLite", "PostgreSQL", "Docker", "React", "Python",
                 "TypeScript", "Vite", "Tailwind", "Zustand", "Ollama", "Alembic", "pytest",
                 "httpx", "Pydantic", "Kubernetes", "Terraform"]
        text = " ".join(tools) + " are all tools."
        entities = extractor.extract(text, GALAXY)
        found = {e.name for e in entities if e.entity_type == "tool"}
        for t in tools:
            assert t in found, f"Missing tool: {t}"


# --- Decision extraction ---

class TestDecisionExtraction:
    def test_decided_pattern(self, extractor):
        entities = extractor.extract("We decided to use PostgreSQL for production.", GALAXY)
        decisions = [e for e in entities if e.entity_type == "decision"]
        assert len(decisions) >= 1
        assert any("PostgreSQL" in d.name for d in decisions)

    def test_rejected_pattern(self, extractor):
        entities = extractor.extract("We rejected the monolith approach for microservices.", GALAXY)
        decisions = [e for e in entities if e.entity_type == "decision"]
        assert len(decisions) >= 1

    def test_decision_colon_pattern(self, extractor):
        entities = extractor.extract("decision: use event sourcing for audit trail.", GALAXY)
        decisions = [e for e in entities if e.entity_type == "decision"]
        assert len(decisions) >= 1

    def test_short_decision_filtered(self, extractor):
        """Decisions under 10 chars should not match the pattern."""
        entities = extractor.extract("We decided ok.", GALAXY)
        decisions = [e for e in entities if e.entity_type == "decision"]
        # "ok" is too short for the {10,80} quantifier
        assert len(decisions) == 0


# --- Code ref extraction ---

class TestCodeRefExtraction:
    def test_module_function(self, extractor):
        entities = extractor.extract("Call stardust_service.write_stardust for writes.", GALAXY)
        refs = {e.name for e in entities if e.entity_type == "code_ref"}
        assert "stardust_service.write_stardust" in refs

    def test_file_path_pattern(self, extractor):
        """File paths without CamelCase/underscores are filtered by is_valid_code_ref."""
        entities = extractor.extract("file: /app/services/search.py is the entry point.", GALAXY)
        refs = {e.name for e in entities if e.entity_type == "code_ref"}
        assert "/app/services/search.py" not in refs  # filtered: no CamelCase or underscore in segments

    def test_endpoint_pattern(self, extractor):
        """URL paths without CamelCase/underscores are filtered by is_valid_code_ref."""
        entities = extractor.extract("endpoint: /api/v1/stardust handles writes.", GALAXY)
        refs = {e.name for e in entities if e.entity_type == "code_ref"}
        assert "/api/v1/stardust" not in refs  # filtered: no CamelCase or underscore

    def test_valid_code_ref(self, extractor):
        entities = extractor.extract("Call app.services.stardust_service to write.", GALAXY)
        refs = {e.name for e in entities if e.entity_type == "code_ref"}
        assert "app.services.stardust_service" in refs


# --- Deduplication ---

class TestDeduplication:
    def test_case_insensitive_dedup(self):
        entities = [
            ExtractedEntity(name="FastAPI", entity_type="tool", galaxy_id=GALAXY),
            ExtractedEntity(name="fastapi", entity_type="tool", galaxy_id=GALAXY),
        ]
        result = _deduplicate(entities)
        assert len(result) == 1

    def test_different_types_not_deduped(self):
        entities = [
            ExtractedEntity(name="Redis", entity_type="tool", galaxy_id=GALAXY),
            ExtractedEntity(name="Redis", entity_type="organization", galaxy_id=GALAXY),
        ]
        result = _deduplicate(entities)
        assert len(result) == 2

    def test_preserves_first_occurrence(self):
        entities = [
            ExtractedEntity(name="John Smith", entity_type="person", galaxy_id=GALAXY),
            ExtractedEntity(name="john smith", entity_type="person", galaxy_id=GALAXY),
        ]
        result = _deduplicate(entities)
        assert result[0].name == "John Smith"

    def test_empty_list(self):
        assert _deduplicate([]) == []


# --- Blocklist ---

class TestBlocklist:
    def test_blocklisted_phrases_filtered(self, extractor):
        entities = extractor.extract("In MVP we build The Backend for Phase Two.", GALAXY)
        names = {e.name for e in entities}
        assert "In MVP" not in names
        assert "The Backend" not in names

    def test_short_strings_filtered(self, extractor):
        """Anything under 3 chars should be filtered."""
        entities = extractor.extract("@ab and `xy` are too short.", GALAXY)
        assert all(len(e.name) >= 3 for e in entities)


# --- Edge cases ---

class TestEdgeCases:
    def test_empty_string(self, extractor):
        assert extractor.extract("", GALAXY) == []

    def test_no_entities(self, extractor):
        """All-lowercase text should find no orgs or tools (person regex matches IGNORECASE though)."""
        entities = extractor.extract("the quick brown fox jumps over the lazy dog", GALAXY)
        orgs = [e for e in entities if e.entity_type == "organization"]
        tools = [e for e in entities if e.entity_type == "tool"]
        assert len(orgs) == 0
        assert len(tools) == 0

    def test_mixed_content(self, extractor):
        text = "John Smith from AWS decided to use FastAPI. @bob_dev approved. ref: app.main_module"
        entities = extractor.extract(text, GALAXY)
        types = {e.entity_type for e in entities}
        assert "person" in types
        assert "organization" in types
        assert "tool" in types
        assert "decision" in types
        assert "code_ref" in types

    def test_galaxy_id_propagated(self, extractor):
        entities = extractor.extract("John Smith works here.", GALAXY)
        for e in entities:
            assert e.galaxy_id == GALAXY

    def test_unicode_content(self, extractor):
        """Should not crash on unicode."""
        entities = extractor.extract("José García mentioned AWS in the meeting.", GALAXY)
        org_names = {e.name for e in entities if e.entity_type == "organization"}
        assert "AWS" in org_names
