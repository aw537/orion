"""Local session tracker — tracks active MCP sessions in-memory, logs lifecycle to Nebula via API."""
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger("orion.mcp.session")

IDLE_TIMEOUT = 300  # 5 minutes


def _create_task(coro) -> None:
    """Schedule a coroutine as a background task, safe to call from sync code."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass  # no running event loop — skip background logging


@dataclass
class Session:
    id: str
    agent: str
    started_at: datetime
    last_active: datetime
    galaxy_id: str = ""
    reads: int = 0
    writes: int = 0
    context_injected: bool = False
    tools_called: list[str] = field(default_factory=list)


class SessionTracker:
    def __init__(self):
        self._sessions: dict[str, Session] = {}  # keyed by session.id
        self._cleanup_task: asyncio.Task | None = None

    def _find_by_agent(self, agent: str) -> Session | None:
        """Return the most recently active session for an agent, if any."""
        matches = [s for s in self._sessions.values() if s.agent == agent]
        return max(matches, key=lambda s: s.last_active) if matches else None

    def touch(self, agent: str, tool_name: str) -> Session:
        now = datetime.now(timezone.utc)
        session = self._find_by_agent(agent)
        if not session:
            session = Session(id=str(uuid.uuid4()), agent=agent, started_at=now, last_active=now)
            self._sessions[session.id] = session
            logger.info(f"Session started: {session.id} agent={agent}")
            _create_task(self._log_start(session))
        session.last_active = now
        session.tools_called.append(tool_name)
        if tool_name in _READ_TOOLS:
            session.reads += 1
        elif tool_name in _WRITE_TOOLS:
            session.writes += 1
        # Start idle cleanup loop
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                self._cleanup_task = asyncio.get_running_loop().create_task(self._idle_loop())
            except RuntimeError:
                pass
        return session

    def set_galaxy_id(self, session_id: str, galaxy_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].galaxy_id = galaxy_id

    def needs_context(self, agent: str) -> bool:
        s = self._find_by_agent(agent)
        return s is not None and not s.context_injected

    def mark_context_injected(self, agent: str):
        s = self._find_by_agent(agent)
        if s:
            s.context_injected = True

    def end_session(self, agent: str) -> dict | None:
        s = self._find_by_agent(agent)
        if not s:
            return None
        self._sessions.pop(s.id, None)
        stats = self._stats(s)
        _create_task(self._log_end(s, "Agent ended session."))
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
                sid for sid, s in self._sessions.items()
                if (now - s.last_active).total_seconds() > IDLE_TIMEOUT
            ]
            for sid in expired:
                session = self._sessions.pop(sid)
                logger.info(f"Session idle-expired: {session.id} agent={session.agent}")
                await self._log_end(session, f"Idle-expired after {IDLE_TIMEOUT}s.")

    async def _log_start(self, session: Session):
        try:
            from orion_mcp import client
            galaxy_id = session.galaxy_id or await client.resolve_galaxy_id()
            self.set_galaxy_id(session.id, galaxy_id)
            await client.log_nebula_event(
                galaxy_id=galaxy_id, action_type="SESSION_START",
                initiated_by=session.agent, session_id=session.id,
            )
        except Exception as e:
            logger.debug(f"Failed to log session start: {e}")

    async def _log_end(self, session: Session, summary: str):
        try:
            from orion_mcp import client
            galaxy_id = session.galaxy_id or await client.resolve_galaxy_id()
            stats = self._stats(session)
            await client.log_nebula_event(
                galaxy_id=galaxy_id, action_type="SESSION_END",
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
