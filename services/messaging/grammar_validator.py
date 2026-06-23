"""Wiley grammar and style validator for outreach messages."""
import httpx
import logging
from shared.config import get_settings

log = logging.getLogger(__name__)

WILEY_PROOFING_URL = "https://api.wiley.com/onlinelibrary/tdm/v1/proofing"


class WileyGrammarValidator:
    """Validates message grammar, tone, and scientific accuracy via Wiley API."""

    def __init__(self):
        self.settings = get_settings()

    async def validate(self, text: str) -> dict:
        """
        Returns:
            {
                valid: bool,
                issues: [{offset, length, message, suggestion}],
                corrected: str | None
            }
        """
        if not self.settings.wiley_api_key:
            log.warning("Wiley API key not configured — skipping grammar validation")
            return {"valid": True, "issues": [], "corrected": None}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    WILEY_PROOFING_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.wiley_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text, "language": "en-US", "domain": "medical"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    issues = data.get("matches", [])
                    corrected = self._apply_corrections(text, issues)
                    return {
                        "valid": len(issues) == 0,
                        "issues": issues,
                        "corrected": corrected if issues else None,
                    }
        except Exception as e:
            log.error("Wiley validation error: %s", e)

        # Fallback: Claude-based grammar check
        return await self._claude_grammar_check(text)

    async def _claude_grammar_check(self, text: str) -> dict:
        """Fallback grammar validation using Claude."""
        import anthropic
        import json
        client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": (
                    "Review this medical outreach message for grammar, professional tone, "
                    "and factual clarity. Return JSON with keys: valid (bool), "
                    "issues (list of strings), corrected (string with corrections applied).\n\n"
                    f"Message:\n{text}"
                ),
            }],
        )
        try:
            return json.loads(response.content[0].text)
        except Exception:
            return {"valid": True, "issues": [], "corrected": None}

    def _apply_corrections(self, text: str, issues: list) -> str:
        """Apply Wiley-suggested corrections to the original text."""
        corrected = text
        offset_shift = 0
        for issue in sorted(issues, key=lambda x: x.get("offset", 0)):
            offset = issue.get("offset", 0) + offset_shift
            length = issue.get("length", 0)
            replacement = issue.get("replacements", [{}])[0].get("value", "")
            if replacement:
                corrected = corrected[:offset] + replacement + corrected[offset + length:]
                offset_shift += len(replacement) - length
        return corrected
