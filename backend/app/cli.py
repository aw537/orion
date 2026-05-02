"""Orion CLI — manage your local knowledge Galaxy from the terminal."""
import json
import os
import subprocess
import sys

import click
import httpx

API_URL = os.environ.get("ORION_API_URL", "http://localhost:8000")
PROJECT_DIR = os.environ.get("ORION_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helpers ─────────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        return httpx.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    except httpx.ConnectError:
        click.secho("Error: Orion is not running. Start it with `orion start`", fg="red")
        sys.exit(1)


def _print_json(data):
    click.echo(json.dumps(data, indent=2, default=str))


def _table(headers: list[str], rows: list[list[str]], pad: int = 2):
    """Print a simple aligned table."""
    if not rows:
        click.secho("  (none)", dim=True)
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))
    sep = " " * pad
    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    click.secho(header_line, bold=True)
    click.echo(sep.join("─" * w for w in widths))
    for row in rows:
        click.echo(sep.join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))


def _short_id(uid: str) -> str:
    return uid[:8] if uid else "—"


def _ts(val) -> str:
    if not val:
        return "—"
    if isinstance(val, str):
        return val[:19]
    return val.isoformat()[:19]


# ── Root group ──────────────────────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="orion")
def cli():
    """Orion — AI-powered local knowledge architecture."""
    pass


# ── Lifecycle ───────────────────────────────────────────────────────────────

@cli.command()
@click.option("-d", "--detach", is_flag=True, help="Run in background (no TUI)")
@click.option("--build", is_flag=True, help="Rebuild images before starting")
@click.option("--no-tui", is_flag=True, help="Skip opening the TUI after start")
def start(detach, build, no_tui):
    """Boot up Orion services, then open the TUI."""
    cmd = ["docker", "compose", "up", "-d"]
    if build:
        cmd.append("--build")
    click.secho("🚀 Starting Orion...", fg="cyan")
    subprocess.run(cmd, cwd=PROJECT_DIR)
    if detach or no_tui:
        click.secho("Services started in background.", fg="green")
        return
    # Wait for API to be ready, then open TUI
    _wait_and_launch_tui()


@cli.command()
def stop():
    """Shut down Orion."""
    click.secho("Stopping Orion...", fg="yellow")
    subprocess.run(["docker", "compose", "down"], cwd=PROJECT_DIR)


@cli.command()
def restart():
    """Restart Orion."""
    subprocess.run(["docker", "compose", "restart"], cwd=PROJECT_DIR)


@cli.command()
def logs():
    """Tail Orion service logs."""
    subprocess.run(["docker", "compose", "logs", "-f", "--tail=50"], cwd=PROJECT_DIR)


# ── Status ──────────────────────────────────────────────────────────────────

@cli.command()
def status():
    """Show Galaxy status and service health."""
    try:
        health = httpx.get(f"{API_URL}/health", timeout=5).json()
        status_str = click.style(health["status"], fg="green" if health["status"] == "ok" else "yellow")
        click.echo(f"Services: {status_str}")
        if health.get("degraded"):
            click.secho(f"  Degraded: {', '.join(health['degraded'])}", fg="yellow")
    except httpx.ConnectError:
        click.secho("Services: offline", fg="red")
        return

    resp = _api("GET", "/api/v1/galaxy/status")
    if resp.status_code != 200:
        click.secho("No Galaxy found. Run `orion init` to create one.", fg="yellow")
        return
    g = resp.json()
    click.echo(f"\n✨ {g['galaxy_name']}")
    click.echo(f"   Strength: {g['strength_score']:.1f}  |  Stardust: {g['total_stardust']}  |  Entities: {g['total_entities']}")
    if g.get("contradiction_count_unresolved"):
        click.secho(f"   ⚠ {g['contradiction_count_unresolved']} unresolved contradictions", fg="yellow")
    for p in g.get("planets", []):
        biomes = ", ".join(p.get("active_biomes", [])) or "none"
        click.echo(f"   🪐 {p['name']} ({p['stardust_count']} stardust) — biomes: {biomes}")


# ── Galaxy init ─────────────────────────────────────────────────────────────

@cli.command()
@click.option("--role", prompt="Your primary role", type=click.Choice(["Developer", "Designer", "Researcher", "Other"]), default="Developer")
@click.option("--biome", prompt="First project/biome name", default="General")
@click.option("--import-path", default=None, help="Markdown folder to import")
@click.option("--name", default="", help="Your name")
@click.option("--goal", default="", help="Current goal or challenge")
@click.option("--tools", default="", help="Comma-separated tools/technologies")
@click.option("--style", default="direct", type=click.Choice(["direct", "thorough", "socratic"]), help="Communication style")
def init(role, biome, import_path, name, goal, tools, style):
    """Initialize a new Galaxy (onboarding)."""
    tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else []
    resp = _api("POST", "/api/v1/onboarding/start", json={
        "role": role, "first_biome_name": biome, "import_path": import_path,
        "name": name, "goal": goal, "tools": tool_list,
        "communication_style": style, "contradiction_preference": "flag_and_ask",
    })
    if resp.status_code == 201:
        data = resp.json()
        click.secho(f"✨ Galaxy created!", fg="green")
        click.echo(f"   Planets: {', '.join(data['planets'])}")
        click.echo(f"   First biome: {biome}")
        click.echo(f"   Stardust: {data.get('stardust_count', 0)}  |  Entities: {data.get('entities_count', 0)}")
        click.echo(f"   Sun configured: {'✓' if data.get('sun_configured') else '✗'}")
        if data.get("import_started"):
            click.echo(f"   📥 Import started from {import_path}")
    elif resp.status_code == 400:
        click.secho("Galaxy already exists.", fg="yellow")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Import ──────────────────────────────────────────────────────────────────

