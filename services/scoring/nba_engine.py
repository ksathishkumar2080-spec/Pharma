"""Next Best Action (NBA) Engine — produces prioritized rep action queues."""
from shared.db import get_session_factory
from sqlalchemy import text
from anthropic import AsyncAnthropic
from shared.config import get_settings
import logging
import json

log = logging.getLogger(__name__)

NBA_PROMPT = """
You are an oncology commercial intelligence system. Based on the HCP profile below,
determine the single best action a sales rep should take this week.

HCP Profile:
- Name: {name}
- Specialty: {specialty}
- KOL Tier: {kol_tier}
- Commercial Score: {commercial_score}
- Recent Triggers: {triggers}
- Last Interaction: {last_interaction}
- Active Trials: {trials}
- Recent Publications: {publications}

Output JSON with keys:
  action (string: one of ["send_linkedin", "send_email", "schedule_call",
          "invite_to_advisory", "share_data", "trial_referral", "no_action"]),
  rationale (string, 1-2 sentences),
  urgency (string: "high" | "medium" | "low"),
  suggested_talking_points (list of strings, max 3)
"""


class NextBestActionEngine:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model_haiku

    async def get_actions_for_territory(self, state: str | None = None, limit: int = 50) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            where = "WHERE h.is_active = TRUE"
            params: dict = {"limit": limit}
            if state:
                where += " AND h.state = :state"
                params["state"] = state

            rows = (await session.execute(text(f"""
                SELECT h.id, h.full_name, h.specialty, h.kol_tier, h.commercial_score
                FROM hcps h
                {where}
                ORDER BY h.commercial_score DESC
                LIMIT :limit
            """), params)).fetchall() or []

        actions = []
        for row in rows:
            action = await self._compute_nba(row)
            actions.append(action)

        urgency_order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(key=lambda x: urgency_order.get(x.get("urgency", "low"), 2))
        return actions

    async def _compute_nba(self, hcp_row) -> dict:
        hcp_id, name, specialty, kol_tier, commercial_score = hcp_row
        factory = get_session_factory()
        async with factory() as session:
            triggers = (await session.execute(text("""
                SELECT event_type, occurred_at FROM trigger_events
                WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 3
            """), {"id": hcp_id})).fetchall() or []

            last_interaction = (await session.execute(text("""
                SELECT interaction_type, occurred_at FROM relationship_memory
                WHERE hcp_id = :id ORDER BY occurred_at DESC LIMIT 1
            """), {"id": hcp_id})).fetchone()

            trials = (await session.execute(text("""
                SELECT ct.title FROM clinical_trials ct
                JOIN trial_investigators ti ON ct.id = ti.trial_id
                WHERE ti.hcp_id = :id AND ct.status = 'RECRUITING' LIMIT 2
            """), {"id": hcp_id})).fetchall() or []

            pubs = (await session.execute(text("""
                SELECT p.title FROM publications p
                JOIN publication_authors pa ON p.id = pa.publication_id
                WHERE pa.hcp_id = :id ORDER BY p.published_at DESC LIMIT 3
            """), {"id": hcp_id})).fetchall() or []

        prompt = NBA_PROMPT.format(
            name=name,
            specialty=specialty or "Oncology",
            kol_tier=kol_tier or "unknown",
            commercial_score=commercial_score,
            triggers=str([{"type": t[0], "date": str(t[1])} for t in triggers]),
            last_interaction=str(last_interaction) if last_interaction else "None",
            trials="; ".join(t[0] for t in trials) or "None",
            publications="; ".join(p[0] for p in pubs) or "None",
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                stripped = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                result = json.loads(stripped)
            result["hcp_id"] = str(hcp_id)
            result["hcp_name"] = name
            result["commercial_score"] = commercial_score
            return result
        except Exception as e:
            log.error("NBA computation failed for %s: %s", hcp_id, e)
            return {
                "hcp_id": str(hcp_id), "hcp_name": name,
                "action": "no_action", "urgency": "low",
                "rationale": "Insufficient data", "suggested_talking_points": [],
            }
