"""Tests for H2.8 Galaxy Merge — proposal lifecycle, Sun negotiation, entity reconciliation, bridges, full merge."""
import json
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone
from app.models import Galaxy, SunSection, Planet, Biome, Entity, Stardust, GravityBridge
from app.models.merge import MergeProposal, EntityMergeMapping
from app.models.user import User
from app.services.merge_service import MergeService


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def two_galaxies(db):
    """Create two Galaxies with Planets, Entities, Sun sections, and owner Users."""
    # Galaxy A (source)
    ga = Galaxy(id=str(uuid4()), name="Galaxy Alpha", strength_score=50.0, total_nodes=10)
    db.add(ga)
    pa = Planet(id=str(uuid4()), galaxy_id=ga.id, name="Engineering", stardust_count=5)
    db.add(pa)
    ba = Biome(id=str(uuid4()), planet_id=pa.id, galaxy_id=ga.id, name="Backend", lifecycle_state="ACTIVE")
    db.add(ba)

    # Galaxy B (target)
    gb = Galaxy(id=str(uuid4()), name="Galaxy Beta", strength_score=60.0, total_nodes=15)
    db.add(gb)
    pb = Planet(id=str(uuid4()), galaxy_id=gb.id, name="Research", stardust_count=8)
    db.add(pb)
    bb = Biome(id=str(uuid4()), planet_id=pb.id, galaxy_id=gb.id, name="ML", lifecycle_state="ACTIVE")
    db.add(bb)

    # Users
    owner_a = User(id=str(uuid4()), email="a@test.com", name="Owner A", password_hash="x", role="owner", galaxy_id=ga.id)
    owner_b = User(id=str(uuid4()), email="b@test.com", name="Owner B", password_hash="x", role="owner", galaxy_id=gb.id)
    db.add_all([owner_a, owner_b])

    # Sun sections for both galaxies
    for gid, vals in [(ga.id, {"name": "Alpha", "galaxy_purpose": "Engineering knowledge"}),
                      (gb.id, {"name": "Beta", "galaxy_purpose": "Research knowledge"})]:
        for key, content in [
            ("identity", vals),
            ("values", {"principles": ["be clear", "cite sources"] if gid == ga.id else ["be thorough", "cite sources"]}),
            ("agent_protocol", {"write_rules": ["rule_a"] if gid == ga.id else ["rule_b"], "read_rules": []}),
            ("planet_registry", {"planets": []}),
            ("working_context", {"current_focus": "", "hot_biomes": [], "recent_decisions": []}),
            ("evolution_log", {"entries": []}),
        ]:
            db.add(SunSection(id=str(uuid4()), galaxy_id=gid, section_key=key, content=json.dumps(content)))

    # Shared entity (exists in both galaxies — should be reconciled)
    e_a = Entity(id=str(uuid4()), galaxy_id=ga.id, planet_id=pa.id, name="FastAPI", entity_type="technology", tier=2, mention_count=5)
    e_b = Entity(id=str(uuid4()), galaxy_id=gb.id, planet_id=pb.id, name="FastAPI", entity_type="technology", tier=3, mention_count=10)
    # Unique entities
    e_a2 = Entity(id=str(uuid4()), galaxy_id=ga.id, planet_id=pa.id, name="Docker", entity_type="technology", tier=1, mention_count=3)
    e_b2 = Entity(id=str(uuid4()), galaxy_id=gb.id, planet_id=pb.id, name="PyTorch", entity_type="technology", tier=2, mention_count=7)
    db.add_all([e_a, e_b, e_a2, e_b2])

    # Stardust in source galaxy
    sd = Stardust(
        id=str(uuid4()), biome_id=ba.id, planet_id=pa.id, galaxy_id=ga.id,
        content="FastAPI is great for building APIs",
    )
    db.add(sd)

    await db.commit()
    return {
        "galaxy_a": ga, "galaxy_b": gb,
        "planet_a": pa, "planet_b": pb,
        "biome_a": ba, "biome_b": bb,
        "owner_a": owner_a, "owner_b": owner_b,
        "entity_a_fastapi": e_a, "entity_b_fastapi": e_b,
        "entity_a_docker": e_a2, "entity_b_pytorch": e_b2,
        "stardust_a": sd,
    }


# ── Merge Service Unit Tests ───────────────────────────────────────────────

