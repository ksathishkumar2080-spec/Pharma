"""Cron-style ingestion scheduler with all research API connectors."""
import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# (connector_dotted_path, interval_hours)
SCHEDULE = [
    # --- High-frequency sources ---
    ("ingestion.connectors.news.NewsConnector",                   1),
    ("ingestion.connectors.twitter_monitor.TwitterMonitor",       1),
    ("ingestion.connectors.reddit_monitor.RedditMonitor",         2),
    ("ingestion.connectors.biorxiv.BioRxivConnector",             4),

    # --- Core research databases (daily) ---
    ("ingestion.connectors.pubmed.PubMedConnector",               6),
    ("ingestion.connectors.clinical_trials.ClinicalTrialsConnector", 12),
    ("ingestion.connectors.semantic_scholar.SemanticScholarConnector", 12),
    ("ingestion.connectors.openalex.OpenAlexConnector",           12),
    ("ingestion.connectors.crossref.CrossRefConnector",           24),
    ("ingestion.connectors.europe_pmc.EuropePMCConnector",        24),
    ("ingestion.connectors.core_api.COREAPIConnector",            24),

    # --- Regulatory & biomarker ---
    ("ingestion.connectors.fda_approvals.FDAApprovalsConnector",  24),
    ("ingestion.connectors.clinvar.ClinVarConnector",             48),
    ("ingestion.connectors.who_ictrp.WHOICTRPConnector",          24),

    # --- Full-text (requires API keys) ---
    ("ingestion.connectors.wiley_tdm.WileyTDMConnector",          24),

    # --- Conference (weekly/slow) ---
    ("ingestion.connectors.nccn_watcher.NCCNWatcher",             24),
    ("ingestion.connectors.asco_scraper.ASCOScraper",             48),
    ("ingestion.connectors.esmo_scraper.ESMOScraper",             48),
    ("ingestion.connectors.aacr_scraper.AACRScraper",             48),
    ("ingestion.connectors.sabcs_scraper.SABCSScraper",           48),

    # --- HCP enrichment ---
    ("ingestion.connectors.linkedin.LinkedInConnector",           24),
]

_connector_status: dict[str, dict] = {}


def _import_class(dotted: str):
    module_path, class_name = dotted.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


async def _run_connector(dotted: str, interval_hours: int):
    cls = _import_class(dotted)
    connector = cls()
    _connector_status[dotted] = {"status": "starting", "last_run": None, "last_error": None}

    while True:
        _connector_status[dotted]["status"] = "running"
        _connector_status[dotted]["last_run"] = datetime.now(timezone.utc).isoformat()
        try:
            log.info("[scheduler] Running %s", dotted)
            await connector.run()
            _connector_status[dotted]["status"] = "ok"
            _connector_status[dotted]["last_error"] = None
        except Exception as e:
            log.error("[scheduler] %s failed: %s", dotted, e)
            _connector_status[dotted]["status"] = "error"
            _connector_status[dotted]["last_error"] = str(e)
        await asyncio.sleep(interval_hours * 3600)


def get_connector_status() -> dict:
    return {
        k.split(".")[-1]: v
        for k, v in _connector_status.items()
    }


async def run_scheduler():
    log.info("Ingestion scheduler starting with %d connectors", len(SCHEDULE))
    await asyncio.gather(*[_run_connector(cls, hrs) for cls, hrs in SCHEDULE])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduler())
