"""Orion TUI — Textual terminal interface for the Galaxy."""
import json
import asyncio
import httpx
from datetime import datetime, timezone
from rich.markup import escape as markup_escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Tree, Label, Input, TextArea
from textual.reactive import reactive
from textual import work

API_URL = "http://localhost:8000"


# ── API helpers ─────────────────────────────────────────────────────────────

async def api_get(path: str) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API_URL}{path}")
            return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def api_post(path: str, body: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{API_URL}{path}", json=body)
            return r.json() if r.status_code in (200, 201) else None
    except Exception:
        return None


async def api_put(path: str, body: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.put(f"{API_URL}{path}", json=body)
            return r.json() if r.status_code == 200 else None
    except Exception:
        return None


# ── Widgets ─────────────────────────────────────────────────────────────────

class GalaxyMap(Tree):
    """Interactive tree showing Sun → Planets → Biomes."""

    def __init__(self, **kwargs):
        super().__init__("☀ Sun", **kwargs)
        self.galaxy_data = None

    async def load(self):
        self.galaxy_data = await api_get("/api/v1/galaxy/status")
        self.clear()
        if not self.galaxy_data:
            self.root.add_leaf("⚠ No galaxy found")
            return
        self.root.label = f"☀ {self.galaxy_data.get('galaxy_name', 'Sun')}"
        for p in self.galaxy_data.get("planets", []):
            node = self.root.add(f"◉ {p['name']}  ({p['stardust_count']}✦)", data={"type": "planet", "id": p["id"], "name": p["name"]})
            # Fetch biomes with IDs for this planet
            biomes = await api_get(f"/api/v1/planets/{p['id']}/biomes") or []
            for b in biomes:
                if b.get("lifecycle_state") in ("SEED", "ACTIVE", "MATURE"):
                    node.add_leaf(f"● {b['name']}  {b['lifecycle_state']}", data={"type": "biome", "id": b["id"], "name": b["name"]})
        self.root.expand_all()


class NebulaFeed(VerticalScroll):
    """Live SSE event feed."""

    events: reactive[list] = reactive(list, init=False)

    def compose(self) -> ComposeResult:
        yield Label("[b]Nebula · Live[/b]", classes="feed-header")

    def add_event(self, event: dict):
        action = event.get("action_type", "?")
        by = event.get("initiated_by", "")
        ts = event.get("timestamp", "")
        age = ""
        if ts:
            try:
                diff = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds()
                age = f"{int(diff)}s" if diff < 60 else (f"{int(diff/60)}m" if diff < 3600 else f"{int(diff/3600)}h")
            except Exception:
                pass
        colors = {"WRITE": "magenta", "READ": "cyan", "ENTITY_EXTRACTED": "green", "ENTITY_ENRICHED": "yellow", "CONTRADICTION_DETECTED": "dark_orange", "AUDIT_RUN": "dim", "HUMAN_EDIT": "gold1"}
        color = colors.get(action, "white")
        name = event.get("entity_name", by)
        label = Label(f"[{color}]{action:<14}[/] {markup_escape(name):<16} {age}")
        self.mount(label, before=1 if self.children and len(self.children) > 1 else None)
        # Keep max 30 events
        while len(self.children) > 31:
            self.children[-1].remove()


class SunSummary(Static):
    """Shows current focus, blockers, hot biomes from Sun."""

    async def load(self):
        sun = await api_get("/api/v1/sun")
        if not sun:
            self.update("[dim]Sun not configured[/]")
            return
        wc = sun.get("working_context", {})
        focus = wc.get("current_focus", "—")
        blockers = wc.get("blockers", [])
        hot = wc.get("hot_biomes", [])
        text = f"[b gold1]Sun[/]\nFocus: {focus}"
        if hot:
            text += f"\nHot: {', '.join(hot)}"
        if blockers:
            text += f"\n[dark_orange]⚠ {len(blockers)} blocker(s)[/]"
        self.update(text)


# ── Screens ─────────────────────────────────────────────────────────────────

class GalaxyScreen(Screen):
    """Main Galaxy screen with tree map + nebula feed."""

    BINDINGS = [
        Binding("enter", "open_selected", "Open"),
        Binding("n", "new_stardust", "New"),
        Binding("s", "goto_search", "Search"),
        Binding("d", "goto_dashboard", "Dashboard"),
        Binding("u", "goto_sun", "Sun"),
        Binding("b", "goto_brain", "Brain"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="left-panel"):
                yield GalaxyMap(id="galaxy-map")
            with Vertical(id="right-panel"):
                yield NebulaFeed(id="nebula-feed")
                yield SunSummary(id="sun-summary")
        yield Footer()

    async def on_mount(self):
        await self.query_one("#galaxy-map", GalaxyMap).load()
        await self.query_one("#sun-summary", SunSummary).load()
        self.stream_sse()

    @work(exclusive=True)
    async def stream_sse(self):
        feed = self.query_one("#nebula-feed", NebulaFeed)
        retries = 0
        while retries < 5:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", f"{API_URL}/api/v1/nebula/stream") as resp:
                        retries = 0
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    event = json.loads(line[6:])
                                    self.app.call_from_thread(feed.add_event, event)
                                except Exception:
                                    pass
            except Exception:
                retries += 1
                await asyncio.sleep(min(2 ** retries, 30))

    def action_open_selected(self):
        tree = self.query_one("#galaxy-map", GalaxyMap)
        node = tree.cursor_node
        if node and node.data:
            if node.data.get("type") == "planet":
                self.app.push_screen(PlanetScreen(node.data["id"], node.data["name"]))
            elif node.data.get("type") == "biome":
                self.app.push_screen(BiomeScreen(node.data["id"], node.data["name"]))

    def action_new_stardust(self):
        self.app.push_screen(WriteScreen())

    def action_goto_search(self):
        self.app.push_screen(SearchScreen())

    def action_goto_dashboard(self):
        self.app.push_screen(DashboardScreen())

    def action_goto_sun(self):
        self.app.push_screen(SunScreen())

    def action_goto_brain(self):
        self.app.push_screen(BrainScreen())


class PlanetScreen(Screen):
    """Planet detail with biome list and recent stardust."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True), Binding("g", "goto_galaxy", "Galaxy")]

    def __init__(self, planet_id: str, planet_name: str):
        super().__init__()
        self.planet_id = planet_id
        self.planet_name = planet_name

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label(f"[b]🪐 {self.planet_name}[/b]", id="planet-title")
            with Horizontal():
                yield VerticalScroll(id="biome-list")
                yield VerticalScroll(id="stardust-list")
        yield Footer()

    async def on_mount(self):
        planet = await api_get(f"/api/v1/planets/{self.planet_id}")
        if not planet:
            return
        bl = self.query_one("#biome-list")
        for b in planet.get("biomes", []):
            state = b["lifecycle_state"]
            colors = {"ACTIVE": "cyan", "MATURE": "magenta", "SEED": "blue", "DORMANT": "dim"}
            bl.mount(Label(f"[{colors.get(state, 'white')}]● {b['name']}  {state}  {b['stardust_count']}✦[/]"))

        biomes = await api_get(f"/api/v1/planets/{self.planet_id}/biomes")
        sl = self.query_one("#stardust-list")
        if biomes:
            for b in biomes[:3]:
                sd = await api_get(f"/api/v1/biomes/{b['id']}/stardust?limit=5")
                for s in (sd or {}).get("items", []):
                    sl.mount(Label(f"[dim]{markup_escape(s['region'][:4])}[/] {markup_escape(s['content'][:80])}"))

    def action_goto_galaxy(self):
        self.app.pop_screen()

    def action_go_back(self):
        self.app.pop_screen()


class BiomeScreen(Screen):
    """Biome detail with stardust list and entities."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True), Binding("g", "goto_galaxy", "Galaxy")]

    def __init__(self, biome_id: str, biome_name: str = ""):
        super().__init__()
        self.biome_id = biome_id
        self.biome_name = biome_name

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label(f"[b]🌿 {self.biome_name}[/b]")
            yield VerticalScroll(id="biome-content")
        yield Footer()

    async def on_mount(self):
        content = self.query_one("#biome-content")
        content.mount(Label("[dim]Loading...[/]"))
        b = await api_get(f"/api/v1/biomes/{self.biome_id}")
        if not b:
            content.remove_children()
            content.mount(Label("[red]Biome not found[/]"))
            return
        content.remove_children()
        content.mount(Label(f"Lifecycle: {b['lifecycle_state']}  |  Stardust: {b['stardust_count']}  |  TTL: {b['cache_ttl_seconds']}s"))
        sd = await api_get(f"/api/v1/biomes/{self.biome_id}/stardust?limit=20") or {}
        for s in sd.get("items", []):
            conf = s.get("confidence", 0)
            color = "green" if conf >= 0.7 else ("yellow" if conf >= 0.4 else "red")
            content.mount(Label(f"\n[dim]{markup_escape(s['region'][:4])}[/] [{color}]{conf:.2f}[/]  {markup_escape(s['content'][:120])}"))

    def action_goto_galaxy(self):
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_go_back(self):
        self.app.pop_screen()


class SearchScreen(Screen):
    """Search with live results."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True)]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="Search your Galaxy...", id="search-input")
            yield VerticalScroll(id="search-results")
        yield Footer()

    def action_go_back(self):
        self.app.pop_screen()

    async def on_input_changed(self, event: Input.Changed):
        query = event.value.strip()
        results_container = self.query_one("#search-results")
        results_container.remove_children()
        if len(query) < 2:
            return
        data = await api_get(f"/api/v1/search?query={query}&limit=10")
        if not data:
            return
        for r in data.get("records", []):
            conf = r.get("confidence", 0)
            color = "green" if conf >= 0.7 else ("yellow" if conf >= 0.4 else "red")
            results_container.mount(Label(
                f"[dim]{markup_escape(r.get('region', '?')[:4])}[/] [{color}]{conf:.2f}[/]  "
                f"{markup_escape(r.get('planet_name', ''))} › {markup_escape(r.get('biome_name', ''))}\n"
                f"  {markup_escape(r.get('content', '')[:120])}"
            ))


class SunScreen(Screen):
    """Sun viewer with section tabs."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("tab", "next_tab", "Next Section", priority=True),
    ]

    SECTIONS = ["identity", "values", "agent_protocol", "planet_registry", "working_context", "evolution_log"]

    def __init__(self):
        super().__init__()
        self.current_tab = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("[b gold1]☀ Sun · Steering Document[/]", id="sun-title")
            yield Label("", id="sun-tabs")
            yield VerticalScroll(id="sun-content")
        yield Footer()

    async def on_mount(self):
        await self.load_section()

    async def load_section(self):
        key = self.SECTIONS[self.current_tab]
        tabs = "  ".join(f"[b reverse] {k} [/]" if i == self.current_tab else f" {k} " for i, k in enumerate(self.SECTIONS))
        self.query_one("#sun-tabs").update(tabs)

        content = self.query_one("#sun-content")
        content.remove_children()

        if key == "evolution_log":
            log = await api_get("/api/v1/sun/evolution-log") or []
            for e in reversed(log[-20:]):
                content.mount(Label(
                    f"[dim]{markup_escape(e.get('timestamp', '')[:16])}[/]  "
                    f"[cyan]{markup_escape(e.get('section_changed', ''))}[/]  "
                    f"by {markup_escape(e.get('changed_by', ''))}  "
                    f"{markup_escape(e.get('summary', ''))}"
                ))
            if not log:
                content.mount(Label("[dim]No changes recorded yet.[/]"))
        else:
            data = await api_get(f"/api/v1/sun/{key}")
            if data and "content" in data:
                section = data["content"]
                if isinstance(section, dict):
                    for k, v in section.items():
                        val = json.dumps(v, indent=2) if isinstance(v, (list, dict)) else str(v)
                        content.mount(Label(f"[b]{markup_escape(k)}[/]\n  {markup_escape(val)}"))
                else:
                    content.mount(Label(markup_escape(str(section))))

    def action_next_tab(self):
        self.current_tab = (self.current_tab + 1) % len(self.SECTIONS)
        self.run_worker(self.load_section(), exit_on_error=False)

    def action_go_back(self):
        self.app.pop_screen()


class BrainScreen(Screen):
    """Brain screen — agent roster, health scores, expertise profiles, session quality."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True), Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("[b]🧠 Brain · Agent Roster[/b]", id="brain-title")
            yield VerticalScroll(id="brain-content")
        yield Footer()

    async def on_mount(self):
        await self.load_agents()

    async def load_agents(self):
        content = self.query_one("#brain-content")
        content.remove_children()
        agents = await api_get("/api/v1/agents") or []
        if not agents:
            content.mount(Label("[dim]No agents have connected yet.[/]"))
            return

        for a in agents:
            name = markup_escape(a.get("agent_name", "?"))
            model = markup_escape(a.get("current_model", "?"))
            sessions = a.get("total_sessions", 0)
            reads = a.get("total_reads", 0)
            writes = a.get("total_writes", 0)
            quality = a.get("retrieval_quality_score", 0)
            born = a.get("birth_date", "")[:10] if a.get("birth_date") else "—"

            content.mount(Label(
                f"\n[b cyan]{name}[/]  {model}\n"
                f"  Sessions: {sessions}  |  Reads: {reads}  |  Writes: {writes}  |  Quality: {quality:.2f}  |  Born: {born}"
            ))

            # Fetch expertise
            expertise = await api_get(f"/api/v1/agents/{a['agent_name']}/expertise") or []
            if isinstance(expertise, list) and expertise:
                for e in expertise[:5]:
                    level = e.get("level", 0)
                    bar_len = int(level * 12)
                    bar = "█" * bar_len + "░" * (12 - bar_len)
                    content.mount(Label(f"    {markup_escape(e['domain']):<20s} {bar} {level:.2f}  ({e.get('evidence_count', 0)} records)"))

            # Fetch health
            health = await api_get(f"/api/v1/agents/{a['agent_name']}/health")
            if health and "overall_health" in health:
                h = health["overall_health"]
                color = "green" if h >= 0.8 else ("dark_orange" if h >= 0.6 else "red")
                content.mount(Label(f"    Health: [{color}]{h:.2f}[/]  |  Freshness: {health.get('knowledge_freshness', 0):.2f}  |  Age: {health.get('brain_age_days', 0)} days"))
                for rec in health.get("recommended_enrichment", [])[:2]:
                    content.mount(Label(f"    [dark_orange]→ {markup_escape(rec)}[/]"))

    def action_refresh(self):
        self.run_worker(self.load_agents(), exit_on_error=False)

    def action_go_back(self):
        self.app.pop_screen()


class DashboardScreen(Screen):
    """Nebula dashboard with metrics."""

    BINDINGS = [Binding("escape", "go_back", "Back", priority=True), Binding("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("[b]Nebula Dashboard[/b]", id="dash-title")
            yield VerticalScroll(id="dash-content")
        yield Footer()

    async def on_mount(self):
        await self.load_dashboard()

    async def load_dashboard(self):
        content = self.query_one("#dash-content")
        content.remove_children()
        data = await api_get("/api/v1/nebula/dashboard?days=30")
        if not data:
            content.mount(Label("[dim]No data available.[/]"))
            return
        s = data.get("summary", {})
        content.mount(Label(
            f"[b]Stardust[/] {s.get('total_stardust', 0)}    "
            f"[b]This Week[/] +{s.get('added_this_week', 0)}    "
            f"[b]Today[/] +{s.get('added_today', 0)}    "
            f"[b]Avg Conf[/] {s.get('avg_confidence', 0):.3f}    "
            f"[b]Biomes[/] {s.get('active_biomes', 0)}    "
            f"[b]Contradictions[/] {'⚠ ' if s.get('unresolved_contradictions', 0) > 0 else ''}{s.get('unresolved_contradictions', 0)}"
        ))

        # Knowledge gaps
        gaps = data.get("knowledge_gaps", [])
        if gaps:
            content.mount(Label("\n[b]Knowledge Gaps ⚠[/]"))
            for g in gaps:
                color = "red" if g["read_write_ratio"] > 10 else ("dark_orange" if g["read_write_ratio"] > 5 else "dim")
                content.mount(Label(f"  [{color}]{'⚠ ' if g['read_write_ratio'] > 5 else '  '}{g['biome_name']:<20} {g['planet_name']:<16} {g['read_write_ratio']:.1f}× more reads[/]"))

        # Top entities
        entities = data.get("top_entities", [])
        if entities:
            content.mount(Label("\n[b]Top Entities[/]"))
            for e in entities[:10]:
                tier_style = "bold magenta" if e["tier"] >= 3 else ("magenta" if e["tier"] >= 2 else "dim")
                content.mount(Label(f"  [{tier_style}]◆[/] {e['name']:<20} {e['entity_type']:<10} tier {e['tier']}  {e['linked_stardust']} records · {e['biomes_spanning']} biomes"))

        # Growth sparkline (simple ASCII)
        growth = data.get("growth_over_time", [])
        if growth:
            content.mount(Label("\n[b]Growth (cumulative)[/]"))
            vals = [g["cumulative"] for g in growth[-30:]]
            if vals:
                mx = max(vals) or 1
                bars = "".join("▁▂▃▄▅▆▇█"[min(7, int(v / mx * 7))] for v in vals)
                content.mount(Label(f"  {bars}  ({vals[-1]} total)"))

    def action_refresh(self):
        self.run_worker(self.load_dashboard())

    def action_go_back(self):
        self.app.pop_screen()


class WriteScreen(Screen):
    """Quick write stardust."""

    BINDINGS = [Binding("escape", "go_back", "Cancel", priority=True)]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("[b]✦ Add to Galaxy[/b]")
            yield Input(placeholder="Planet name", id="write-planet")
            yield TextArea(id="write-content")
            yield Label("[dim]Press Ctrl+S to submit, Escape to cancel[/]")
            yield Label("", id="write-status")
        yield Footer()

    async def on_key(self, event):
        if event.key == "ctrl+s":
            planet = self.query_one("#write-planet", Input).value.strip()
            content = self.query_one("#write-content", TextArea).text.strip()
            if not planet or not content:
                self.query_one("#write-status").update("[red]Planet and content required[/]")
                return
            result = await api_post("/api/v1/stardust/quick-capture", {"content": content, "planet": planet, "region": "contextual"})
            if result:
                self.query_one("#write-status").update(f"[green]✓ Written! id={result.get('stardust_id', '?')[:8]}[/]")
                await asyncio.sleep(1)
                self.app.pop_screen()
            else:
                self.query_one("#write-status").update("[red]Error writing stardust[/]")

    def action_go_back(self):
        self.app.pop_screen()


# ── Main App ────────────────────────────────────────────────────────────────

class OrionApp(App):
    """Orion TUI — terminal interface for the Galaxy."""

    TITLE = "✦ ORION"
    CSS = """
    Screen { background: #07041A; }
    Header { background: #0F0A2E; color: #E9D5FF; }
    Footer { background: #0F0A2E; }
    #left-panel { width: 1fr; min-width: 30; padding: 1; }
    #right-panel { width: 1fr; max-width: 50; padding: 1; border-left: solid #1A1040; }
    #galaxy-map { height: 1fr; }
    #nebula-feed { height: 2fr; }
    .feed-header { color: #7C6AAD; }
    #sun-summary { height: auto; padding: 1; border-top: solid #1A1040; }
    #search-input { margin: 1; }
    #search-results { padding: 1; }
    #sun-tabs { padding: 0 1; color: #7C6AAD; }
    #sun-content { padding: 1; }
    #dash-content { padding: 1; }
    #write-content { height: 10; margin: 1 0; }
    #write-planet { margin: 1 0 0 0; }
    #write-status { margin: 1 0; }
    Label { margin: 0; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
    ]

    def on_mount(self):
        self.push_screen(GalaxyScreen())

    def action_help(self):
        self.notify(
            "Q=Quit  G=Galaxy  S=Search  D=Dashboard  U=Sun  B=Brain  N=New  ?=Help\n"
            "These shortcuts work from the Galaxy screen. Press ESC to go back from any screen.",
            title="Keybindings", timeout=5,
        )


def run_tui():
    """Entry point for `orion tui`."""
    app = OrionApp()
    app.run()
