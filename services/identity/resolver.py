"""HCP identity resolution using name + NPI + institution fuzzy matching."""
from thefuzz import fuzz
from shared.db import get_session_factory
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

MATCH_THRESHOLD = 88  # fuzzy score threshold for deduplication


class HCPResolver:
    async def run(self):
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(text("SELECT id, full_name, npi, email FROM hcps ORDER BY created_at"))
            hcps = result.fetchall()

        log.info("Resolving identities for %d HCPs", len(hcps))
        clusters = self._cluster(hcps)
        await self._merge_clusters(clusters)

    def _cluster(self, hcps: list) -> list[list]:
        """Group HCPs that likely represent the same person."""
        used = set()
        clusters = []
        for i, a in enumerate(hcps):
            if a[0] in used:
                continue
            cluster = [a]
            used.add(a[0])
            for j, b in enumerate(hcps):
                if b[0] in used or i == j:
                    continue
                # NPI exact match
                if a[2] and b[2] and a[2] == b[2]:
                    cluster.append(b)
                    used.add(b[0])
                    continue
                # Email exact match
                if a[3] and b[3] and a[3].lower() == b[3].lower():
                    cluster.append(b)
                    used.add(b[0])
                    continue
                # Fuzzy name match
                if fuzz.token_sort_ratio(a[1], b[1]) >= MATCH_THRESHOLD:
                    cluster.append(b)
                    used.add(b[0])
            if len(cluster) > 1:
                clusters.append(cluster)
        return clusters

    async def _merge_clusters(self, clusters: list[list]):
        factory = get_session_factory()
        async with factory() as session:
            for cluster in clusters:
                primary = cluster[0]  # keep earliest record as canonical
                for duplicate in cluster[1:]:
                    log.info("Merging %s into %s", duplicate[0], primary[0])
                    # Reassign foreign keys to primary, then delete duplicate
                    for fk_table, fk_col in [
                        ("publication_authors", "hcp_id"),
                        ("trial_investigators", "hcp_id"),
                        ("trigger_events", "hcp_id"),
                        ("outreach_messages", "hcp_id"),
                        ("relationship_memory", "hcp_id"),
                    ]:
                        await session.execute(
                            text(f"UPDATE {fk_table} SET {fk_col} = :primary WHERE {fk_col} = :dup"),
                            {"primary": primary[0], "dup": duplicate[0]},
                        )
                    await session.execute(
                        text("DELETE FROM hcps WHERE id = :dup"),
                        {"dup": duplicate[0]},
                    )
            await session.commit()
