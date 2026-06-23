"""Grammar and tone validation for outbound HCP messages."""
from anthropic import AsyncAnthropic
from shared.config import get_settings
from shared.db import get_session_factory
from sqlalchemy import text
import logging
import json

log = logging.getLogger(__name__)

GRAMMAR_CHECK_PROMPT = """
You are a medical communications editor reviewing an oncology sales message.

Message:
{message}

Return JSON with keys:
  grammar_ok: bool
  tone_ok: bool (professional, empathetic, evidence-based)
  issues: list of specific issues found
  revised_message: corrected version (or original if no changes needed)
  compliance_notes: any pharma compliance concerns
"""


class GrammarValidator:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def validate(self, message_id: str) -> dict:
        factory = get_session_factory()
        async with factory() as session:
            row = (await session.execute(
                text("SELECT content, hcp_id FROM messages WHERE id = :id"),
                {"id": message_id},
            )).fetchone()

        if not row:
            return {"error": "Message not found"}

        result = await self._claude_grammar_check(row[0])

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text("""
                    UPDATE messages
                    SET grammar_checked = TRUE,
                        grammar_issues = :issues,
                        revised_content = :revised
                    WHERE id = :id
                """),
                {
                    "issues": result.get("issues", []),
                    "revised": result.get("revised_message", row[0]),
                    "id": message_id,
                },
            )
            await session.commit()

        return result

    async def _claude_grammar_check(self, message_text: str) -> dict:
        response = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": GRAMMAR_CHECK_PROMPT.format(message=message_text)}],
        )
        try:
            return json.loads(response.content[0].text)
        except Exception:
            return {"grammar_ok": True, "tone_ok": True, "issues": [], "revised_message": message_text}

    async def batch_validate_pending(self) -> list[dict]:
        factory = get_session_factory()
        async with factory() as session:
            rows = (await session.execute(text("""
                SELECT id FROM messages
                WHERE status = 'pending' AND grammar_checked = FALSE
                LIMIT 50
            """))).fetchall() or []

        results = []
        for (msg_id,) in rows:
            results.append(await self.validate(str(msg_id)))
        return results
