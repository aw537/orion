"""MCP Session Tracker — makes Orion a brain agents are connected to, not tools they remember to call."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 300  # 5 minutes
_SESSION_PREFIX = "orion:mcp:session:"


@dataclass
class Session:
    id: str
    galaxy_id: str
    agent: str
    started_at: datetime
    last_active: datetime
    reads: int = 0
    writes: int = 0
    context_injected: bool = False
    tools_called: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "galaxy_id": self.galaxy_id, "agent": self.agent,
            "started_at": self.started_at.isoformat(), "last_active": self.last_active.isoformat(),
            "reads": self.reads, "writes": self.writes,
            "context_injected": self.context_injected, "tools_called": self.tools_called,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        return cls(
            id=d["id"], galaxy_id=d["galaxy_id"], agent=d["agent"],
            started_at=datetime.fromisoformat(d["started_at"]),
            last_active=datetime.fromisoformat(d["last_active"]),
            reads=d.get("reads", 0), writes=d.get("writes", 0),
            context_injected=d.get("context_injected", False),
            tools_called=d.get("tools_called", []),
        )


class SessionTracker:
    def __init__(self):
        self._local_cache: dict[str, Session] = {}  # hot cache, backed by Redis
        self._cleanup_task: asyncio.Task | None = None

    def _agent_key(self, agent: str) -> str:
        return agent or "anonymous"

    def _redis_key(self, agent_key: str) -> str:
        return f"{_SESSION_PREFIX}{agent_key}"

    async def _get_redis(self):
        try:
            from app.storage.redis_client import get_redis
            return await get_redis()
        except Exception:
            return None

    async def _save_to_redis(self, key: str, session: Session):
        redis = await self._get_redis()
        if redis:
            try:
                await redis.setex(self._redis_key(key), IDLE_TIMEOUT_SECONDS + 60, json.dumps(session.to_dict()))
            except Exception as e:
                logger.warning(f"Failed to persist session to Redis: {e}")

    async def _load_from_redis(self, key: str) -> Session | None:
        redis = await self._get_redis()
        if redis:
            try:
                raw = await redis.get(self._redis_key(key))
                if raw:
                    return Session.from_dict(json.loads(raw))
            except Exception as e:
                logger.warning(f"Failed to load session from Redis: {e}")
        return None

    async def _delete_from_redis(self, key: str):
        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(self._redis_key(key))
            except Exception:
                pass

    async def touch(self, agent: str, tool_name: str, galaxy_id: str) -> Session:
        key = self._agent_key(agent)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        session = self._local_cache.get(key)
        if not session:
            session = await self._load_from_redis(key)
            if session:
                self._local_cache[key] = session

        if not session:
            session = Session(
                id=str(uuid.uuid4()), galaxy_id=galaxy_id,
                agent=agent or "anonymous", started_at=now, last_active=now,
            )
            self._local_cache[key] = session
            await self._log_session_start(session)
            logger.info(f"Session started: {session.id} for agent={session.agent}")
        else:
            session.last_active = now

        session.tools_called.append(tool_name)
        read_tools = {"memory.search", "memory.context", "memory.entity_get", "memory.status",
                       "brain.orient", "brain.recall", "brain.health", "brain.know", "brain.graph_query", "brain.find_path",
                       "sun.read"}
        write_tools = {"memory.write", "brain.think", "brain.calibrate", "sun.update", "sun.working_context"}
        if tool_name in read_tools:
            session.reads += 1
        elif tool_name in write_tools:
            session.writes += 1

        await self._save_to_redis(key, session)

        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._idle_loop())

        return session

    def needs_context(self, agent: str) -> bool:
        key = self._agent_key(agent)
        session = self._local_cache.get(key)
        if not session or session.context_injected:
            return False
        return True

    def mark_context_injected(self, agent: str):
        key = self._agent_key(agent)
        if key in self._local_cache:
            self._local_cache[key].context_injected = True

    async def end_session(self, agent: str, summary: str | None = None) -> dict | None:
        key = self._agent_key(agent)
        session = self._local_cache.pop(key, None)
        if not session:
            session = await self._load_from_redis(key)
        if not session:
            return None
        await self._delete_from_redis(key)
        await self._log_session_end(session, summary or "Agent ended session explicitly.")
        return self._session_stats(session)

    def get_session(self, agent: str) -> Session | None:
        return self._local_cache.get(self._agent_key(agent))

    async def _idle_loop(self):
        while self._local_cache:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            expired = [
                key for key, s in self._local_cache.items()
                if (now - s.last_active).total_seconds() > IDLE_TIMEOUT_SECONDS
            ]
            for key in expired:
                session = self._local_cache.pop(key)
                await self._delete_from_redis(key)
                logger.info(f"Session idle-expired: {session.id} agent={session.agent} (reads={session.reads}, writes={session.writes})")
                await self._log_session_end(session, f"Session idle-expired after {IDLE_TIMEOUT_SECONDS}s inactivity.")

    def _session_stats(self, session: Session) -> dict:
        duration = int((session.last_active - session.started_at).total_seconds())
        return {
            "session_id": session.id,
            "agent": session.agent,
            "duration_seconds": duration,
            "reads": session.reads,
            "writes": session.writes,
            "tools_called": len(session.tools_called),
        }

    async def _log_session_start(self, session: Session):
        try:
            from app.services import nebula_service
            await nebula_service.log_event(
                galaxy_id=session.galaxy_id, action_type="SESSION_START",
                initiated_by=session.agent, session_id=session.id,
            )
        except Exception as e:
            logger.warning(f"Failed to log session start: {e}")

    async def _log_session_end(self, session: Session, summary: str):
        try:
            import json as _json
            from app.services import nebula_service
            stats = self._session_stats(session)
            payload = _json.dumps({
                "reads": stats["reads"],
                "writes": stats["writes"],
                "duration": stats["duration_seconds"],
                "summary": summary,
            })
            await nebula_service.log_event(
                galaxy_id=session.galaxy_id, action_type="SESSION_END",
                initiated_by=session.agent, session_id=session.id,
                payload_after=payload,
            )
            # Emit SESSION_SUMMARY if there were writes
            if session.writes > 0:
                try:
                    from app.services.session_summary_service import session_summary_service
                    from app.database import async_session as _async_session
                    async with _async_session() as db:
                        s = await session_summary_service.generate_summary(
                            session.id, session.galaxy_id, db,
                        )
                        if s:
                            await nebula_service.log_event(
                                galaxy_id=session.galaxy_id,
                                action_type="SESSION_SUMMARY",
                                initiated_by=session.agent,
                                session_id=session.id,
                                payload_after=_json.dumps({
                                    "records_written": s.records_written,
                                    "entities_enriched": s.entities_enriched,
                                    "tier_upgrades": [{"name": n, "from": f, "to": t} for n, f, t in s.tier_upgrades],
                                    "contradictions_detected": s.contradictions_detected,
                                    "top_topics": s.top_topics,
                                    "strength_delta": s.strength_delta,
                                    "strength_before": s.strength_before,
                                    "strength_after": s.strength_after,
                                    "duration_minutes": s.duration_minutes,
                                }),
                            )
                except Exception as e:
                    logger.warning(f"Failed to generate session summary: {e}")
        except Exception as e:
            logger.warning(f"Failed to log session end: {e}")


# Singleton
tracker = SessionTracker()
