"""Institution referral pattern analyzer — maps HCP referral networks."""
from shared.db import get_session_factory
from neo4j import AsyncGraphDatabase
from shared.config import get_settings
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)


class ReferralAnalyzer:
    """
    Uses co-authorship and co-trial-participation as proxies for referral relationships.
    Builds a Neo4j subgraph of likely referral patterns.
    """

    def __init__(self):
        settings = get_settings()
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )

    async def build_referral_graph(self):
        await self._build_coauthorship_edges()
        await self._build_co_investigator_edges()
        log.info("Referral graph built")

    async def _build_coauthorship_edges(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT a.hcp_id, b.hcp_id, COUNT(*) AS shared_pubs
                FROM publication_authors a
                JOIN publication_authors b ON a.publication_id = b.publication_id AND a.hcp_id < b.hcp_id
                GROUP BY a.hcp_id, b.hcp_id
                HAVING COUNT(*) >= 2
            """))).fetchall()

        async with self.driver.session() as gs:
            for a_id, b_id, shared in rows:
                await gs.run("""
                    MATCH (a:HCP {id: $a}), (b:HCP {id: $b})
                    MERGE (a)-[r:CO_AUTHOR]->(b)
                    SET r.shared_publications = $shared
                """, a=str(a_id), b=str(b_id), shared=shared)
        log.info("Built %d co-authorship edges", len(rows))

    async def _build_co_investigator_edges(self):
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT a.hcp_id, b.hcp_id, COUNT(*) AS shared_trials
                FROM trial_investigators a
                JOIN trial_investigators b ON a.trial_id = b.trial_id AND a.hcp_id < b.hcp_id
                GROUP BY a.hcp_id, b.hcp_id
                HAVING COUNT(*) >= 1
            """))).fetchall()

        async with self.driver.session() as gs:
            for a_id, b_id, shared in rows:
                await gs.run("""
                    MATCH (a:HCP {id: $a}), (b:HCP {id: $b})
                    MERGE (a)-[r:CO_INVESTIGATOR]->(b)
                    SET r.shared_trials = $shared
                """, a=str(a_id), b=str(b_id), shared=shared)
        log.info("Built %d co-investigator edges", len(rows))

    async def get_referral_network(self, hcp_id: str, depth: int = 2) -> dict:
        async with self.driver.session() as gs:
            result = await gs.run("""
                MATCH path = (h:HCP {id: $id})-[:CO_AUTHOR|CO_INVESTIGATOR*1..$depth]-(connected:HCP)
                RETURN connected.id AS id, connected.name AS name,
                       connected.specialty AS specialty, length(path) AS hops
                ORDER BY hops
                LIMIT 50
            """, id=hcp_id, depth=depth)
            nodes = [{"id": r["id"], "name": r["name"], "specialty": r["specialty"], "hops": r["hops"]}
                     async for r in result]
        return {"hcp_id": hcp_id, "network": nodes}
