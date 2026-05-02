"""Session Summary Service — generates end-of-session summaries."""
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.brain import AgentSession, AgentIdentity
from app.models import Galaxy

logger = logging.getLogger(__name__)


@dataclass
class SessionSummary:
    session_id: str
    agent_name: str
    duration_minutes: int
    records_written: int
    entities_enriched: int
    tier_upgrades: list[tuple]
    contradictions_detected: int
    top_topics: list[str]
    strength_before: float
    strength_after: float
    strength_delta: float


class SessionSummaryService:

    async def generate_summary(
        self, session_id: str, galaxy_id: str, db: AsyncSession,
    ) -> SessionSummary | None:
        session = await db.get(AgentSession, session_id)
        if not session:
            return None

        # Get agent name
        agent = await db.get(AgentIdentity, session.agent_identity_id)
        agent_name = agent.agent_name if agent else "unknown"

        # Count writes
        row = await db.execute(text(
            "SELECT COUNT(*) FROM interaction_log "
            "WHERE session_id = :sid AND action_type = 'WRITE'"
        ), {"sid": session_id})
        write_count = row.scalar() or 0

        if write_count == 0:
            return None

        # Count contradictions
        row = await db.execute(text(
            "SELECT COUNT(*) FROM interaction_log "
            "WHERE session_id = :sid AND action_type = 'CONTRADICTION_DETECTED'"
        ), {"sid": session_id})
        contradiction_count = row.scalar() or 0

        # Count entity enrichments
        row = await db.execute(text(
            "SELECT COUNT(*) FROM interaction_log "
            "WHERE session_id = :sid AND action_type = 'ENTITY_ENRICHED'"
        ), {"sid": session_id})
        enriched_count = row.scalar() or 0

        # Tier upgrades: entities whose tier increased during this session
        tier_upgrades = await self._extract_tier_upgrades(session_id, galaxy_id, db)

        # Extract topics from written stardust context_tags
        topics = await self._extract_session_topics(session_id, db)

        # Strength delta — read-only, no recomputation side effect
        strength_before = session.galaxy_strength_at_start or 0.0
        galaxy = await db.get(Galaxy, galaxy_id)
        strength_after = galaxy.strength_score if galaxy and galaxy.strength_score else 0.0

        # Duration
        started = session.started_at or datetime.now(timezone.utc).replace(tzinfo=None)
        if started.tzinfo:
            started = started.replace(tzinfo=None)
        duration = int((datetime.now(timezone.utc).replace(tzinfo=None) - started).total_seconds() / 60)

        return SessionSummary(
            session_id=session_id,
            agent_name=agent_name,
            duration_minutes=duration,
            records_written=write_count,
            entities_enriched=enriched_count,
            tier_upgrades=tier_upgrades,
            contradictions_detected=contradiction_count,
            top_topics=topics[:3],
            strength_before=round(strength_before, 1),
            strength_after=round(strength_after, 1),
            strength_delta=round(strength_after - strength_before, 1),
        )

    async def _extract_session_topics(
        self, session_id: str, db: AsyncSession,
    ) -> list[str]:
        result = await db.execute(text(
            "SELECT s.context_tags FROM stardust s "
            "JOIN interaction_log il ON s.id = il.record_id "
            "WHERE il.session_id = :sid AND il.action_type = 'WRITE'"
        ), {"sid": session_id})
        all_tags: list[str] = []
        for row in result.fetchall():
            raw = row[0]
            try:
                tags = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except (ValueError, TypeError):
                tags = []
            all_tags.extend(tags)
        return [tag for tag, _ in Counter(all_tags).most_common(5)]

    async def _extract_tier_upgrades(
        self, session_id: str, galaxy_id: str, db: AsyncSession,
    ) -> list[tuple]:
        """Find entities that were promoted during this session via ENTITY_ENRICHED events."""
        result = await db.execute(text(
            "SELECT payload_after FROM interaction_log "
            "WHERE session_id = :sid AND action_type = 'ENTITY_ENRICHED' "
            "AND payload_after IS NOT NULL"
        ), {"sid": session_id})
        upgrades = []
        for row in result.fetchall():
            try:
                data = json.loads(row[0])
                prev = data.get("previous_tier")
                new = data.get("new_tier")
                name = data.get("entity_name", "")
                if prev is not None and new is not None and new > prev:
                    upgrades.append((name, prev, new))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        return upgrades


def build_status_line(records_retrieved: int, biome_name: str, galaxy_strength: float) -> str:
    """Build the [orion: ...] status line, max 80 chars."""
    # Truncate biome name to fit within 80 chars
    prefix = f"[orion: {records_retrieved} records · "
    suffix = f" · {galaxy_strength}/100]"
    max_biome = 80 - len(prefix) - len(suffix)
    if len(biome_name) > max_biome:
        biome_name = biome_name[:max_biome - 1] + "…"
    return f"{prefix}{biome_name}{suffix}"


def build_confirmation_line(biome_name: str, region: str, total_records_today: int) -> str:
    """Build the [orion: written to ...] confirmation line."""
    return f"[orion: written to {biome_name} · {region} · {total_records_today} records today]"


session_summary_service = SessionSummaryService()
