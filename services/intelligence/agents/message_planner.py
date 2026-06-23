"""Message Planner Agent — L13 Human Messaging (pre-generation strategy layer).

Before the Human Messaging Generator writes the actual message, this agent produces
a strategic communication plan:
- Selects the optimal channel (LinkedIn vs email vs conversation starter)
- Identifies the single strongest evidence hook from the HCP's publications
- Determines tone calibration (peer-to-peer vs educational vs action-oriented)
- Drafts talking points ranked by impact
- Sets compliance guardrails for the generator

The MessagePlan object is passed downstream to the HumanMessagingGenerator,
ensuring every message is strategically grounded before LLM generation.
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)


@dataclass
class MessagePlan:
    hcp_id: str
    hcp_name: str
    recommended_channel: str
    tone: str
    primary_evidence_hook: str
    talking_points: list[str]
    call_to_action: str
    compliance_flags: list[str]
    context_summary: str
    urgency: str


PLANNING_PROMPT = """
You are a medical affairs communication strategist for an oncology commercial team.
Create a strategic communication plan for a rep reaching out to this HCP.

HCP Profile:
- Name: {name}
- Specialty: {specialty}
- KOL Tier: {kol_tier}
- Commercial Score: {commercial_score}
- Recent Trigger: {trigger}
- Last Interaction: {last_interaction} ({interaction_type})
- Top Publications (by citations):
{publications}
- Active Trials:
{trials}
- Communication History: {message_count} prior messages, {reply_count} replies

Produce JSON with keys:
  recommended_channel: one of ["linkedin", "email", "conversation_starter", "follow_up"]
  tone: one of ["peer_scientific", "educational", "commercial", "warm_reengagement"]
  primary_evidence_hook: specific publication title or trial to anchor the message
  talking_points: list of 3 ranked talking points (most impactful first)
  call_to_action: specific ask (e.g. "15-min call to discuss DESTINY-Breast04 data")
  compliance_flags: list of topics to avoid or disclose (empty list if none)
  context_summary: 1-2 sentence briefing for the rep
  urgency: one of ["immediate", "this_week", "this_month"]
"""


class MessagePlannerAgent:
    """L13 — strategic planning layer before message generation."""

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def plan(self, hcp_id: str) -> MessagePlan:
        context = await self._gather_hcp_context(hcp_id)
        if "error" in context:
            raise ValueError(context["error"])

        prompt = PLANNING_PROMPT.format(**context)
        response = await self.client.messages.create(
            model=self._settings.anthropic_model_sonnet,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            stripped = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(stripped)

        return MessagePlan(
            hcp_id=hcp_id,
            hcp_name=context["name"],
            recommended_channel=data.get("recommended_channel", "email"),
            tone=data.get("tone", "educational"),
            primary_evidence_hook=data.get("primary_evidence_hook", ""),
            talking_points=data.get("talking_points", []),
            call_to_action=data.get("call_to_action", ""),
            compliance_flags=data.get("compliance_flags", []),
            context_summary=data.get("context_summary", ""),
            urgency=data.get("urgency", "this_month"),
        )

    async def plan_as_dict(self, hcp_id: str) -> dict:
        plan = await self.plan(hcp_id)
        return asdict(plan)

    async def _gather_hcp_context(self, hcp_id: str) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            hcp = (await session.execute(text("""
                SELECT full_name, specialty, kol_tier, commercial_score
                FROM hcps WHERE id = :id
            """), {"id": hcp_id})).fetchone()
            if not hcp:
                return {"error": "HCP not found"}

            trigger = (await session.execute(text("""
                SELECT event_type, event_data->>'title' AS title
                FROM trigger_events WHERE hcp_id = :id
                ORDER BY occurred_at DESC LIMIT 1
            """), {"id": hcp_id})).fetchone()

            last_msg = (await session.execute(text("""
                SELECT interaction_type, occurred_at FROM relationship_memory
                WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 1
            """), {"id": hcp_id})).fetchone()

            pubs = (await session.execute(text("""
                SELECT p.title, p.journal, p.citation_count
                FROM publications p
                JOIN publication_authors pa ON pa.publication_id = p.id
                WHERE pa.hcp_id = :id
                ORDER BY p.citation_count DESC NULLS LAST
                LIMIT 5
            """), {"id": hcp_id})).fetchall() or []

            trials = (await session.execute(text("""
                SELECT ct.title, ct.phase
                FROM clinical_trials ct
                JOIN trial_investigators ti ON ti.trial_id = ct.id
                WHERE ti.hcp_id = :id AND ct.status = 'RECRUITING'
                LIMIT 3
            """), {"id": hcp_id})).fetchall() or []

            msg_count = (await session.execute(text(
                "SELECT COUNT(*) FROM outreach_messages WHERE hcp_id = :id"
            ), {"id": hcp_id})).scalar() or 0

            reply_count = (await session.execute(text(
                "SELECT COUNT(*) FROM outreach_messages WHERE hcp_id = :id AND replied_at IS NOT NULL"
            ), {"id": hcp_id})).scalar() or 0

        return {
            "name": hcp[0],
            "specialty": hcp[1] or "Oncology",
            "kol_tier": hcp[2] or "unknown",
            "commercial_score": hcp[3] or 0,
            "trigger": f"{trigger[0]}: {trigger[1]}" if trigger and trigger[1] else (trigger[0] if trigger else "None"),
            "last_interaction": str(last_msg[1])[:10] if last_msg else "Never",
            "interaction_type": last_msg[0] if last_msg else "None",
            "publications": "\n".join(
                f"  - {p[0]} ({p[1]}, {p[2]} citations)" for p in pubs
            ) or "  None on record",
            "trials": "\n".join(f"  - {t[0]} Phase {t[1]}" for t in trials) or "  None",
            "message_count": msg_count,
            "reply_count": reply_count,
        }