@cli.command("import")
@click.argument("path", type=click.Path(exists=True))
@click.option("-p", "--planet", default="Engineering", help="Target planet")
def import_md(path, planet):
    """Import a markdown folder into the Galaxy."""
    _import_impl(path, planet)


def _import_impl(path, planet):
    resp = _api("GET", "/api/v1/planets")
    planets = resp.json() if resp.status_code == 200 else []
    target = next((p for p in planets if p["name"].lower() == planet.lower()), None)
    if not target:
        click.secho(f"Planet '{planet}' not found.", fg="red")
        return
    abs_path = os.path.abspath(path)
    resp = _api("POST", f"/api/v1/onboarding/import?planet_id={target['id']}&path={abs_path}")
    if resp.status_code == 200:
        click.secho(f"📥 Import started from {abs_path} → {planet}", fg="green")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Audit ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--run", "trigger", is_flag=True, help="Trigger an audit now")
def audit(trigger):
    """Show last audit or trigger a new one."""
    if trigger:
        click.secho("🔧 Running audit...", fg="cyan")
        resp = _api("POST", "/api/v1/audit/run")
        if resp.status_code == 200:
            data = resp.json()
            click.secho("Audit complete!", fg="green")
            click.echo(f"   Reviewed: {data.get('records_reviewed', 0)} | Merged: {data.get('duplicates_merged', 0)}")
            click.echo(f"   Contradictions: {data.get('contradictions_found', 0)} | Decayed: {data.get('confidence_decays', 0)}")
            click.echo(f"   Promoted: {data.get('promotions_made', 0)} | Duration: {data.get('duration_ms', 0)}ms")
        else:
            click.secho(f"Error: {resp.text}", fg="red")
    else:
        resp = _api("GET", "/api/v1/audit/status")
        data = resp.json()
        if data.get("status") == "no_audits_run":
            click.echo("No audits have run yet. Use `orion audit --run` to trigger one.")
        else:
            click.echo(f"Last audit: {data.get('run_at', '—')}")
            click.echo(f"   Reviewed: {data.get('records_reviewed', 0)} | Merged: {data.get('duplicates_merged', 0)}")
            click.echo(f"   Contradictions: {data.get('contradictions_found', 0)} | Duration: {data.get('duration_ms', 0)}ms")


# ── Reset ───────────────────────────────────────────────────────────────────

@cli.command()
@click.confirmation_option(prompt="This will destroy all data. Are you sure?")
def reset():
    """Destroy all data and start fresh."""
    click.secho("🗑️  Resetting Orion...", fg="red")
    subprocess.run(["docker", "compose", "down", "-v"], cwd=PROJECT_DIR)
    data_dir = os.path.join(PROJECT_DIR, "data")
    if os.path.exists(data_dir):
        import shutil
        shutil.rmtree(data_dir)
        os.makedirs(data_dir)
    click.secho("Reset complete. Run `orion start` to begin fresh.", fg="green")


# ── MCP connect ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("tool", default="claude")
def connect(tool):
    """Show how to connect an AI tool to Orion's MCP server."""
    commands = {
        "claude": "claude mcp add orion --transport http http://localhost:8787/mcp",
        "cursor": 'Add to .cursor/mcp.json:\n  {"orion": {"transport": "http", "url": "http://localhost:8787/mcp"}}',
    }
    if tool in commands:
        click.echo(f"Run this to connect {tool}:\n")
        click.secho(f"  {commands[tool]}", fg="cyan")
    else:
        click.echo(f"MCP endpoint: http://localhost:8787/mcp")
        click.echo("Add this URL to any MCP-compatible tool.")


# ── Search ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("-p", "--planet", default=None, help="Filter by planet name")
@click.option("-b", "--biome", default=None, help="Filter by biome name")
@click.option("-r", "--region", default=None, type=click.Choice(["analytical", "procedural", "contextual"]))
@click.option("-n", "--limit", default=5, help="Max results")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def search(query, planet, biome, region, limit, as_json):
    """Search the Galaxy for knowledge."""
    _search_impl(query, planet, biome, region, limit, as_json)


def _search_impl(query, planet, biome, region, limit, as_json=False):
    params = {"query": query, "limit": limit}
    if planet:
        params["planet"] = planet
    if biome:
        params["biome"] = biome
    if region:
        params["region"] = region
    resp = _api("GET", "/api/v1/search", params=params)
    if resp.status_code == 404:
        click.secho("No Galaxy found. Run `orion init` first.", fg="yellow")
        return
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    records = data.get("records", [])
    meta = data.get("retrieval_metadata", {})
    click.echo(f"🔍 {len(records)} results for \"{query}\" ({meta.get('retrieval_latency_ms', 0)}ms)")
    if not records:
        click.secho("  No matching stardust found.", dim=True)
        return
    for i, r in enumerate(records, 1):
        conf = r.get("confidence", 0)
        color = "green" if conf >= 0.7 else ("yellow" if conf >= 0.4 else "red")
        click.echo()
        click.echo(f"  {i}. [{r.get('region', '?')[:4]}] ", nl=False)
        click.secho(f"conf={conf:.2f}", fg=color, nl=False)
        click.echo(f"  {r.get('planet_name', '')} › {r.get('biome_name', '')}")
        content = r.get("content", "")
        click.echo(f"     {content[:120]}{'…' if len(content) > 120 else ''}")
        tags = r.get("context_tags", [])
        if tags:
            click.secho(f"     tags: {', '.join(tags)}", dim=True)


# ── Write ───────────────────────────────────────────────────────────────────

@cli.command("write")
@click.argument("content")
@click.option("-p", "--planet", required=True, help="Planet name")
@click.option("-b", "--biome", default=None, help="Biome name")
@click.option("-r", "--region", default="contextual", type=click.Choice(["analytical", "procedural", "contextual"]))
@click.option("-t", "--tags", default="", help="Comma-separated context tags")
@click.option("-g", "--gravity", default="BIOME", type=click.Choice(["BIOME", "PLANET", "GALAXY"]))
def write_stardust(content, planet, biome, region, tags, gravity):
    """Write a Stardust record to the Galaxy."""
    _write_impl(content, planet, biome, region, tags, gravity)


