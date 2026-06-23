"""ResearchGate HCP activity monitor."""
import httpx
from ingestion.connectors.base import BaseConnector


class ResearchGateConnector(BaseConnector):
    """Monitors ResearchGate for HCP publication activity via public profile pages."""

    async def fetch(self) -> list[dict]:
        # ResearchGate does not provide a public API.
        # Production: use a compliant data vendor or authenticated scraping with consent.
        # This stub demonstrates the integration point.
        self.log.info("ResearchGate connector: configure a compliant data vendor API key")
        return []

    async def store(self, records: list[dict]) -> None:
        pass
