"""Detects buying signals and trigger events for HCPs."""
from shared.db import get_session_factory
from sqlalchemy import text
import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger(__name__)

TRIGGER_TYPES = [
    "new_publication",
    "trial_enrollment_opened",
    "conference_presentation",
    "institution_change",
    "grant_awarded",
    "advisory_board_appointment",
    "competitor_drug_approved",
    "guideline_update",
]


class TriggerDetector:
    async def run(self):
        await self._detect_new_publications()
        await self._detect_new_trial_activity()
        log.info("Trigger detection complete")

    async def _detect_new_publications(self):
        """Fire a trigger for HCPs who published in the last 7 days."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("""
                    SELECT DISTINCT pa.hcp_id, p.id as pub_id, p.title
                    FROM publication_authors pa
                    JOIN publications p ON pa.publication_id = p.id
                    WHERE p.created_at >= NOW() - INTERVAL '7 days'
                    AND NOT EXISTS (
                        SELECT 1 FROM trigger_events te
                        WHERE te.hcp_id = pa.hcp_id
                        AND te.event_type = 'new_publication'
                        AND te.event_data->>'pub_id' = p.id::text
                    )
                """)
            )).fetchall()

            for hcp_id, pub_id, title in rows:
                await session.execute(
                    text("""
                        INSERT INTO trigger_events (id, hcp_id, event_type, event_data, source, occurred_at)
                        VALUES (:id, :hcp_id, 'new_publication', :data, 'pubmed', :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "hcp_id": hcp_id,
                        "data": f'{{"pub_id": "{pub_id}", "title": "{title}"}}',
                        "now": datetime.now(timezone.utc),
                    },
                )
            await session.commit()
        log.info("Created %d new publication triggers", len(rows))

    async def _detect_new_trial_activity(self):
        """Fire triggers for newly opened trial sites."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(
                text("""
                    SELECT DISTINCT ti.hcp_id, ct.id, ct.nct_id
                    FROM trial_investigators ti
                    JOIN clinical_trials ct ON ti.trial_id = ct.id
                    WHERE ct.status = 'RECRUITING'
                    AND NOT EXISTS (
                        SELECT 1 FROM trigger_events te
                        WHERE te.hcp_id = ti.hcp_id
                        AND te.event_type = 'trial_enrollment_opened'
                        AND te.event_data->>'nct_id' = ct.nct_id
                    )
                """)
            )).fetchall()

            for hcp_id, trial_id, nct_id in rows:
                await session.execute(
                    text("""
                        INSERT INTO trigger_events (id, hcp_id, event_type, event_data, source, occurred_at)
                        VALUES (:id, :hcp_id, 'trial_enrollment_opened', :data, 'clinicaltrials', :now)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "hcp_id": hcp_id,
                        "data": f'{{"trial_id": "{trial_id}", "nct_id": "{nct_id}"}}',
                        "now": datetime.now(timezone.utc),
                    },
                )
            await session.commit()
