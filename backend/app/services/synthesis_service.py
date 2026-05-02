"""Synthesis Service — LLM-powered topic synthesis from Galaxy knowledge."""
import hashlib
import json
import logging
import re
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.search_service import search
from app.services import nebula_service

logger = logging.getLogger(__name__)


class SynthesisResult(BaseModel):
    topic: str
    current_understanding: str
    key_decisions: list[str] = []
    open_questions: list[str] = []
    contradictions: list[str] = []
    confidence: float = 0.0
    record_count: int = 0
    last_updated: str | None = None


async def llm_complete(prompt: str, max_tokens: int, system: str) -> str:
    """Call the configured LLM provider (ollama, anthropic, or openai)."""
    try:
        import httpx
        from app.config import get_settings
        settings = get_settings()
        provider = settings.LLM_PROVIDER

        if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": settings.LLM_MODEL, "max_tokens": max_tokens,
                          "system": system, "messages": [{"role": "user", "content": prompt}]},
                )
                data = resp.json()
                return data.get("content", [{}])[0].get("text", "")

        if provider == "openai" and settings.OPENAI_API_KEY:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json={"model": settings.LLM_MODEL, "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                )
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Default: Ollama
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={"model": settings.LLM_MODEL,
                       "prompt": f"{system}\n\n{prompt}",
                       "stream": False, "options": {"num_predict": max_tokens}},
            )
            return resp.json().get("response", "")
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


class SynthesisService:

    def _hash(self, topic: str, planet_id: str | None, biome_id: str | None) -> str:
        key = f"{topic}:{planet_id}:{biome_id}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    async def synthesize(
        self, topic: str, galaxy_id: str,
        planet_id: str | None, biome_id: str | None,
        include_open_questions: bool, include_contradictions: bool,
        max_tokens: int, db: AsyncSession, redis,
    ) -> SynthesisResult:
        # 1. Check cache
        cache_key = f"orion:{galaxy_id}:synthesis:{self._hash(topic, planet_id, biome_id)}"
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached) if isinstance(cached, str) else json.loads(cached.decode())
            return SynthesisResult(**data)

        # 2. Retrieve relevant records
        results = await search(topic, galaxy_id, limit=30)
        records = results.records

        if not records:
            return SynthesisResult(
                topic=topic,
                current_understanding="No knowledge found about this topic.",
                record_count=0, confidence=0.0,
            )

        # 2b. Fetch unresolved contradictions if requested
        contradiction_texts = []
        if include_contradictions:
            try:
                from app.services.contradiction_service import contradiction_service
                contras = await contradiction_service.list_contradictions(galaxy_id, "UNRESOLVED", 10, db)
                for c in contras:
                    from app.models.stardust import Stardust as _Stardust
                    a = await db.get(_Stardust, c["record_a_id"])
                    b = await db.get(_Stardust, c["record_b_id"])
                    if a and b:
                        contradiction_texts.append(f"'{a.content[:80]}' vs '{b.content[:80]}'")
            except Exception:
                pass

        # 3. Build synthesis prompt
        records_text = self._format_records(records)
        prompt = self._build_prompt(topic, records_text, include_open_questions, max_tokens, contradiction_texts)

        # 4. LLM call
        system = (
            "You are synthesizing knowledge from a personal knowledge base. "
            "Be direct and specific. Cite reasoning when provided. "
            "Identify genuine uncertainty."
        )
        raw = await llm_complete(prompt, max_tokens, system)

        # 5. Parse response
        result = self._parse_response(raw, topic, records, contradiction_texts)

        # 6. Cache for 30 minutes
        await redis.setex(cache_key, 1800, result.model_dump_json())

        # 7. Log to Nebula
        try:
            await nebula_service.log_event(
                galaxy_id=galaxy_id, action_type="SYNTHESIS_GENERATED",
                initiated_by="synthesis_service",
                payload_after=json.dumps({"topic": topic, "record_count": result.record_count}),
                db=db,
            )
        except Exception:
            pass

        return result

    def _format_records(self, records) -> str:
        lines = []
        for i, r in enumerate(records, 1):
            text = f"{i}. [{r.region}] {r.content}"
            text += f"\n   Confidence: {r.confidence}"
            lines.append(text)
        return "\n\n".join(lines)

    def _build_prompt(self, topic: str, records_text: str,
                      include_open_questions: bool, max_tokens: int,
                      contradictions: list[str] | None = None) -> str:
        sections = [
            f"Topic: {topic}", "", "Knowledge records:", records_text, "",
            "Provide a synthesis with these sections:",
            "CURRENT_UNDERSTANDING: [2-3 paragraphs]",
            "KEY_DECISIONS: [bulleted list with reasoning]",
        ]
        if include_open_questions:
            sections.append("OPEN_QUESTIONS: [bulleted list]")
        if contradictions:
            sections.append("CONTRADICTIONS: [bulleted list of unresolved tensions]")
            sections.append("")
            sections.append("Known contradictions:")
            for c in contradictions:
                sections.append(f"• {c}")
        sections.append("CONFIDENCE: [0.0-1.0 with explanation]")
        return "\n".join(sections)

    def _parse_response(self, raw: str, topic: str, records, contradiction_texts: list[str] | None = None) -> SynthesisResult:
        understanding = self._extract_section(raw, "CURRENT_UNDERSTANDING")
        decisions = self._extract_bullets(raw, "KEY_DECISIONS")
        questions = self._extract_bullets(raw, "OPEN_QUESTIONS")
        contradictions = self._extract_bullets(raw, "CONTRADICTIONS") or (contradiction_texts or [])
        confidence = self._extract_confidence(raw)

        last_updated = None
        if records:
            dates = [r.valid_from for r in records if r.valid_from]
            if dates:
                last_updated = max(dates).isoformat()

        return SynthesisResult(
            topic=topic,
            current_understanding=understanding or raw[:500] or "Synthesis generated.",
            key_decisions=decisions,
            open_questions=questions,
            contradictions=contradictions,
            confidence=confidence,
            record_count=len(records),
            last_updated=last_updated,
        )

    def _extract_section(self, text: str, header: str) -> str:
        pattern = rf"{header}:\s*\n?(.*?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_bullets(self, text: str, header: str) -> list[str]:
        section = self._extract_section(text, header)
        if not section:
            return []
        return [line.lstrip("•-* ").strip() for line in section.split("\n") if line.strip().startswith(("•", "-", "*"))]

    def _extract_confidence(self, text: str) -> float:
        match = re.search(r"CONFIDENCE:\s*([\d.]+)", text)
        if match:
            try:
                return min(1.0, max(0.0, float(match.group(1))))
            except ValueError:
                pass
        return 0.5


synthesis_service = SynthesisService()
