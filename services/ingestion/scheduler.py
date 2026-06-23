"""Cron-style ingestion scheduler."""
import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# (connector_class, interval_hours)
SCHEDULE = [
    ("ingestion.connectors.pubmed.PubMedConnector", 6),
    ("ingestion.connectors.clinical_trials.ClinicalTrialsConnector", 12),
    ("ingestion.connectors.news.NewsConnector", 1),
    ("ingestion.connectors.twitter_monitor.TwitterMonitor", 1),
    ("ingestion.connectors.reddit_monitor.RedditMonitor", 2),
    ("ingestion.connectors.nccn_watcher.NCCNWatcher", 24),
    ("ingestion.connectors.asco_scraper.ASCOScraper", 48),
    ("ingestion.connectors.esmo_scraper.ESMOScraper", 48),
    ("ingestion.connectors.aacr_scraper.AACRScraper", 48),
    ("ingestion.connectors.sabcs_scraper.SABCSScraper", 48),
    ("ingestion.connectors.linkedin.LinkedInConnector", 24),
]


def _import_class(dotted: str):
    module_path, class_name = dotted.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


async def _run_connector(dotted: str, interval_hours: int):
    cls = _import_class(dotted)
    connector = cls()
    while True:
        try:
            log.info("[scheduler] Running %s", dotted)
            await connector.run()
        except Exception as e:
            log.error("[scheduler] %s failed: %s", dotted, e)
        await asyncio.sleep(interval_hours * 3600)


async def run_scheduler():
    log.info("Ingestion scheduler starting with %d connectors", len(SCHEDULE))
    await asyncio.gather(*[_run_connector(cls, hrs) for cls, hrs in SCHEDULE])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())
