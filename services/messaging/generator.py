"""Evidence-grounded outreach message generator using Claude."""
import anthropic
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging
from uuid import UUID

log = logging.getLogger(__name__)

MESSAGE_PROMPT = """
You are an oncology commercial intelligence assistant generating evidence-grounded outreach.

HCP Context:
- Name: {name}
- Specialty: {specialty}
- Institution: {institution}
- Recent Publications: {publications}
- Active Trials: {trials}
- Trigger Events: {triggers}
- Relationship Notes: {notes}

Channel: {channel}
Additional context from rep: {context_notes}

Instructions:
- Generate a {channel} message that is specific, evidence-grounded, and relevant.
- Every claim must reference the HCP's actual publications, trials, or confirmed activity above.
- Do NOT fabricate facts or references.
- Keep LinkedIn messages under 300 characters for connection requests, or under 1000 for InMail.
- Email subject lines should be concise and specific.
- End with a clear, low-pressure call to action.

Return JSON with keys: subject (null if not email), body, evidence_citations (list of {{type, title, id}}).
"""


class MessageGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def generate(self, hcp_id: UUID, channel: str, context_notes: str) -> dict | None:
        context = await self._build_context(hcp_id)
        if not context:
            return None

        prompt = MESSAGE_PROMPT.format(
            channel=channel,
            context_notes=context_notes,
            **context,
        )
        import json
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text)

        await self._save(hcp_id, channel, data)
        return {
            "channel": channel,
            "subject": data.get("subject"),
            "body": data["body"],
            "evidence_citations": data.get("evidence_citations", []),
            "grammar_validated": False,
        }

    async def _build_context(self, hcp_id: UUID) -> dict | None:
        factory = get_session_factory()
        async with factory() as session:
            hcp = (await session.execute(
                text("SELECT full_name, specialty FROM hcps WHERE id = :id"),
                {"id": hcp_id},
            )).fetchone()
            if not hcp:
                return None

            pubs = (await session.execute(
                text("""
                    SELECT p.title FROM publications p
                    JOIN publication_authors pa ON p.id = pa.publication_id
                    WHERE pa.hcp_id = :id ORDER BY p.published_at DESC LIMIT 5
                """),
                {"id": hcp_id},
            )).fetchall()

            trials = (await session.execute(
                text("""
                    SELECT ct.title FROM clinical_trials ct
                    JOIN trial_investigators ti ON ct.id = ti.trial_id
                    WHERE ti.hcp_id = :id AND ct.status = 'RECRUITING' LIMIT 3
                """),
                {"id": hcp_id},
            )).fetchall()

            triggers = (await session.execute(
                text("""
                    SELECT event_type, event_data FROM trigger_events
                    WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 5
                """),
                {"id": hcp_id},
            )).fetchall()

            notes = (await session.execute(
                text("""
                    SELECT interaction_type, notes FROM relationship_memory
                    WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 3
                """),
                {"id": hcp_id},
            )).fetchall()

        return {
            "name": hcp[0],
            "specialty": hcp[1] or "Oncology",
            "institution": "Unknown",
            "publications": "; ".join(p[0] for p in pubs) or "None on record",
            "trials": "; ".join(t[0] for t in trials) or "None active",
            "triggers": str([dict(type=t[0], data=t[1]) for t in triggers]) or "None",
            "notes": "; ".join(f"{n[0]}: {n[1]}" for n in notes) or "No prior interactions",
        }

    async def _save(self, hcp_id: UUID, channel: str, data: dict):
        from sqlalchemy import text
        import uuid
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text("""
                    INSERT INTO outreach_messages (id, hcp_id, channel, subject, body, evidence_citations)
                    VALUES (:id, :hcp_id, :channel, :subject, :body, :citations)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "hcp_id": str(hcp_id),
                    "channel": channel,
                    "subject": data.get("subject"),
                    "body": data["body"],
                    "citations": str(data.get("evidence_citations", [])),
                },
            )
            await session.commit()
