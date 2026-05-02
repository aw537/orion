"""Wraps Graphify's knowledge graph builder for Orion's routing pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GraphifyAnalysis:
    primary_cluster: str
    cluster_confidence: float
    secondary_clusters: list[str] = field(default_factory=list)
    extracted_concepts: list[str] = field(default_factory=list)
    extracted_relationships: list[tuple[str, str, str]] = field(default_factory=list)
    content_type: str = "prose"
    languages_detected: list[str] = field(default_factory=list)
    graphify_ran: bool = True


_EMPTY = GraphifyAnalysis(primary_cluster="unknown", cluster_confidence=0.0, graphify_ran=False)


class GraphifyAdapter:
    _MAX_CACHE_SIZE = 1024

    def __init__(self):
        self._cache: dict[str, GraphifyAnalysis] = {}

    async def analyze(self, content: str, filename: str | None = None, use_llm: bool = True) -> GraphifyAnalysis:
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        if h in self._cache:
            return self._cache[h]
        result = await asyncio.get_running_loop().run_in_executor(None, self._run_sync, content, filename, use_llm)
        if len(self._cache) >= self._MAX_CACHE_SIZE:
            # Evict oldest entry (FIFO approximation)
            self._cache.pop(next(iter(self._cache)))
        self._cache[h] = result
        return result

    def _run_sync(self, content: str, filename: str | None, use_llm: bool) -> GraphifyAnalysis:
        try:
            import graphifyy as graphify
        except ImportError:
            logger.warning("graphifyy not installed — returning empty analysis")
            return _EMPTY

        ext = self._infer_ext(content, filename)
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / f"input{ext}").write_text(content, encoding="utf-8")
            out = Path(tmpdir) / "graphify-out"
            out.mkdir()
            try:
                graphify.run(source_path=str(tmpdir), output_dir=str(out), use_llm=use_llm, silent=True)
            except Exception as e:
                logger.error(f"Graphify analysis failed: {e}")
                return _EMPTY
            gj = out / "graph.json"
            if not gj.exists():
                return _EMPTY
            return self._parse(json.loads(gj.read_text()), content)

    def _parse(self, data: dict, content: str) -> GraphifyAnalysis:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        communities = data.get("communities", {})
        meta = data.get("metadata", {})
        if not nodes:
            return GraphifyAnalysis(primary_cluster="unknown", cluster_confidence=0.0, graphify_ran=True)

        counts: dict[str, int] = {}
        conf_sums: dict[str, float] = {}
        for n in nodes:
            lbl = n.get("community_label", "unknown")
            counts[lbl] = counts.get(lbl, 0) + 1
            conf_sums[lbl] = conf_sums.get(lbl, 0.0) + n.get("confidence", 0.5)

        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        primary = ranked[0][0]
        primary_n = ranked[0][1]
        proportion = primary_n / len(nodes)
        avg_conf = conf_sums.get(primary, 0.0) / primary_n
        cluster_confidence = round(proportion * avg_conf, 3)

        secondary = [l for l, _ in ranked[1:] if l != "unknown"][:3]

        # Hub nodes from primary community
        concepts = []
        for cid, cdata in communities.items():
            if cdata.get("label") == primary:
                concepts = cdata.get("hub_nodes", [])[:10]
                break

        label_map = {n["id"]: n.get("label", "") for n in nodes}
        rels = []
        for e in edges[:20]:
            s, t = label_map.get(e["source"], ""), label_map.get(e["target"], "")
            if s and t:
                rels.append((s, e.get("type", "related_to"), t))

        return GraphifyAnalysis(
            primary_cluster=primary, cluster_confidence=cluster_confidence,
            secondary_clusters=secondary, extracted_concepts=concepts,
            extracted_relationships=rels, content_type=meta.get("content_type", "prose"),
            languages_detected=meta.get("languages_detected", []), graphify_ran=True,
        )

    @staticmethod
    def _infer_ext(content: str, filename: str | None) -> str:
        if filename:
            s = Path(filename).suffix
            if s:
                return s
        if "def " in content and "import " in content:
            return ".py"
        if "function " in content or "const " in content:
            return ".js"
        if "func " in content and "package " in content:
            return ".go"
        return ".md"


graphify_adapter = GraphifyAdapter()
