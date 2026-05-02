import logging
import os
import re
import uuid
from pathlib import Path
from sqlalchemy import select, insert
from app.database import async_session
from app.models import Biome
from app.models.planet import Planet
from app.services import stardust_service, nebula_service
from app.extraction.signal_detector import infer_region_from_content

logger = logging.getLogger(__name__)

# ── Format detection ────────────────────────────────────────────────────────

_GBRAIN_KEYS = {"cognitive_mode", "confidence", "gravity", "reasoning"}


def detect_import_format(path: str) -> str:
    """Auto-detect import format from folder structure.

    Priority: obsidian > claude > gbrain > plain
    """
    p = Path(path)
    if (p / ".obsidian").is_dir():
        return "obsidian"
    if (p / "CLAUDE.md").is_file():
        return "claude"
    # Check first few .md files for GBrain frontmatter keys
    for md in list(p.glob("*.md"))[:5]:
        try:
            meta, _ = parse_frontmatter(md.read_text(encoding="utf-8", errors="ignore"))
            if meta and _GBRAIN_KEYS & set(meta.keys()):
                return "gbrain"
        except Exception:
            pass
    return "plain"


# ── Obsidian wikilink extraction ────────────────────────────────────────────

_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?\|?[^\]]*\]\]")


def extract_wikilinks(text: str) -> list[str]:
    """Extract unique wikilink targets from markdown, ignoring code blocks."""
    cleaned = _CODE_BLOCK_RE.sub("", text)
    links = _WIKILINK_RE.findall(cleaned)
    seen = set()
    result = []
    for link in links:
        link = link.strip()
        if link and link not in seen:
            seen.add(link)
            result.append(link)
    return result


# ── CLAUDE.md parsing ───────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^#+\s+(.+)$", re.MULTILINE)


def parse_claude_md(content: str) -> list[dict]:
    """Parse CLAUDE.md into high-confidence contextual stardust records.

    Each list item or paragraph becomes a record with GALAXY gravity.
    Headings become context tags.
    """
    if not content.strip():
        return []

    records = []
    current_section = ""

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            current_section = heading_match.group(1).strip()
            continue
        # List items
        if line.startswith("- ") or line.startswith("* "):
            item = line.lstrip("-* ").strip()
            if item:
                records.append({
                    "content": item,
                    "gravity": "GALAXY",
                    "confidence": 0.95,
                    "region": "contextual",
                    "tags": [current_section] if current_section else [],
                })
        # Non-empty non-heading lines (paragraphs)
        elif not line.startswith("#"):
            records.append({
                "content": line,
                "gravity": "GALAXY",
                "confidence": 0.95,
                "region": "contextual",
                "tags": [current_section] if current_section else [],
            })

    return records


# ── GBrain frontmatter mapping ─────────────────────────────────────────────

def parse_gbrain_frontmatter(meta: dict, body: str) -> dict:
    """Map GBrain-specific frontmatter fields to stardust metadata."""
    confidence = meta.get("confidence", 0.5)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except ValueError:
            confidence = 0.5

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags] if tags else []

    return {
        "region": meta.get("cognitive_mode", "contextual"),
        "confidence": confidence,
        "gravity": meta.get("gravity", "BIOME"),
        "tags": tags,
        "reasoning": meta.get("reasoning"),
    }


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 3:].strip()
    meta = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            if key.strip() == "tags":
                # Handle YAML list
                if val.startswith("["):
                    meta["tags"] = [t.strip().strip('"').strip("'") for t in val.strip("[]").split(",") if t.strip()]
                else:
                    meta["tags"] = [val] if val else []
            else:
                meta[key.strip()] = val
    return meta, body


def infer_biome_from_path(file_path: str, root_path: str) -> str:
    """Infer biome name from folder structure."""
    rel = os.path.relpath(file_path, root_path)
    parts = Path(rel).parts
    if len(parts) > 1:
        # Use first subfolder as biome name
        return parts[0].replace("_", " ").replace("-", " ").title()
    return "General"


