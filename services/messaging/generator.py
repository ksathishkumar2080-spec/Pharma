"""Evidence-grounded outreach message generator using Claude + Wiley validation."""
import anthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from messaging.grammar_validator import WileyGrammarValidator
from sqlalchemy import text
import logging
import uuid
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
- LinkedIn InMail: under 1000 chars. Email: include subject line. Follow-up: reference prior interaction.
- End with a clear, low-pressure call to action.

Return JSON with keys:
  subject (string or null),
  body (string),
  evidence_citations (list of {{type, title, id}})
"""


class MessageGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.validator = WileyGrammarValidator()

    async def generate(self, hcp_id: UUID, channel: str, context_notes: str) -> dict | None:
        context = await self._build_context(hcp_id)
        if not context:
            return None

        prompt = MESSAGE_PROMPT.format(channel=channel, context_notes=context_notes, **context)
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text)

        # Grammar + style validation via Wiley (with Claude fallback)
        validation = await self.validator.validate(data["body"])
        final_body = validation.get("corrected") or data["body"]

        await self._save(hcp_id, channel, data, final_body, validation["valid"])
        return {
            "channel": channel,
            "subject": data.get("subject"),
            "body": final_body,
            "evidence_citations": data.get("evidence_citations", []),
            "grammar_validated": True,
            "grammar_issues": validation.get("issues", []),
        }

    async def _build_context(self, hcp_id: UUID) -> dict | None:
        factory = get_session_factory()
        async with factory() as session:
            hcp = (await session.execute(
                text("SELECT h.full_name, h.specialty, i.name FROM hcps h LEFT JOIN institutions i ON h.institution_id = i.id WHERE h.id = :id"),
                {"id": hcp_id},
            )).fetchone()
            if not hcp:
                return None

            pubs = (await session.execute(
                text("""
                    SELECT p.title, p.pubmed_id FROM publications p
                    JOIN publication_authors pa ON p.id = pa.publication_id
                    WHERE pa.hcp_id = :id ORDER BY p.published_at DESC LIMIT 5
                """),
                {"id": hcp_id},
            )).fetchall()

            trials = (await session.execute(
                text("""
                    SELECT ct.title, ct.nct_id FROM clinical_trials ct
                    JOIN trial_investigators ti ON ct.id = ti.trial_id
                    WHERE ti.hcp_id = :id AND ct.status = 'RECRUITING' LIMIT 3
                """),
                {"id": hcp_id},
            )).fetchall()

            triggers = (await session.execute(
                text("SELECT event_type, event_data FROM trigger_events WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 5"),
                {"id": hcp_id},
            )).fetchall()

            notes = (await session.execute(
                text("SELECT interaction_type, notes FROM relationship_memory WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 3"),
                {"id": hcp_id},
            )).fetchall()

        return {
            "name": hcp[0],
            "specialty": hcp[1] or "Oncology",
            "institution": hcp[2] or "Unknown",
            "publications": "; ".join(f"{p[0]} (PMID:{p[1]})" for p in pubs) or "None on record",
            "trials": "; ".join(f"{t[0]} ({t[1]})" for t in trials) or "None active",
            "triggers": str([{"type": t[0], "data": t[1]} for t in triggers]) or "None",
            "notes": "; ".join(f"{n[0]}: {n[1]}" for n in notes) or "No prior interactions",
        }

    async def _save(self, hcp_id: UUID, channel: str, data: dict, final_body: str, validated: bool):
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text("""
                    INSERT INTO outreach_messages (id, hcp_id, channel, subject, body, evidence_citations, grammar_validated)
                    VALUES (:id, :hcp_id, :channel, :subject, :body, :citations, :validated)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "hcp_id": str(hcp_id),
                    "channel": channel,
                    "subject": data.get("subject"),
                    "body": final_body,
                    "citations": json.dumps(data.get("evidence_citations", [])),
                    "validated": validated,
                },
            )
            await session.commit()
