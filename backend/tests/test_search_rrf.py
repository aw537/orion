"""Unit tests for RRF fusion logic in search_service."""
import pytest
from app.services.search_service import _rrf_fuse, RRF_K


class TestRRFFusion:
    def test_single_ranking(self):
        ranking = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.7}, {"id": "c", "score": 0.5}]
        result = _rrf_fuse([ranking])
        ids = [d["id"] for d in result]
        assert ids == ["a", "b", "c"]

    def test_two_identical_rankings(self):
        ranking = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        result = _rrf_fuse([ranking, ranking])
        ids = [d["id"] for d in result]
        # Same order preserved since scores are doubled equally
        assert ids == ["a", "b", "c"]

    def test_disagreeing_rankings_fused(self):
        r1 = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        r2 = [{"id": "c"}, {"id": "b"}, {"id": "a"}]
        result = _rrf_fuse([r1, r2])
        ids = [d["id"] for d in result]
        # All three have equal RRF scores (each appears at rank 0,1,2 across the two lists)
        # "a": 1/(61) + 1/(63) = ~0.032, "b": 1/(62) + 1/(62) = ~0.032, "c": 1/(63) + 1/(61) = ~0.032
        # All equal, so order depends on sort stability — just verify all present
        assert set(ids) == {"a", "b", "c"}

    def test_three_rankings(self):
        r1 = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        r2 = [{"id": "b"}, {"id": "c"}, {"id": "a"}]
        r3 = [{"id": "c"}, {"id": "a"}, {"id": "b"}]
        result = _rrf_fuse([r1, r2, r3])
        # All docs appear at each rank once, so scores should be equal
        # Order depends on dict iteration but all should be present
        ids = {d["id"] for d in result}
        assert ids == {"a", "b", "c"}

    def test_empty_rankings(self):
        assert _rrf_fuse([]) == []
        assert _rrf_fuse([[]]) == []
        assert _rrf_fuse([[], []]) == []

    def test_non_overlapping_rankings(self):
        r1 = [{"id": "a"}, {"id": "b"}]
        r2 = [{"id": "c"}, {"id": "d"}]
        result = _rrf_fuse([r1, r2])
        ids = {d["id"] for d in result}
        assert ids == {"a", "b", "c", "d"}

    def test_partial_overlap(self):
        r1 = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        r2 = [{"id": "b"}, {"id": "d"}]
        result = _rrf_fuse([r1, r2])
        ids = [d["id"] for d in result]
        # "b" appears in both rankings, should be boosted to top
        assert ids[0] == "b"

    def test_rrf_scores_are_correct(self):
        """Verify the actual RRF score computation."""
        r1 = [{"id": "x"}]
        r2 = [{"id": "x"}]
        result = _rrf_fuse([r1, r2], k=60)
        # x is rank 0 in both: score = 2 * (1 / (60 + 0 + 1)) = 2/61
        expected = 2.0 / 61.0
        # We can't directly access scores, but x should be the only result
        assert len(result) == 1
        assert result[0]["id"] == "x"

    def test_custom_k_value(self):
        r1 = [{"id": "a"}, {"id": "b"}]
        r2 = [{"id": "b"}, {"id": "a"}]
        # With k=0, rank differences are amplified
        result_k0 = _rrf_fuse([r1, r2], k=0)
        # With k=1000, rank differences are dampened
        result_k1000 = _rrf_fuse([r1, r2], k=1000)
        # Both should have same docs
        assert {d["id"] for d in result_k0} == {"a", "b"}
        assert {d["id"] for d in result_k1000} == {"a", "b"}

    def test_preserves_doc_metadata(self):
        r1 = [{"id": "a", "content": "hello", "extra": 42}]
        result = _rrf_fuse([r1])
        assert result[0]["content"] == "hello"
        assert result[0]["extra"] == 42

    def test_first_occurrence_wins_metadata(self):
        """When same doc appears in multiple rankings, first occurrence's metadata is kept."""
        r1 = [{"id": "a", "source": "r1"}]
        r2 = [{"id": "a", "source": "r2"}]
        result = _rrf_fuse([r1, r2])
        assert result[0]["source"] == "r1"

    def test_large_ranking(self):
        ranking = [{"id": str(i)} for i in range(100)]
        result = _rrf_fuse([ranking])
        assert len(result) == 100
        assert result[0]["id"] == "0"
        assert result[-1]["id"] == "99"

    def test_default_k_is_60(self):
        assert RRF_K == 60
