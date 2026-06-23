"""Research API Orchestrator — runs all sources once in dependency order."""
import asyncio
import logging
from .connectors.pubmed import PubMedConnector
from .connectors.semantic_scholar import SemanticScholarConnector
from .connectors.openalex import OpenAlexConnector
from .connectors.crossref import CrossRefConnector
from .connectors.europe_pmc import EuropePMCConnector
from .connectors.biorxiv import BioRxivConnector
from .connectors.core_api import COREAPIConnector
from .connectors.clinical_trials import ClinicalTrialsConnector
from .connectors.who_ictrp import WHOICTRPConnector
from .connectors.fda_approvals import FDAApprovalsConnector
from .connectors.clinvar import ClinVarConnector
from .connectors.wiley_tdm import WileyTDMConnector
from .connectors.nccn_watcher import NCCNWatcher
from .connectors.news import NewsConnector
from .connectors.twitter_monitor import TwitterMonitor
from .connectors.reddit_monitor import RedditMonitor

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

        pub_connectors = [
            PubMedConnector(),
            SemanticScholarConnector(),
            OpenAlexConnector(),
            CrossRefConnector(),
            EuropePMCConnector(),
            BioRxivConnector(),
            COREAPIConnector(),
        ]

        trial_connectors = [
            ClinicalTrialsConnector(),
            WHOICTRPConnector(),
            FDAApprovalsConnector(),
            ClinVarConnector(),
            NCCNWatcher(),
        ]

        fulltext_connectors = [WileyTDMConnector()]

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
