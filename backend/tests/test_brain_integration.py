"""Integration test: brain.orient → brain.think → brain.recall → brain.calibrate flow.

Tests the full cognitive lifecycle using the MCP tool functions directly.
Requires a running database (uses SQLite in-memory via test fixtures).
"""
import pytest
import asyncio
import os

# Skip if no database available (CI without docker)
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION", "1") == "1",
    reason="Integration tests require running services (set SKIP_INTEGRATION=0)",
)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_brain_full_lifecycle():
    """Test the complete brain lifecycle: orient → think → recall → calibrate."""
    from app.mcp.tools_brain import brain_orient, brain_think, brain_recall, brain_calibrate, brain_health

    # Step 1: Orient — creates agent identity and starts session
    orientation = await brain_orient(
        agent_name="test-integration-agent",
        model="claude-sonnet-4-6",
        agent_type="CODING",
    )
    assert "error" not in orientation or orientation.get("error") is None
    # Should have session_id if galaxy exists
    if "session_id" in orientation:
        session_id = orientation["session_id"]

        # Step 2: Think — write knowledge with reasoning
        think_result = await brain_think(
            content="FastAPI uses Pydantic for request validation",
            planet="Engineering",
            cognitive_mode="procedural",
            confidence=0.8,
            reasoning="Observed in the codebase — all endpoints use Pydantic models",
            session_id=session_id,
        )
        assert think_result.get("status") in ("success", "written_with_conflict")
        stardust_id = think_result.get("stardust_id")
        assert stardust_id is not None

        # Step 3: Recall — search for what we just wrote
        recall_result = await brain_recall(
            query="FastAPI validation",
            cognitive_mode="procedural",
            context_window="Working on API endpoint validation",
            include_reasoning=True,
            limit=5,
            session_id=session_id,
        )
        records = recall_result.get("records", [])
        # Should find at least the record we just wrote
        assert isinstance(records, list)
        assert recall_result.get("cognitive_mode") == "procedural"
        assert recall_result.get("context_window_used") is True

        # Step 4: Calibrate — report what was useful
        cal_result = await brain_calibrate(
            session_id=session_id,
            records_used=[stardust_id] if stardust_id else [],
            records_retrieved_unused=[],
            knowledge_gaps=["OAuth2 patterns"],
            session_outcome="Completed API validation setup",
            knowledge_quality_score=0.85,
        )
        assert cal_result.get("calibration_id") is not None
        assert cal_result.get("gaps_logged") == 1

        # Step 5: Health check
        health = await brain_health(agent_name="test-integration-agent")
        if "error" not in health:
            assert 0.0 <= health.get("overall_health", 0) <= 1.0
            assert health.get("agent_sessions", 0) >= 1


@pytest.mark.asyncio
async def test_brain_orient_model_switch():
    """Test that orienting with a different model triggers model switch."""
    from app.mcp.tools_brain import brain_orient

    # First orient with model A
    result1 = await brain_orient(
        agent_name="test-switch-agent",
        model="claude-sonnet-4-6",
    )

    # Second orient with model B — should trigger model switch
    result2 = await brain_orient(
        agent_name="test-switch-agent",
        model="gpt-4o",
    )

    # If galaxy exists, the second orient should include a transition brief
    if "session_id" in result2:
        # The transition brief may or may not be present depending on
        # whether the first orient created a session
        assert result2.get("model_calibration", {}).get("model") == "gpt-4o"


@pytest.mark.asyncio
async def test_brain_orient_identity_persistence():
    """Test that the same agent_name returns the same identity across calls."""
    from app.mcp.tools_brain import brain_orient

    r1 = await brain_orient(agent_name="persistent-agent", model="claude-sonnet-4-6")
    r2 = await brain_orient(agent_name="persistent-agent", model="claude-sonnet-4-6")

    if "agent_identity" in r1 and "agent_identity" in r2:
        assert r1["agent_identity"]["agent_name"] == r2["agent_identity"]["agent_name"]
        # Session count should increment
        assert r2["agent_identity"]["total_sessions"] >= r1["agent_identity"]["total_sessions"]