def _write_impl(content, planet, biome, region, tags, gravity):
    resp = _api("GET", "/api/v1/planets")
    if resp.status_code != 200:
        click.secho("Error fetching planets.", fg="red")
        return
    planets = resp.json()
    target = next((p for p in planets if p["name"].lower() == planet.lower()), None)
    if not target:
        click.secho(f"Planet '{planet}' not found. Available: {', '.join(p['name'] for p in planets)}", fg="red")
        return

    biomes_resp = _api("GET", f"/api/v1/planets/{target['id']}/biomes")
    biomes_list = biomes_resp.json() if biomes_resp.status_code == 200 else []
    if biome:
        target_biome = next((b for b in biomes_list if b["name"].lower() == biome.lower()), None)
    else:
        target_biome = biomes_list[0] if biomes_list else None
    if not target_biome:
        click.secho(f"No biome found. Available: {', '.join(b['name'] for b in biomes_list)}", fg="red")
        return

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    resp = _api("POST", f"/api/v1/biomes/{target_biome['id']}/stardust", json={
        "content": content, "region": region, "context_tags": tag_list, "gravity": gravity,
    })
    if resp.status_code == 201:
        data = resp.json()
        click.secho(f"✏️  Written! id={data['stardust_id'][:8]}...", fg="green")
        click.echo(f"   Planet: {planet} → Biome: {target_biome['name']} | Contradiction: {data['contradiction_check']}")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Context ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("-p", "--planet", default=None, help="Planet name")
@click.option("-b", "--biome", default=None, help="Biome name")
@click.option("--max-tokens", default=4000, help="Token budget")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def context(planet, biome, max_tokens, as_json):
    """Get a structured context bundle for the current session."""
    params = {"max_tokens": max_tokens}
    if planet:
        params["planet"] = planet
    if biome:
        params["biome"] = biome
    # Context is available via MCP; we build it from sub-endpoints
    # Sun
    resp_sun = _api("GET", "/api/v1/sun")
    if resp_sun.status_code != 200:
        click.secho("No Galaxy found. Run `orion init` first.", fg="yellow")
        return
    sun = resp_sun.json()

    # Planets
    resp_planets = _api("GET", "/api/v1/planets")
    planets_data = resp_planets.json() if resp_planets.status_code == 200 else []

    # Resolve target planet
    if planet:
        target_p = next((p for p in planets_data if p["name"].lower() == planet.lower()), None)
    else:
        target_p = planets_data[0] if planets_data else None

    bundle = {"sun": sun}  # /api/v1/sun returns {section_key: content_dict}

    if target_p:
        biomes_resp = _api("GET", f"/api/v1/planets/{target_p['id']}/biomes")
        biomes_data = biomes_resp.json() if biomes_resp.status_code == 200 else []
        bundle["planet"] = {"name": target_p["name"], "biomes": [b["name"] for b in biomes_data]}

        if biome:
            target_b = next((b for b in biomes_data if b["name"].lower() == biome.lower()), None)
        else:
            target_b = biomes_data[0] if biomes_data else None
        if target_b:
            sd_resp = _api("GET", f"/api/v1/biomes/{target_b['id']}/stardust", params={"limit": 10})
            sd_data = sd_resp.json() if sd_resp.status_code == 200 else {}
            bundle["biome"] = {
                "name": target_b["name"],
                "lifecycle": target_b["lifecycle_state"],
                "stardust_count": target_b["stardust_count"],
                "recent": [{"content": s["content"][:100], "region": s["region"]} for s in sd_data.get("items", [])[:5]],
            }

    if as_json:
        _print_json(bundle)
        return

    click.secho("📦 Context Bundle", bold=True)
    click.echo()
    click.secho("Sun:", bold=True)
    for key, val in bundle.get("sun", {}).items():
        val_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
        click.echo(f"  {key}: {val_str[:80]}{'…' if len(val_str) > 80 else ''}")
    if bundle.get("planet"):
        click.echo()
        click.secho(f"Planet: {bundle['planet']['name']}", bold=True)
        click.echo(f"  Biomes: {', '.join(bundle['planet']['biomes']) or 'none'}")
    if bundle.get("biome"):
        b = bundle["biome"]
        click.echo()
        click.secho(f"Biome: {b['name']} ({b['lifecycle']})", bold=True)
        click.echo(f"  Stardust: {b['stardust_count']}")
        for s in b.get("recent", []):
            click.echo(f"  • [{s['region'][:4]}] {s['content']}")


