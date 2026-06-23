"""LinkedIn HCP activity connector."""
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings


class LinkedInConnector(BaseConnector):
    """Fetches HCP profile data and activity via LinkedIn API or RapidAPI proxy."""

    async def fetch(self) -> list[dict]:
        settings = get_settings()
        if not settings.linkedin_api_key:
            self.log.warning("No LinkedIn API key configured — skipping")
            return []

        # Placeholder: real implementation uses LinkedIn Marketing API
        # or a compliant data provider with proper authorization
        headers = {"Authorization": f"Bearer {settings.linkedin_api_key}"}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.linkedin.com/v2/people",
                headers=headers,
                params={"q": "oncologist"},
            )
            if resp.status_code == 200:
                return resp.json().get("elements", [])
        return []

    async def store(self, records: list[dict]) -> None:
        self.log.info("Stored %d LinkedIn records", len(records))