def _clean_folder_name(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def infer_hierarchy_from_path(file_path: str, root_path: str) -> tuple[str | None, str]:
    """Infer planet and biome from Obsidian folder depth.

    Returns (planet_name | None, biome_name).
    - Root files: (None, "General")
    - 1 level deep: (first_folder, "General")  — top-level folder becomes a planet
    - 2+ levels deep: (first_folder, second_folder)
    """
    rel = os.path.relpath(file_path, root_path)
    parts = Path(rel).parts
    if len(parts) <= 1:
        return None, "General"
    # first folder = planet, second folder (if any) = biome
    planet = _clean_folder_name(parts[0])
    biome = _clean_folder_name(parts[1]) if len(parts) > 2 else "General"
    return planet, biome


def chunk_by_paragraph(text: str, max_tokens: int = 500) -> list[str]:
    """Split text into chunks at paragraph boundaries, ~max_tokens each."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > max_tokens * 4:  # ~4 chars per token
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_tokens * 4]] if text.strip() else []


async def _get_or_create_planet(galaxy_id: str, planet_name: str) -> str:
    """Return planet_id, creating the planet if it doesn't exist."""
    async with async_session() as db:
        planet = (await db.execute(select(Planet).where(Planet.galaxy_id == galaxy_id, Planet.name == planet_name))).scalar_one_or_none()
        if planet:
            return planet.id
        planet_id = str(uuid.uuid4())
        await db.execute(insert(Planet).values(id=planet_id, galaxy_id=galaxy_id, name=planet_name, color="#6D28D9"))
        await db.commit()
        return planet_id


async def _get_or_create_biome(planet_id: str, galaxy_id: str, biome_name: str) -> str:
    async with async_session() as db:
        biome = (await db.execute(select(Biome).where(Biome.planet_id == planet_id, Biome.name == biome_name))).scalar_one_or_none()
        if biome:
            return biome.id
        biome_id = str(uuid.uuid4())
        await db.execute(insert(Biome).values(id=biome_id, planet_id=planet_id, galaxy_id=galaxy_id, name=biome_name))
        await db.commit()
        return biome_id


async def import_markdown_folder(path: str, planet_id: str, galaxy_id: str, max_files: int = 500, max_depth: int = 5):
    """Import a folder of markdown files into the Galaxy, with format-aware behavior."""
    logger.info(f"Starting markdown import from {path}")
    fmt = detect_import_format(path)
    logger.info(f"Detected format: {fmt}")

    root = Path(path)

    # Resolve the default planet (passed in by caller)
    async with async_session() as db:
        from app.models import Planet
        planet = (await db.execute(select(Planet).where(Planet.id == planet_id))).scalar_one_or_none()
        if not planet:
            logger.error(f"Planet {planet_id} not found")
            return
        default_planet_name = planet.name

    # ── CLAUDE.md format: parse CLAUDE.md as high-confidence GALAXY stardust ──
    if fmt == "claude":
        claude_file = root / "CLAUDE.md"
        if claude_file.is_file():
            records = parse_claude_md(claude_file.read_text(encoding="utf-8", errors="ignore"))
            biome_id = await _get_or_create_biome(planet_id, galaxy_id, "Context")
            for rec in records:
                try:
                    await stardust_service.write_stardust(
                        content=rec["content"], galaxy_id=galaxy_id,
                        planet_name=default_planet_name, biome_name="Context",
                        region=rec.get("region", "contextual"),
                        gravity=rec["gravity"], confidence=rec["confidence"],
                        source_agent="importer",
                        context_tags=rec.get("tags", []),
                    )
                except Exception as e:
                    logger.warning(f"Failed to import CLAUDE.md record: {e}")
        # Also import remaining .md files as plain
        fmt = "plain"

    # Collect files
    files = [
        str(p) for p in root.rglob("*.md")
        if len(p.relative_to(root).parts) <= max_depth
        and not any(part.startswith(".") for part in p.relative_to(root).parts)
    ][:max_files]
    if not files:
        logger.warning(f"No .md files found in {path}")
        return

    imported = 0
    wikilink_map: dict[str, list[str]] = {}  # filename_stem -> [target_stems]

    for md_file in files:
        try:
            with open(md_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            frontmatter, body = parse_frontmatter(content)
            if not body.strip():
                continue

            # ── Per-format metadata resolution ──
            if fmt == "obsidian":
                cur_planet_name, biome_name = infer_hierarchy_from_path(md_file, path)
                # Ensure the folder-inferred planet and biome exist so routing can use them
                if cur_planet_name:
                    planet_id = await _get_or_create_planet(galaxy_id, cur_planet_name)
                    await _get_or_create_biome(planet_id, galaxy_id, biome_name)
                region = infer_region_from_content(body)
                gravity = "BIOME"
                confidence = 0.5
                tags = frontmatter.get("tags", [])
                # Collect wikilinks for relationship creation
                links = extract_wikilinks(content)
                if links:
                    stem = Path(md_file).stem
                    wikilink_map[stem] = links

            elif fmt == "gbrain":
                gbrain_meta = parse_gbrain_frontmatter(frontmatter, body)
                biome_name = infer_biome_from_path(md_file, path)
                cur_planet_name = None  # let routing decide
                region = gbrain_meta["region"]
                gravity = gbrain_meta["gravity"]
                confidence = gbrain_meta["confidence"]
                tags = gbrain_meta["tags"]

            else:  # plain (or claude fallthrough)
                biome_name = infer_biome_from_path(md_file, path)
                cur_planet_name = None  # let routing decide
                region = infer_region_from_content(body)
                gravity = "BIOME"
                confidence = 0.5
                tags = frontmatter.get("tags", [])

            # ── Chunk and write ──
            if isinstance(tags, str):
                tags = [tags]
            chunks = chunk_by_paragraph(body)
            for chunk in chunks:
                if len(chunk.strip()) < 10:
                    continue
                try:
                    await stardust_service.write_stardust(
                        content=chunk, galaxy_id=galaxy_id,
                        planet_name=cur_planet_name, biome_name=biome_name,
                        region=region, gravity=gravity, confidence=confidence,
                        source_agent="importer", context_tags=tags,
                        filename=str(md_file),
                    )
                    imported += 1
                except Exception as e:
                    logger.warning(f"Failed to import chunk from {md_file}: {e}")

            await nebula_service.log_event(galaxy_id=galaxy_id, action_type="IMPORT", initiated_by="importer", record_id=os.path.basename(md_file))
        except Exception as e:
            logger.error(f"Failed to import {md_file}: {e}")

    # ── Obsidian: create entity relationships from wikilinks ──
    if wikilink_map:
        logger.info(f"Creating entity relationships from {len(wikilink_map)} files with wikilinks")
        from app.models import Entity
        for source_stem, targets in wikilink_map.items():
            for target_stem in targets:
                try:
                    async with async_session() as db:
                        # Get or create source entity
                        src = (await db.execute(select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name == source_stem))).scalar_one_or_none()
                        if not src:
                            src = Entity(id=str(uuid.uuid4()), galaxy_id=galaxy_id, name=source_stem, entity_type="concept")
                            db.add(src)
                        # Get or create target entity
                        tgt = (await db.execute(select(Entity).where(Entity.galaxy_id == galaxy_id, Entity.name == target_stem))).scalar_one_or_none()
                        if not tgt:
                            tgt = Entity(id=str(uuid.uuid4()), galaxy_id=galaxy_id, name=target_stem, entity_type="concept")
                            db.add(tgt)
                        await db.commit()
                except Exception as e:
                    logger.warning(f"Failed to create entity for wikilink {source_stem} -> {target_stem}: {e}")

    logger.info(f"Import complete ({fmt}): {imported} stardust records from {len(files)} files")
