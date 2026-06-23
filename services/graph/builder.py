"""Syncs relational data into Neo4j knowledge graph."""
from neo4j import AsyncGraphDatabase
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class GraphBuilder:
    def __init__(self):
        settings = get_settings()
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def sync(self):
        await self._sync_hcps()
        await self._sync_publications()
        await self._sync_trials()
        await self._sync_authorships()
        await self._sync_investigatorships()
        log.info("Graph sync complete")

    async def _sync_hcps(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("SELECT id, full_name, specialty, state, kol_tier FROM hcps")
            )).fetchall()

        async with self.driver.session() as gs:
            for row in rows:
                await gs.run(
                    """
                    MERGE (h:HCP {id: $id})
                    SET h.name = $name, h.specialty = $specialty,
                        h.state = $state, h.kol_tier = $kol_tier
                    """,
                    id=str(row[0]), name=row[1], specialty=row[2],
                    state=row[3], kol_tier=row[4],
                )
        log.info("Synced %d HCPs to graph", len(rows))

    async def _sync_publications(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("SELECT id, pubmed_id, title, journal, disease_areas FROM publications")
            )).fetchall()

        async with self.driver.session() as gs:
            for row in rows:
                await gs.run(
                    """
                    MERGE (p:Publication {id: $id})
                    SET p.pubmed_id = $pubmed_id, p.title = $title,
                        p.journal = $journal, p.disease_areas = $disease_areas
                    """,
                    id=str(row[0]), pubmed_id=row[1], title=row[2],
                    journal=row[3], disease_areas=row[4] or [],
                )
        log.info("Synced %d publications to graph", len(rows))

    async def _sync_trials(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("SELECT id, nct_id, title, phase, status, sponsor FROM clinical_trials")
            )).fetchall()

        async with self.driver.session() as gs:
            for row in rows:
                await gs.run(
                    """
                    MERGE (t:Trial {id: $id})
                    SET t.nct_id = $nct_id, t.title = $title,
                        t.phase = $phase, t.status = $status, t.sponsor = $sponsor
                    """,
                    id=str(row[0]), nct_id=row[1], title=row[2],
                    phase=row[3], status=row[4], sponsor=row[5],
                )
        log.info("Synced %d trials to graph", len(rows))

    async def _sync_authorships(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("SELECT hcp_id, publication_id, is_corresponding FROM publication_authors")
            )).fetchall()

        async with self.driver.session() as gs:
            for row in rows:
                await gs.run(
                    """
                    MATCH (h:HCP {id: $hcp_id}), (p:Publication {id: $pub_id})
                    MERGE (h)-[r:AUTHORED]->(p)
                    SET r.is_corresponding = $is_corresponding
                    """,
                    hcp_id=str(row[0]), pub_id=str(row[1]), is_corresponding=row[2],
                )

    async def _sync_investigatorships(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("SELECT hcp_id, trial_id, role FROM trial_investigators")
            )).fetchall()

        async with self.driver.session() as gs:
            for row in rows:
                await gs.run(
                    """
                    MATCH (h:HCP {id: $hcp_id}), (t:Trial {id: $trial_id})
                    MERGE (h)-[r:INVESTIGATES]->(t)
                    SET r.role = $role
                    """,
                    hcp_id=str(row[0]), trial_id=str(row[1]), role=row[2],
                )
