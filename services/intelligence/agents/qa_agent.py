"""QA Agent — L13 Human Messaging (quality gate).

Runs a structured quality check on every AI-generated message before it is
sent or surfaced to the rep. Catches:
- Unsubstantiated clinical claims
- Off-label promotion language
- Tone mismatches (too promotional, not peer-appropriate)
- Missing evidence citations
- Grammar / readability issues beyond Wiley style
- Compliance red flags (comparative claims, superiority language)

Returns a QAResult with pass/fail, issue list, and a revised message if needed.
Works alongside Citation Validator (L16) and Wiley Grammar (L13).
"""
from anthropic import AsyncAnthropic
import json
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)


@dataclass
class QAResult:
    message_id: str | None
    passed: bool
    overall_score: int
    issues: list[dict] = field(default_factory=list)
    revised_message: str | None = None
    compliance_flags: list[str] = field(default_factory=list)
    reviewer_notes: str = ""


QA_PROMPT = """
You are a medical affairs QA reviewer for an oncology commercial team.
Review the following outreach message for quality, accuracy, and compliance.

Channel: {channel}
HCP Tier: {kol_tier}
Message:
---
{message_body}
---

Evidence available for this HCP:
{evidence_summary}

Check for ALL of the following and produce JSON:
  passed: boolean — true only if no CRITICAL or HIGH issues
  overall_score: integer 0-100 (100 = publication-ready)
  issues: list of {{
    severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
    type: "unsubstantiated_claim" | "off_label" | "tone" | "missing_citation" | "grammar" | "compliance" | "other",
    description: string,
    location: excerpt from message where issue appears
  }}
  revised_message: corrected version of the full message (null if passed=true and score>=85)
  compliance_flags: list of specific compliance concerns (empty list if none)
  reviewer_notes: 1-2 sentence summary for the rep
"""


class QAAgent:
    """L13 — quality gate for generated messages before delivery to rep or HCP."""

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def review_message(
        self,
        message_body: str,
        channel: str = "email",
        hcp_id: str | None = None,
        message_id: str | None = None,
    ) -> QAResult:
        evidence_summary = await self._get_evidence_summary(hcp_id) if hcp_id else "No HCP context provided"
        kol_tier = await self._get_kol_tier(hcp_id) if hcp_id else "unknown"

        prompt = QA_PROMPT.format(
            channel=channel,
            kol_tier=kol_tier,
            message_body=message_body,
            evidence_summary=evidence_summary,
        )
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

        return QAResult(
            message_id=message_id,
            passed=data.get("passed", False),
            overall_score=data.get("overall_score", 0),
            issues=data.get("issues", []),
            revised_message=data.get("revised_message"),
            compliance_flags=data.get("compliance_flags", []),
            reviewer_notes=data.get("reviewer_notes", ""),
        )

    async def review_message_as_dict(self, **kwargs) -> dict:
        result = await self.review_message(**kwargs)
        return asdict(result)

    async def batch_review_pending(self, limit: int = 20) -> list[dict]:
        """Review all unsent messages that have not been QA-checked yet."""
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT id, hcp_id, channel, body
                FROM outreach_messages
                WHERE sent_at IS NULL
                  AND grammar_validated = TRUE
                ORDER BY created_at ASC
                LIMIT :limit
            """), {"limit": limit})).fetchall() or []

        results = []
        for row in rows:
            msg_id, hcp_id, channel, body = row
            try:
                result = await self.review_message(
                    message_body=body,
                    channel=channel,
                    hcp_id=str(hcp_id),
                    message_id=str(msg_id),
                )
                results.append(asdict(result))
            except Exception as e:
                log.error("QA review failed for message %s: %s", msg_id, e)
        return results

    async def _get_evidence_summary(self, hcp_id: str) -> str:
        factory = get_session_factory()
        async with factory() as session:
            pubs = (await session.execute(text("""
                SELECT p.title, p.journal, p.citation_count
                FROM publications p
                JOIN publication_authors pa ON pa.publication_id = p.id
                WHERE pa.hcp_id = :id
                ORDER BY p.citation_count DESC NULLS LAST LIMIT 5
            """), {"id": hcp_id})).fetchall() or []

        if not pubs:
            return "No publications on record for this HCP"
        return "\n".join(f"- {p[0]} ({p[1]}, {p[2]} citations)" for p in pubs)

    async def _get_kol_tier(self, hcp_id: str) -> str:
        factory = get_session_factory()
        async with factory() as session:
            row = (await session.execute(
                text("SELECT kol_tier FROM hcps WHERE id = :id"), {"id": hcp_id}
            )).fetchone()
        return row[0] if row else "unknown"