class TestMergeProposalLifecycle:
    @pytest.mark.asyncio
    async def test_propose_merge(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        assert proposal.status == "proposed"
        assert proposal.source_galaxy_id == g["galaxy_a"].id
        assert proposal.target_galaxy_id == g["galaxy_b"].id

    @pytest.mark.asyncio
    async def test_cannot_merge_self(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        with pytest.raises(ValueError, match="Cannot merge a Galaxy with itself"):
            await svc.propose_merge(g["galaxy_a"].id, g["galaxy_a"].id, g["owner_a"].id, db)

    @pytest.mark.asyncio
    async def test_duplicate_proposal_rejected(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        with pytest.raises(ValueError, match="active merge proposal already exists"):
            await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)

    @pytest.mark.asyncio
    async def test_accept_merge(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        accepted = await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        assert accepted.status == "accepted"
        assert accepted.accepted_by == g["owner_b"].id

    @pytest.mark.asyncio
    async def test_reject_merge(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        rejected = await svc.reject_merge(proposal.id, g["owner_b"].id, "Not interested", db)
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Not interested"

    @pytest.mark.asyncio
    async def test_cannot_accept_rejected(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.reject_merge(proposal.id, g["owner_b"].id, "No", db)
        with pytest.raises(ValueError, match="not 'proposed'"):
            await svc.accept_merge(proposal.id, g["owner_b"].id, db)


class TestSunNegotiation:
    @pytest.mark.asyncio
    async def test_negotiate_sun_merges_sections(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        merged = await svc.negotiate_sun(proposal.id, db)

        # Identity: target wins, source purpose appended
        assert "Beta" in merged["identity"]["name"]
        assert "Engineering knowledge" in merged["identity"]["galaxy_purpose"]

        # Values: principles merged and deduplicated
        principles = merged["values"]["principles"]
        assert "be clear" in principles
        assert "be thorough" in principles
        assert "cite sources" in principles
        assert len(principles) == 3  # deduplicated

        # Agent protocol: rules merged, target first
        assert merged["agent_protocol"]["write_rules"][0] == "rule_b"
        assert "rule_a" in merged["agent_protocol"]["write_rules"]

    @pytest.mark.asyncio
    async def test_preview_merged_sun(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        preview = await svc.preview_merged_sun(proposal.id, db)
        assert "identity" in preview
        assert "values" in preview

    @pytest.mark.asyncio
    async def test_negotiate_requires_accepted(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        with pytest.raises(ValueError, match="must be 'accepted'"):
            await svc.negotiate_sun(proposal.id, db)


class TestEntityReconciliation:
    @pytest.mark.asyncio
    async def test_reconcile_finds_duplicates(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        mappings = await svc.reconcile_entities(proposal.id, db)

        # Should find FastAPI as a duplicate (same name + type in both galaxies)
        assert len(mappings) == 1
        assert mappings[0]["source"]["name"] == "FastAPI"
        assert mappings[0]["target"]["name"] == "FastAPI"
        assert mappings[0]["match_type"] == "same_type_and_name"

    @pytest.mark.asyncio
    async def test_get_entity_mappings(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        await svc.reconcile_entities(proposal.id, db)
        mappings = await svc.get_entity_mappings(proposal.id, db)
        assert len(mappings) == 1
        assert mappings[0]["merged"] is False


class TestGravityBridgeCreation:
    @pytest.mark.asyncio
    async def test_create_bridges(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        await svc.reconcile_entities(proposal.id, db)
        bridges = await svc.create_bridges(proposal.id, db)

        # 1 source planet × 1 target planet = 1 bridge
        assert len(bridges) == 1
        assert bridges[0]["bridge_type"] == "MERGE"
        assert bridges[0]["source_planet"] == "Engineering"
        assert bridges[0]["target_planet"] == "Research"


class TestFullMergeExecution:
    @pytest.mark.asyncio
    async def test_execute_merge_full_flow(self, db, two_galaxies):
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        await svc.reconcile_entities(proposal.id, db)
        await svc.create_bridges(proposal.id, db)
        result = await svc.execute_merge(proposal.id, db)

        assert result["status"] == "complete"
        assert result["entities_merged"] == 1
        assert result["bridges_created"] == 1
        assert result["sun_negotiated"] is True

        # Verify source data migrated to target galaxy
        from sqlalchemy import select, func
        target_gid = g["galaxy_b"].id

        # Planets from source now in target
        planet_count = (await db.execute(
            select(func.count()).select_from(Planet).where(Planet.galaxy_id == target_gid)
        )).scalar()
        assert planet_count == 2  # Research + Engineering

        # Stardust migrated
        sd_count = (await db.execute(
            select(func.count()).select_from(Stardust).where(Stardust.galaxy_id == target_gid)
        )).scalar()
        assert sd_count == 1

        # Merged entity has combined mention count
        await db.refresh(g["entity_b_fastapi"])
        assert g["entity_b_fastapi"].mention_count == 15  # 5 + 10
        assert g["entity_b_fastapi"].tier == 3  # max(2, 3)

        # Users migrated
        await db.refresh(g["owner_a"])
        assert g["owner_a"].galaxy_id == target_gid

        # Target galaxy total_nodes updated
        await db.refresh(g["galaxy_b"])
        assert g["galaxy_b"].total_nodes == 25  # 10 + 15

    @pytest.mark.asyncio
    async def test_execute_merge_stepwise(self, db, two_galaxies):
        """execute_merge works when all phases are run individually first."""
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        await svc.reconcile_entities(proposal.id, db)
        await svc.create_bridges(proposal.id, db)
        result = await svc.execute_merge(proposal.id, db)
        assert result["status"] == "complete"
        assert result["sun_negotiated"] is True

    @pytest.mark.asyncio
    async def test_merge_clears_cross_galaxy_bridge_refs(self, db, two_galaxies):
        """After merge, target_galaxy_id on bridges should be cleared."""
        svc = MergeService()
        g = two_galaxies
        proposal = await svc.propose_merge(g["galaxy_a"].id, g["galaxy_b"].id, g["owner_a"].id, db)
        await svc.accept_merge(proposal.id, g["owner_b"].id, db)
        await svc.negotiate_sun(proposal.id, db)
        await svc.reconcile_entities(proposal.id, db)
        await svc.create_bridges(proposal.id, db)
        await svc.execute_merge(proposal.id, db)

        from sqlalchemy import select
        bridges = (await db.execute(
            select(GravityBridge).where(GravityBridge.galaxy_id == g["galaxy_b"].id)
        )).scalars().all()
        for b in bridges:
            assert b.target_galaxy_id is None  # cleared after merge


# ── API Endpoint Tests ──────────────────────────────────────────────────────

class TestMergeAPI:
    async def _setup_two_galaxies(self, client):
        """Create two galaxies via onboarding, return their IDs."""
        # First galaxy via onboarding
        resp = await client.post("/api/v1/onboarding/start", json={
            "role": "Developer", "first_biome_name": "Project A",
        })
        assert resp.status_code == 201
        data_a = resp.json()
        galaxy_a_id = data_a["galaxy_id"]

        # Second galaxy — create directly since onboarding blocks second galaxy
        from app.database import get_db
        from app.main import app
        override = app.dependency_overrides.get(get_db)
        if override:
            async for session in override():
                g2 = Galaxy(id=str(uuid4()), name="Galaxy Two", strength_score=0, total_nodes=0)
                session.add(g2)
                p2 = Planet(id=str(uuid4()), galaxy_id=g2.id, name="Research", stardust_count=0)
                session.add(p2)
                await session.commit()
                return galaxy_a_id, g2.id
        return galaxy_a_id, None

    @pytest.mark.asyncio
    async def test_propose_merge_endpoint(self, client):
        ga_id, gb_id = await self._setup_two_galaxies(client)
        if not gb_id:
            pytest.skip("Could not create second galaxy")
        resp = await client.post("/api/v1/galaxy/merge/propose", json={"target_galaxy_id": gb_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "proposed"
        assert "proposal_id" in data

    @pytest.mark.asyncio
    async def test_get_proposal_endpoint(self, client):
        ga_id, gb_id = await self._setup_two_galaxies(client)
        if not gb_id:
            pytest.skip("Could not create second galaxy")
        resp = await client.post("/api/v1/galaxy/merge/propose", json={"target_galaxy_id": gb_id})
        pid = resp.json()["proposal_id"]
        resp = await client.get(f"/api/v1/galaxy/merge/{pid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "proposed"

    @pytest.mark.asyncio
    async def test_reject_merge_endpoint(self, client):
        ga_id, gb_id = await self._setup_two_galaxies(client)
        if not gb_id:
            pytest.skip("Could not create second galaxy")
        resp = await client.post("/api/v1/galaxy/merge/propose", json={"target_galaxy_id": gb_id})
        pid = resp.json()["proposal_id"]
        resp = await client.post(f"/api/v1/galaxy/merge/{pid}/reject", json={"reason": "Not now"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_proposal_not_found(self, client):
        resp = await client.get("/api/v1/galaxy/merge/nonexistent")
        assert resp.status_code == 404
