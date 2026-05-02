"""Local session tracker — tracks active MCP sessions in-memory, logs lifecycle to Nebula via API."""
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger("orion.mcp.session")

IDLE_TIMEOUT = 300  # 5 minutes


@dataclass
class Session:
    id: str
    agent: str
    started_at: datetime
    last_active: datetime
    reads: int = 0
    writes: int = 0
    context_injected: bool = False
    tools_called: list[str] = field(default_factory=list)


class SessionTracker:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._cleanup_task: asyncio.Task | None = None

    def touch(self, agent: str, tool_name: str) -> Session:
        now = datetime.now(timezone.utc)
        session = self._sessions.get(agent)
        if not session:
            session = Session(id=str(uuid.uuid4()), agent=agent, started_at=now, last_active=now)
            self._sessions[agent] = session
            logger.info(f"Session started: {session.id} agent={agent}")
            asyncio.ensure_future(self._log_start(session))
        session.last_active = now
        session.tools_called.append(tool_name)
        if tool_name in _READ_TOOLS:
            session.reads += 1
        elif tool_name in _WRITE_TOOLS:
            session.writes += 1
        # Start idle cleanup loop
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._idle_loop())
        return session

    def needs_context(self, agent: str) -> bool:
        s = self._sessions.get(agent)
        return s is not None and not s.context_injected

    def mark_context_injected(self, agent: str):
        if agent in self._sessions:
            self._sessions[agent].context_injected = True

    def end_session(self, agent: str) -> dict | None:
        session = self._sessions.pop(agent, None)
        if not session:
            return None
        stats = self._stats(session)
        asyncio.ensure_future(self._log_end(session, "Agent ended session."))
        return stats

    def _stats(self, session: Session) -> dict:
        duration = int((session.last_active - session.started_at).total_seconds())
        return {
            "session_id": session.id, "agent": session.agent,
            "duration_seconds": duration, "reads": session.reads,
            "writes": session.writes, "tools_called": len(session.tools_called),
        }

    async def _idle_loop(self):
        while self._sessions:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            expired = [
                key for key, s in self._sessions.items()
                if (now - s.last_active).total_seconds() > IDLE_TIMEOUT
            ]
            for key in expired:
                session = self._sessions.pop(key)
                logger.info(f"Session idle-expired: {session.id} agent={session.agent}")
                await self._log_end(session, f"Idle-expired after {IDLE_TIMEOUT}s.")

    async def _log_start(self, session: Session):
        try:
            from orion_mcp import client
            await client.log_nebula_event(
                galaxy_id="", action_type="SESSION_START",
                initiated_by=session.agent, session_id=session.id,
            )
        except Exception as e:
            logger.debug(f"Failed to log session start: {e}")

    async def _log_end(self, session: Session, summary: str):
        try:
            from orion_mcp import client
            stats = self._stats(session)
            await client.log_nebula_event(
                galaxy_id="", action_type="SESSION_END",
                initiated_by=session.agent, session_id=session.id,
                payload=json.dumps({
                    "reads": stats["reads"], "writes": stats["writes"],
                    "duration": stats["duration_seconds"], "summary": summary,
                }),
            )
        except Exception as e:
            logger.debug(f"Failed to log session end: {e}")


_READ_TOOLS = {
    "memory.search", "memory.context", "memory.entity_get", "memory.status",
    "brain.orient", "brain.recall", "brain.health", "brain.know",
    "brain.graph_query", "brain.find_path", "brain.ask", "sun.read",
}
_WRITE_TOOLS = {
    "memory.write", "brain.think", "brain.calibrate",
    "brain.synthesize", "sun.update", "sun.working_context",
}

tracker = SessionTracker()