# ── Strength ────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def strength(as_json):
    """Show Galaxy strength score with 5-dimension breakdown."""
    resp = _api("GET", "/api/v1/galaxy/strength")
    if resp.status_code == 404:
        click.secho("No Galaxy found. Run `orion init` first.", fg="yellow")
        return
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    grade = data.get("grade", "?")
    grade_color = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}.get(grade, "white")
    click.echo(f"✦ Strength: {data['score']} / 100  ", nl=False)
    click.secho(f"[{grade}]", fg=grade_color)
    click.echo(f"  {data.get('trend', '')}  ·  {data.get('days_active', 0)} days active")
    click.echo()
    dims = data.get("dimensions", {})
    for key in ["volume", "density", "health", "diversity", "coverage"]:
        d = dims.get(key, {})
        score = d.get("score", 0)
        bar_len = int(score / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        color = "green" if score >= 80 else ("cyan" if score >= 60 else ("yellow" if score >= 40 else "red"))
        click.echo(f"  {d.get('label', key):.<28s} ", nl=False)
        click.secho(f"{score:5.1f}  {bar}", fg=color)


# ── Quick capture ───────────────────────────────────────────────────────────

@cli.command()
@click.argument("content")
@click.option("-p", "--planet", required=True, help="Planet name")
@click.option("-r", "--region", default="contextual", type=click.Choice(["analytical", "procedural", "contextual"]))
def capture(content, planet, region):
    """Quick-capture a stardust record (auto-resolves biome)."""
    resp = _api("POST", "/api/v1/stardust/quick-capture", json={
        "content": content, "planet": planet, "region": region,
    })
    if resp.status_code == 201:
        data = resp.json()
        click.secho(f"✏️  Captured! id={_short_id(data['stardust_id'])}", fg="green")
        click.echo(f"   Biome: {_short_id(data['biome_id'])} | Contradiction: {data['contradiction_check']}")
    elif resp.status_code == 404:
        click.secho(f"Planet '{planet}' not found.", fg="red")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Planet commands ─────────────────────────────────────────────────────────

@cli.group()
def planet():
    """Manage planets (knowledge domains)."""
    pass


@planet.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def planet_list(as_json):
    """List all planets."""
    resp = _api("GET", "/api/v1/planets")
    if resp.status_code != 200:
        click.secho("Error fetching planets.", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    if not data:
        click.secho("No planets. Run `orion init` first.", fg="yellow")
        return
    rows = []
    for p in data:
        rows.append([_short_id(p["id"]), p["name"], str(p["stardust_count"]), p.get("health_status", "—"), p.get("color", "")])
    _table(["ID", "Name", "Stardust", "Health", "Color"], rows)


@planet.command("create")
@click.argument("name")
@click.option("--desc", default=None, help="Description")
@click.option("--color", default="#6D28D9", help="Hex color")
def planet_create(name, desc, color):
    """Create a new planet."""
    resp = _api("POST", "/api/v1/planets", json={"name": name, "description": desc, "color": color})
    if resp.status_code == 201:
        p = resp.json()
        click.secho(f"🪐 Planet '{p['name']}' created (id={_short_id(p['id'])})", fg="green")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


@planet.command("show")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def planet_show(name, as_json):
    """Show planet details with biomes."""
    resp = _api("GET", "/api/v1/planets")
    planets = resp.json() if resp.status_code == 200 else []
    target = next((p for p in planets if p["name"].lower() == name.lower()), None)
    if not target:
        click.secho(f"Planet '{name}' not found.", fg="red")
        return
    resp = _api("GET", f"/api/v1/planets/{target['id']}")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    click.secho(f"🪐 {data['name']}", bold=True)
    click.echo(f"   ID: {data['id']}")
    click.echo(f"   Color: {data.get('color', '—')}  |  Stardust: {data['stardust_count']}  |  Health: {data.get('health_status', '—')}")
    if data.get("description"):
        click.echo(f"   {data['description']}")
    biomes = data.get("biomes", [])
    if biomes:
        click.echo()
        rows = [[_short_id(b["id"]), b["name"], b["lifecycle_state"], str(b["stardust_count"])] for b in biomes]
        _table(["ID", "Biome", "Lifecycle", "Stardust"], rows)
    else:
        click.secho("   No biomes yet.", dim=True)


# ── Biome commands ──────────────────────────────────────────────────────────

@cli.group()
def biome():
    """Manage biomes (project contexts)."""
    pass


def _resolve_planet_id(name: str) -> str | None:
    resp = _api("GET", "/api/v1/planets")
    planets = resp.json() if resp.status_code == 200 else []
    target = next((p for p in planets if p["name"].lower() == name.lower()), None)
    return target["id"] if target else None


@biome.command("list")
@click.option("-p", "--planet", required=True, help="Planet name")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def biome_list(planet, as_json):
    """List biomes for a planet."""
    pid = _resolve_planet_id(planet)
    if not pid:
        click.secho(f"Planet '{planet}' not found.", fg="red")
        return
    resp = _api("GET", f"/api/v1/planets/{pid}/biomes")
    data = resp.json() if resp.status_code == 200 else []
    if as_json:
        _print_json(data)
        return
    if not data:
        click.secho(f"No biomes on planet '{planet}'.", dim=True)
        return
    rows = [[_short_id(b["id"]), b["name"], b["lifecycle_state"], str(b["stardust_count"]), str(b["cache_ttl_seconds"])] for b in data]
    _table(["ID", "Name", "Lifecycle", "Stardust", "TTL"], rows)


@biome.command("create")
@click.option("-p", "--planet", required=True, help="Planet name")
@click.argument("name")
@click.option("--desc", default=None, help="Description")
def biome_create(planet, name, desc):
    """Create a new biome on a planet."""
    pid = _resolve_planet_id(planet)
    if not pid:
        click.secho(f"Planet '{planet}' not found.", fg="red")
        return
    resp = _api("POST", f"/api/v1/planets/{pid}/biomes", json={"name": name, "description": desc})
    if resp.status_code == 201:
        b = resp.json()
        click.secho(f"🌿 Biome '{b['name']}' created (id={_short_id(b['id'])})", fg="green")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


@biome.command("show")
@click.argument("biome_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def biome_show(biome_id, as_json):
    """Show biome details by ID (or first 8 chars)."""
    resp = _api("GET", f"/api/v1/biomes/{biome_id}")
    if resp.status_code == 404:
        click.secho("Biome not found.", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    click.secho(f"🌿 {data['name']}", bold=True)
    click.echo(f"   ID: {data['id']}")
    click.echo(f"   Planet: {_short_id(data['planet_id'])}  |  Lifecycle: {data['lifecycle_state']}  |  Stardust: {data['stardust_count']}")
    click.echo(f"   TTL: {data['cache_ttl_seconds']}s  |  Last active: {_ts(data.get('last_active_at'))}")
    if data.get("description"):
        click.echo(f"   {data['description']}")


@biome.command("lifecycle")
@click.argument("biome_id")
@click.argument("state", type=click.Choice(["SEED", "ACTIVE", "MATURE", "DORMANT", "ARCHIVED"]))
def biome_lifecycle(biome_id, state):
    """Update biome lifecycle state."""
    resp = _api("PUT", f"/api/v1/biomes/{biome_id}/lifecycle", json={"lifecycle_state": state})
    if resp.status_code == 200:
        b = resp.json()
        click.secho(f"🌿 '{b['name']}' → {state}", fg="green")
    elif resp.status_code == 404:
        click.secho("Biome not found.", fg="red")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Stardust commands ───────────────────────────────────────────────────────

@cli.group()
def stardust():
    """Manage stardust records (atomic knowledge)."""
    pass


@stardust.command("list")
@click.argument("biome_id")
@click.option("-n", "--limit", default=20, help="Max results")
@click.option("--offset", default=0, help="Pagination offset")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def stardust_list(biome_id, limit, offset, as_json):
    """List stardust in a biome."""
    resp = _api("GET", f"/api/v1/biomes/{biome_id}/stardust", params={"limit": limit, "offset": offset})
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    items = data.get("items", [])
    total = data.get("total", 0)
    click.echo(f"Stardust ({len(items)}/{total}):")
    if not items:
        click.secho("  (empty)", dim=True)
        return
    rows = []
    for s in items:
        rows.append([
            _short_id(s["id"]),
            s["region"][:4],
            f"{s['confidence']:.2f}",
            s["gravity"],
            s["content"][:60] + ("…" if len(s["content"]) > 60 else ""),
        ])
    _table(["ID", "Rgn", "Conf", "Gravity", "Content"], rows)


@stardust.command("get")
@click.argument("stardust_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def stardust_get(stardust_id, as_json):
    """Get a single stardust record."""
    resp = _api("GET", f"/api/v1/stardust/{stardust_id}")
    if resp.status_code == 404:
        click.secho("Stardust not found.", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    click.secho(f"⭐ Stardust {_short_id(data['id'])}", bold=True)
    click.echo(f"   Region: {data['region']}  |  Gravity: {data['gravity']}  |  Confidence: {data['confidence']:.2f}")
    click.echo(f"   Planet: {_short_id(data['planet_id'])}  |  Biome: {_short_id(data['biome_id'])}")
    click.echo(f"   Created: {_ts(data['created_at'])}  |  Accessed: {data['access_count']}x")
    tags = data.get("context_tags", [])
    if tags:
        click.echo(f"   Tags: {', '.join(tags)}")
    if data.get("source_agent"):
        click.echo(f"   Agent: {data['source_agent']}")
    click.echo()
    click.echo(data["content"])


@stardust.command("update")
@click.argument("stardust_id")
@click.option("-c", "--content", default=None, help="New content")
@click.option("-t", "--tags", default=None, help="New comma-separated tags")
@click.option("-g", "--gravity", default=None, type=click.Choice(["BIOME", "PLANET", "GALAXY"]))
def stardust_update(stardust_id, content, tags, gravity):
    """Update a stardust record."""
    body = {}
    if content is not None:
        body["content"] = content
    if tags is not None:
        body["context_tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if gravity is not None:
        body["gravity"] = gravity
    if not body:
        click.secho("Nothing to update. Use -c, -t, or -g.", fg="yellow")
        return
    resp = _api("PUT", f"/api/v1/stardust/{stardust_id}", json=body)
    if resp.status_code == 200:
        click.secho(f"⭐ Updated {_short_id(stardust_id)}", fg="green")
    elif resp.status_code == 404:
        click.secho("Stardust not found.", fg="red")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


# ── Entity commands ─────────────────────────────────────────────────────────

@cli.group()
def entity():
    """Browse extracted entities (people, tools, concepts)."""
    pass


@entity.command("list")
@click.option("-n", "--limit", default=20, help="Max results")
@click.option("--type", "entity_type", default=None, help="Filter by type (PERSON, TOOL, etc.)")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def entity_list(limit, entity_type, as_json):
    """List entities in the Galaxy."""
    params = {"limit": limit}
    if entity_type:
        params["entity_type"] = entity_type
    resp = _api("GET", "/api/v1/entities", params=params)
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    items = data.get("items", [])
    total = data.get("total", 0)
    click.echo(f"Entities ({len(items)}/{total}):")
    if not items:
        click.secho("  (none)", dim=True)
        return
    rows = [[_short_id(e["id"]), e["name"], e["entity_type"], str(e["tier"]), str(e["mention_count"])] for e in items]
    _table(["ID", "Name", "Type", "Tier", "Mentions"], rows)


@entity.command("get")
@click.argument("entity_id")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def entity_get(entity_id, as_json):
    """Get entity profile with relationships and timeline."""
    resp = _api("GET", f"/api/v1/entities/{entity_id}")
    if resp.status_code == 404:
        click.secho("Entity not found.", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    e = data["entity"]
    click.secho(f"👤 {e['name']} ({e['entity_type']})", bold=True)
    click.echo(f"   Tier: {e['tier']}  |  Mentions: {e['mention_count']}  |  First seen: {_ts(e['first_seen'])}")
    profile = e.get("profile", {})
    if profile:
        click.echo(f"   Profile: {json.dumps(profile)[:100]}")
    rel = data.get("relationship_types", [])
    if rel:
        click.echo(f"   Relationships: {', '.join(rel)}")
    related = data.get("related_stardust", [])
    if related:
        click.echo()
        click.secho("  Related stardust:", bold=True)
        for s in related[:5]:
            click.echo(f"    • [{s['region'][:4]}] {s['content'][:80]}{'…' if len(s['content']) > 80 else ''}")
    timeline = data.get("timeline", [])
    if timeline:
        click.echo()
        click.secho("  Timeline:", bold=True)
        for t in timeline[:10]:
            click.echo(f"    {t['event_date'][:10]} {t['event_type']}: {t['event_content'][:60]}")


# ── Nebula commands ─────────────────────────────────────────────────────────

@cli.group()
def nebula():
    """View the Nebula activity log and dashboard."""
    pass


@nebula.command("log")
@click.option("-n", "--limit", default=20, help="Max events")
@click.option("--type", "action_type", default=None, help="Filter by action type")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def nebula_log(limit, action_type, as_json):
    """Show recent Nebula events."""
    params = {"limit": limit}
    if action_type:
        params["action_type"] = action_type
    resp = _api("GET", "/api/v1/nebula", params=params)
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    events = data.get("events", [])
    total = data.get("total", 0)
    click.echo(f"Nebula events ({len(events)}/{total}):")
    if not events:
        click.secho("  (none)", dim=True)
        return
    rows = []
    for ev in events:
        rows.append([
            str(ev["event_id"]),
            ev["action_type"],
            ev["initiated_by"],
            _short_id(ev.get("record_id") or ""),
            _ts(ev["timestamp"]),
        ])
    _table(["#", "Action", "By", "Record", "Time"], rows)


@nebula.command("dashboard")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def nebula_dashboard(as_json):
    """Show Nebula dashboard stats."""
    resp = _api("GET", "/api/v1/nebula/dashboard")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    click.secho("📊 Nebula Dashboard", bold=True)
    click.echo(f"   Total events: {data.get('total_events', 0)}")
    click.echo(f"   Last 24h: {data.get('events_last_24h', 0)}")
    by_type = data.get("events_by_type", {})
    if by_type:
        click.echo()
        click.secho("  Events by type:", bold=True)
        for t, c in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            click.echo(f"    {t}: {c}")


# ── Sun commands ────────────────────────────────────────────────────────────

@cli.group()
def sun():
    """Manage the Sun (steering layer — values, rules, protocol)."""
    pass


@sun.command("show")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def sun_show(as_json):
    """Show all Sun sections."""
    resp = _api("GET", "/api/v1/sun")
    if resp.status_code != 200:
        click.secho("No Galaxy found.", fg="yellow")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
        return
    if not data:
        click.secho("Sun has no sections.", dim=True)
        return
    click.secho("☀️  Sun Sections", bold=True)
    for key, content in data.items():
        click.echo()
        click.secho(f"  [{key}]", bold=True)
        if isinstance(content, dict):
            for k, v in content.items():
                val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
                click.echo(f"    {k}: {val_str[:80]}{'…' if len(val_str) > 80 else ''}")
        elif isinstance(content, list):
            for item in content[:5]:
                click.echo(f"    • {item}")
        else:
            click.echo(f"    {str(content)[:120]}")


@sun.command("update")
@click.argument("section_key")
@click.argument("content")
def sun_update(section_key, content):
    """Update a Sun section's content."""
    # Try to parse content as JSON, otherwise wrap as string
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        parsed = content
    resp = _api("PUT", f"/api/v1/sun/{section_key}", json={"content": parsed})
    if resp.status_code == 200:
        s = resp.json()
        click.secho(f"☀️  Updated '{section_key}' → v{s['version']}", fg="green")
    elif resp.status_code == 404:
        click.secho(f"Section '{section_key}' not found.", fg="red")
    else:
        click.secho(f"Error: {resp.text}", fg="red")




# ── Memory subcommand group ────────────────────────────────────────────────

@cli.group("memory")
def memory():
    """Memory operations — knowledge management."""
    pass


@memory.command("write")
@click.argument("content")
@click.option("-p", "--planet", required=True, help="Planet name")
@click.option("-b", "--biome", default=None, help="Biome name")
@click.option("-r", "--region", default="contextual")
@click.option("-t", "--tags", default="", help="Comma-separated tags")
@click.option("-g", "--gravity", default="BIOME")
def memory_write(content, planet, biome, region, tags, gravity):
    """Write a Stardust record."""
    _write_impl(content, planet, biome, region, tags, gravity)


@memory.command("search")
@click.argument("query")
@click.option("-p", "--planet", default=None)
@click.option("-b", "--biome", default=None)
@click.option("-r", "--region", default=None, type=click.Choice(["analytical", "procedural", "contextual"]))
@click.option("-n", "--limit", default=5)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
def memory_search(query, planet, biome, region, limit, as_json):
    """Search the Galaxy for knowledge."""
    _search_impl(query, planet, biome, region, limit, as_json)


@memory.command("status")
def memory_status():
    """Show Galaxy status."""
    resp = _api("GET", "/api/v1/galaxy/status")
    if resp.status_code != 200:
        click.secho("No Galaxy found.", fg="yellow")
        return
    g = resp.json()
    click.echo(f"✨ {g['galaxy_name']}  |  Strength: {g['strength_score']:.1f}  |  Stardust: {g['total_stardust']}  |  Entities: {g['total_entities']}")


@memory.command("import")
@click.argument("path", type=click.Path(exists=True))
@click.option("-p", "--planet", default="Engineering")
def memory_import(path, planet):
    """Import a markdown folder."""
    _import_impl(path, planet)


@memory.command("export")
@click.argument("path", type=click.Path())
def memory_export(path):
    """Export Galaxy knowledge to a JSON file."""
    import json as _json
    import httpx

    try:
        resp = httpx.get(f"{API_URL}/api/v1/galaxy/status", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        click.secho(f"❌ Failed to fetch galaxy status: {e}", fg="red")
        raise SystemExit(1)

    out = os.path.expanduser(path)
    with open(out, "w") as f:
        _json.dump(data, f, indent=2, default=str)
    click.secho(f"📤 Exported galaxy status to {out}", fg="green")


# ── Brain subcommand group ──────────────────────────────────────────────────

@cli.group("brain")
def brain():
    """Brain operations — inspect agent cognitive state."""
    pass


@brain.command("status")
@click.argument("agent_name")
def brain_status(agent_name):
    """Show agent identity, top expertise, health score."""
    resp = _api("GET", f"/api/v1/agents/{agent_name}")
    if resp.status_code != 200:
        click.secho(f"Agent '{agent_name}' not found.", fg="red")
        return
    a = resp.json()
    if "error" in a:
        click.secho(a["error"], fg="red")
        return
    click.secho(f"🧠 {a['agent_name']} ({a['agent_type']})", bold=True)
    click.echo(f"   Model: {a['current_model']}  |  Sessions: {a['total_sessions']}  |  Reads: {a['total_reads']}  |  Writes: {a['total_writes']}")
    click.echo(f"   Quality: {a.get('retrieval_quality_score', 0):.2f}  |  Born: {_ts(a.get('birth_date'))}")
    # Top expertise
    exp_resp = _api("GET", f"/api/v1/agents/{agent_name}/expertise")
    if exp_resp.status_code == 200:
        expertise = exp_resp.json()
        if expertise and not isinstance(expertise, dict):
            click.echo("   Top expertise:")
            for e in expertise[:5]:
                bar = "█" * int(e["level"] * 12) + "░" * (12 - int(e["level"] * 12))
                click.echo(f"     {e['domain']:<20s} {bar} {e['level']:.2f}")


@brain.command("health")
@click.argument("agent_name")
def brain_health_cmd(agent_name):
    """Full brain health report."""
    resp = _api("GET", f"/api/v1/agents/{agent_name}/health")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    h = resp.json()
    if "error" in h:
        click.secho(h["error"], fg="red")
        return
    score = h.get("overall_health", 0)
    color = "green" if score >= 0.8 else ("yellow" if score >= 0.6 else "red")
    click.secho(f"🧠 Brain Health: {score:.2f}", fg=color, bold=True)
    click.echo(f"   Freshness: {h.get('knowledge_freshness', 0):.2f}  |  Items: {h.get('total_knowledge_items', 0)}  |  Age: {h.get('brain_age_days', 0)} days")
    gaps = h.get("coverage_gaps", [])
    if gaps:
        click.echo(f"   Gaps: {', '.join(gaps)}")
    stale = h.get("stale_beliefs", [])
    if stale:
        click.echo(f"   Stale beliefs: {len(stale)}")
    for rec in h.get("recommended_enrichment", []):
        click.secho(f"   → {rec}", fg="yellow")


@brain.command("expertise")
@click.argument("agent_name")
def brain_expertise(agent_name):
    """Full expertise breakdown."""
    resp = _api("GET", f"/api/v1/agents/{agent_name}/expertise")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        click.secho(data["error"], fg="red")
        return
    if not data:
        click.secho("No expertise recorded yet.", dim=True)
        return
    rows = [[e["domain"], f"{e['level']:.2f}", str(e["evidence_count"]), _ts(e.get("last_demonstrated"))] for e in data]
    _table(["Domain", "Level", "Evidence", "Last Demo"], rows)


@brain.command("sessions")
@click.argument("agent_name")
@click.option("-n", "--limit", default=10)
def brain_sessions(agent_name, limit):
    """Session history."""
    resp = _api("GET", f"/api/v1/agents/{agent_name}/sessions", params={"limit": limit})
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        click.secho(data["error"], fg="red")
        return
    if not data:
        click.secho("No sessions yet.", dim=True)
        return
    rows = [[_short_id(s["id"]), s.get("model_used", ""), _ts(s.get("started_at")), str(s.get("reads", 0)), str(s.get("writes", 0)), f"{s.get('session_quality_score') or 0:.2f}"] for s in data]
    _table(["ID", "Model", "Started", "Reads", "Writes", "Quality"], rows)


@brain.command("switches")
@click.argument("agent_name")
def brain_switches(agent_name):
    """Model switch history."""
    resp = _api("GET", "/api/v1/model-switches")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if not data:
        click.secho("No model switches recorded.", dim=True)
        return
    rows = [[s.get("previous_model", ""), "→", s.get("new_model", ""), f"{s.get('continuity_score') or 0:.2f}", _ts(s.get("switched_at"))] for s in data]
    _table(["From", "", "To", "Continuity", "When"], rows)


# ── Graph subcommand group ──────────────────────────────────────────────────

@cli.group("graph")
def graph():
    """Knowledge graph operations."""
    pass


@graph.command("query")
@click.argument("entity_name")
@click.option("-d", "--depth", default=2)
@click.option("--type", "rel_type", default=None, help="Filter by relationship type")
def graph_query(entity_name, depth, rel_type):
    """Print entity neighborhood."""
    # First resolve entity ID by name
    resp = _api("GET", "/api/v1/entities", params={"limit": 100})
    entities = resp.json().get("items", []) if resp.status_code == 200 else []
    entity = next((e for e in entities if e["name"].lower() == entity_name.lower()), None)
    if not entity:
        click.secho(f"Entity '{entity_name}' not found.", fg="red")
        return
    params = {"depth": depth}
    if rel_type:
        params["relationship_types"] = rel_type
    resp = _api("GET", f"/api/v1/graph/entity/{entity['id']}/neighborhood", params=params)
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    click.secho(f"🕸️  {entity_name} (depth={depth})", bold=True)
    for e in data.get("entities", []):
        marker = "●" if e["id"] == data.get("center_entity_id") else "○"
        click.echo(f"  {marker} {e['name']} ({e['type']}) tier={e.get('tier', 1)}")
    edges = data.get("edges", [])
    if edges:
        click.echo(f"\n  Edges ({len(edges)}):")
        for edge in edges:
            click.echo(f"    {_short_id(edge['source'])} —[{edge['type']}]→ {_short_id(edge['target'])}  conf={edge.get('confidence', 0):.2f}")


@graph.command("path")
@click.argument("entity_a")
@click.argument("entity_b")
def graph_path(entity_a, entity_b):
    """Find shortest path between two entities."""
    resp = _api("GET", "/api/v1/entities", params={"limit": 200})
    entities = resp.json().get("items", []) if resp.status_code == 200 else []
    a = next((e for e in entities if e["name"].lower() == entity_a.lower()), None)
    b = next((e for e in entities if e["name"].lower() == entity_b.lower()), None)
    if not a or not b:
        click.secho("One or both entities not found.", fg="red")
        return
    resp = _api("GET", "/api/v1/graph/path", params={"source": a["id"], "target": b["id"]})
    data = resp.json()
    if data.get("path") is None and "nodes" not in data:
        click.secho(f"No path found between '{entity_a}' and '{entity_b}'.", dim=True)
        return
    nodes = data.get("nodes", [])
    types = data.get("relationship_types", [])
    click.secho(f"🔗 Path ({data.get('length', len(nodes)-1)} hops):", bold=True)
    for i, nid in enumerate(nodes):
        click.echo(f"  {_short_id(nid)}", nl=False)
        if i < len(types):
            click.echo(f" —[{types[i]}]→ ", nl=False)
    click.echo()


@graph.command("hubs")
@click.option("-n", "--limit", default=10)
def graph_hubs(limit):
    """Top hub entities by degree centrality."""
    resp = _api("GET", "/api/v1/graph/hubs", params={"limit": limit})
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if not data:
        click.secho("No hub entities found.", dim=True)
        return
    rows = [[e.get("name", ""), e.get("entity_type", ""), str(e.get("tier", 1)), str(e.get("degree", 0))] for e in data]
    _table(["Name", "Type", "Tier", "Degree"], rows)


@graph.command("unlinked")
def graph_unlinked():
    """List unlinked mention suggestions."""
    resp = _api("GET", "/api/v1/graph/unlinked-mentions")
    if resp.status_code != 200:
        click.secho(f"Error: {resp.text}", fg="red")
        return
    data = resp.json()
    if not data:
        click.secho("No unlinked mentions found.", dim=True)
        return
    for item in data[:10]:
        click.echo(f"  {item['entity_name']}: {item['unlinked_count']} unlinked mentions")
        click.secho(f"    Sample: {item.get('sample', '')[:80]}", dim=True)


# ── Sun subcommand additions ────────────────────────────────────────────────

@sun.command("read")
@click.option("-s", "--section", default=None, type=click.Choice(["identity", "values", "agent_protocol", "planet_registry", "working_context", "evolution_log"]))
@click.option("--json", "as_json", is_flag=True)
def sun_read(section, as_json):
    """Read Sun sections."""
    if section:
        resp = _api("GET", f"/api/v1/sun/{section}")
    else:
        resp = _api("GET", "/api/v1/sun")
    if resp.status_code != 200:
        click.secho("No Galaxy found.", fg="yellow")
        return
    data = resp.json()
    if as_json:
        _print_json(data)
    else:
        click.secho("☀️  Sun", bold=True)
        if section:
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            for key, val in data.items():
                click.echo(f"\n  [{key}]")
                val_str = json.dumps(val, indent=2, default=str) if isinstance(val, (dict, list)) else str(val)
                for line in val_str.split("\n")[:5]:
                    click.echo(f"    {line}")


@sun.command("edit")
@click.argument("section_key", type=click.Choice(["working-context", "values", "identity", "agent_protocol"]))
def sun_edit(section_key):
    """Edit a Sun section in $EDITOR."""
    # Map CLI names to API names
    key_map = {"working-context": "working_context", "values": "values", "identity": "identity", "agent_protocol": "agent_protocol"}
    api_key = key_map.get(section_key, section_key)
    resp = _api("GET", f"/api/v1/sun/{api_key}")
    if resp.status_code != 200:
        click.secho("Section not found.", fg="red")
        return
    data = resp.json()
    content = data.get("content", data)
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(content, f, indent=2, default=str)
        f.flush()
        click.edit(filename=f.name)
        with open(f.name) as rf:
            try:
                new_content = json.load(rf)
            except json.JSONDecodeError:
                click.secho("Invalid JSON. Aborting.", fg="red")
                return
    resp = _api("PUT", f"/api/v1/sun/{api_key}", json={"content": new_content})
    if resp.status_code == 200:
        click.secho(f"☀️  Updated '{api_key}'", fg="green")
    else:
        click.secho(f"Error: {resp.text}", fg="red")


def _wait_and_launch_tui():
    """Wait for the API to become reachable, then launch the Textual TUI."""
    import time
    click.echo("Waiting for API...", nl=False)
    for _ in range(15):
        try:
            r = httpx.get(f"{API_URL}/health", timeout=2)
            if r.status_code == 200:
                click.secho(" ready!", fg="green")
                from app.tui import run_tui
                run_tui()
                return
        except (httpx.ConnectError, httpx.ReadError):
            pass
        click.echo(".", nl=False)
        time.sleep(1)
    click.secho("\n✗ API did not become ready. Check `orion logs`.", fg="red")


if __name__ == "__main__":
    cli()


@cli.command()
def tui():
    """Open the full-screen terminal UI (assumes services are running)."""
    try:
        httpx.get(f"{API_URL}/health", timeout=3)
    except httpx.ConnectError:
        click.secho("✗ Cannot connect to Orion API at " + API_URL, fg="red")
        click.echo("  Run 'orion start' to start the services.")
        click.echo("  Tip: If services are already running, check with 'docker compose ps'")
        return
    from app.tui import run_tui
    run_tui()
