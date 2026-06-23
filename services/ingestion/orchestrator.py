"""Research API Orchestrator — runs all sources once in dependency order."""
import asyncio
import logging
from ingestion.connectors.pubmed import PubMedConnector
from ingestion.connectors.semantic_scholar import SemanticScholarConnector
from ingestion.connectors.openalex import OpenAlexConnector
from ingestion.connectors.crossref import CrossRefConnector
from ingestion.connectors.europe_pmc import EuropePMCConnector
from ingestion.connectors.biorxiv import BioRxivConnector
from ingestion.connectors.core_api import COREAPIConnector
from ingestion.connectors.clinical_trials import ClinicalTrialsConnector
from ingestion.connectors.who_ictrp import WHOICTRPConnector
from ingestion.connectors.fda_approvals import FDAApprovalsConnector
from ingestion.connectors.clinvar import ClinVarConnector
from ingestion.connectors.wiley_tdm import WileyTDMConnector
from ingestion.connectors.nccn_watcher import NCCNWatcher
from ingestion.connectors.news import NewsConnector
from ingestion.connectors.twitter_monitor import TwitterMonitor
from ingestion.connectors.reddit_monitor import RedditMonitor

log = logging.getLogger(__name__)


class ResearchAPIOrchestrator:
    """
    Runs all research API connectors in two phases:
    1. Publication sources (PubMed, S2, OpenAlex, CrossRef, EuropePMC, bioRxiv, CORE)
    2. Trial + regulatory sources (CT.gov, WHO ICTRP, FDA, ClinVar, NCCN)
    3. Full-text enrichment (Wiley TDM)
    4. Social/news signals (News RSS, Twitter, Reddit)
    """

    async def run_all(self, parallel: bool = True):
        log.info("ResearchAPIOrchestrator: starting full pipeline run")

        # Phase 1: Publication databases (can run in parallel)
        pub_connectors = [
            PubMedConnector(),
            SemanticScholarConnector(),
            OpenAlexConnector(),
            CrossRefConnector(),
            EuropePMCConnector(),
            BioRxivConnector(),
            COREAPIConnector(),
        ]

        # Phase 2: Trial and regulatory
        trial_connectors = [
            ClinicalTrialsConnector(),
            WHOICTRPConnector(),
            FDAApprovalsConnector(),
            ClinVarConnector(),
            NCCNWatcher(),
        ]

        # Phase 3: Full text enrichment
        fulltext_connectors = [
            WileyTDMConnector(),
        ]

        # Phase 4: Social / news
        social_connectors = [
            NewsConnector(),
            TwitterMonitor(),
            RedditMonitor(),
        ]

        if parallel:
            log.info("Running Phase 1: publication databases")
            await asyncio.gather(*[c.run() for c in pub_connectors], return_exceptions=True)

            log.info("Running Phase 2: trials & regulatory")
            await asyncio.gather(*[c.run() for c in trial_connectors], return_exceptions=True)

            log.info("Running Phase 3: full-text enrichment")
            await asyncio.gather(*[c.run() for c in fulltext_connectors], return_exceptions=True)

            log.info("Running Phase 4: social & news signals")
            await asyncio.gather(*[c.run() for c in social_connectors], return_exceptions=True)
        else:
            for connector in pub_connectors + trial_connectors + fulltext_connectors + social_connectors:
                try:
                    await connector.run()
                except Exception as e:
                    log.error("%s failed: %s", connector.__class__.__name__, e)

        log.info("ResearchAPIOrchestrator: pipeline run complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ResearchAPIOrchestrator().run_all())
