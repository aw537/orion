"""Unit tests for signal_detector — region inference for all 3 regions + edge cases."""
import pytest
from app.extraction.signal_detector import infer_region_from_content


class TestAnalyticalRegion:
    def test_decision_heavy(self):
        assert infer_region_from_content("We decided because the tradeoff analysis showed this was the reason to evaluate and compare") == "analytical"

    def test_reasoning_keywords(self):
        assert infer_region_from_content("The reason we chosen this approach is therefore clear after evaluated comparison and rejected alternatives") == "analytical"

    def test_threshold_met(self):
        """Needs score > 2 to qualify."""
        assert infer_region_from_content("decided because reason") == "analytical"

    def test_threshold_not_met(self):
        """Score of 2 is not > 2."""
        assert infer_region_from_content("decided because") == "contextual"


class TestProceduralRegion:
    def test_step_by_step(self):
        assert infer_region_from_content("Step 1: install the package. Then run the process. Next execute the workflow.") == "procedural"

    def test_how_to(self):
        assert infer_region_from_content("how to install and run the procedure for the process workflow playbook") == "procedural"

    def test_threshold_met(self):
        assert infer_region_from_content("step first then next") == "procedural"

    def test_threshold_not_met(self):
        assert infer_region_from_content("step first") == "contextual"


class TestContextualRegion:
    def test_default_fallback(self):
        assert infer_region_from_content("The weather is nice today.") == "contextual"

    def test_no_keywords(self):
        assert infer_region_from_content("Just some random notes about the project.") == "contextual"

    def test_empty_string(self):
        assert infer_region_from_content("") == "contextual"

    def test_equal_scores_below_threshold(self):
        """When both scores are equal and <= 2, should be contextual."""
        assert infer_region_from_content("decided step") == "contextual"


class TestTieBreaking:
    def test_analytical_wins_tie(self):
        """When analytical > procedural and both > 2, analytical wins."""
        text = "decided because reason therefore step first then"
        result = infer_region_from_content(text)
        assert result == "analytical"

    def test_procedural_wins_tie(self):
        """When procedural > analytical and both > 2, procedural wins."""
        text = "step first then next install run decided"
        result = infer_region_from_content(text)
        assert result == "procedural"


class TestCaseInsensitivity:
    def test_uppercase_keywords(self):
        assert infer_region_from_content("DECIDED BECAUSE REASON THEREFORE") == "analytical"

    def test_mixed_case(self):
        assert infer_region_from_content("Step First Then Next Install Run Execute") == "procedural"


class TestKeywordCounting:
    def test_repeated_keywords_count(self):
        """Each occurrence of a keyword should count."""
        text = "decided decided decided"
        assert infer_region_from_content(text) == "analytical"

    def test_substring_matches(self):
        """Keywords match as substrings in .count()."""
        # "reason" appears in "reasoning"
        text = "reasoning reasoning reasoning"
        assert infer_region_from_content(text) == "analytical"
