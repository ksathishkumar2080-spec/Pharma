"""ClinVar (NCBI) biomarker variant connector.

Docs: https://www.ncbi.nlm.nih.gov/clinvar/ (NCBI E-utilities)
Free, NCBI API key optional (increases rate limit 10x).
Fetches oncology-relevant variant-disease associations.
"""
import asyncio
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings
from shared.db import get_session_factory
from elasticsearch import AsyncElasticsearch
from sqlalchemy import text

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CLINVAR_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# High-value oncology biomarker genes
ONCOLOGY_GENES = [
    "BRCA1", "BRCA2",   # Breast/ovarian cancer
    "KRAS", "NRAS",     # Colorectal, lung, pancreatic
    "EGFR",             # Lung cancer
    "ALK",              # Lung cancer
    "BRAF",             # Melanoma, colorectal
    "HER2",             # Breast, gastric
    "PIK3CA",           # Multiple cancers
    "TP53",             # Pan-cancer
    "PTEN",             # Multiple cancers
    "RET",              # Thyroid, lung
    "MET",              # Lung, gastric
    "FGFR2",            # Cholangiocarcinoma
    "IDH1", "IDH2",    # Glioma, AML
    "FLT3",             # AML
    "NPM1",             # AML
    "BCR-ABL1",         # CML
]


class ClinVarConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        settings = get_settings()
        self._api_key = settings.ncbi_api_key
        self._email = settings.ncbi_email

    def _params(self, extra: dict) -> dict:
        p = {"retmode": "json", **extra}
        if self._api_key:
            p["api_key"] = self._api_key
        if self._email:
            p["email"] = self._email
        return p

    async def fetch(self) -> list[dict]:
        variants = []
        async with httpx.AsyncClient(timeout=30) as client:
            for gene in ONCOLOGY_GENES:
                batch = await self._fetch_gene_variants(client, gene)
                variants.extend(batch)
                # NCBI rate limit: 10/sec with key, 3/sec without
                await asyncio.sleep(0.5 if self._api_key else 1.5)
        self.log.info("ClinVar: fetched %d variants across %d genes", len(variants), len(ONCOLOGY_GENES))
        return variants

    async def _fetch_gene_variants(self, client: httpx.AsyncClient, gene: str) -> list[dict]:
        try:
            # Step 1: Search ClinVar for pathogenic variants in this gene
            search_resp = await client.get(
                f"{BASE}/esearch.fcgi",
                params=self._params({
                    "db": "clinvar",
                    "term": f'{gene}[gene] AND ("pathogenic"[sig] OR "likely pathogenic"[sig]) AND cancer[dis]',
                    "retmax": 50,
                }),
            )
            search_resp.raise_for_status()
            ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            # Step 2: Fetch summaries
            summary_resp = await client.get(
                f"{BASE}/esummary.fcgi",
                params=self._params({
                    "db": "clinvar",
                    "id": ",".join(ids[:20]),
                }),
            )
            summary_resp.raise_for_status()
            result = summary_resp.json().get("result", {})
            return [
                {**result[vid], "gene_symbol": gene}
                for vid in ids[:20]
                if vid in result
            ]
        except Exception as e:
            self.log.warning("ClinVar fetch failed for %s: %s", gene, e)
            return []

    async def store(self, records: list[dict]) -> None:
        """Store variants in Elasticsearch for biomarker intelligence queries."""
        settings = get_settings()
        es = AsyncElasticsearch(settings.elasticsearch_url)
        stored = 0
        for variant in records:
            try:
                await es.index(
                    index="oncology_biomarkers",
                    id=str(variant.get("uid", "")),
                    document={
                        "gene": variant.get("gene_symbol"),
                        "variant_id": variant.get("uid"),
                        "title": variant.get("title", ""),
                        "clinical_significance": variant.get("clinical_significance", {}).get("description"),
                        "conditions": [
                            t.get("trait_name", "")
                            for t in variant.get("trait_set", [])
                        ],
                        "review_status": variant.get("review_status"),
                        "last_evaluated": variant.get("last_evaluated"),
                    },
                )
                stored += 1
            except Exception as e:
                self.log.warning("ES index failed for variant: %s", e)
        await es.close()
        self.log.info("ClinVar: indexed %d variants", stored)
