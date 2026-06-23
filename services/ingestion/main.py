"""Ingestion service entry point — runs all connectors on schedule."""
import asyncio
import logging
from ingestion.connectors.pubmed import PubMedConnector
from ingestion.connectors.clinical_trials import ClinicalTrialsConnector
from ingestion.connectors.conferences import ConferenceConnector
from ingestion.connectors.news import NewsConnector
from ingestion.connectors.linkedin import LinkedInConnector

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def run_all():
    connectors = [
        PubMedConnector(),
        ClinicalTrialsConnector(),
        ConferenceConnector(),
        NewsConnector(),
        LinkedInConnector(),
    ]
    await asyncio.gather(*[c.run() for c in connectors], return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(run_all())
