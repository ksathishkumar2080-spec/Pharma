"""PubMed connector using NCBI E-utilities API."""
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ONCOLOGY_QUERY = (
    "(oncology[MeSH] OR cancer[MeSH] OR tumor[MeSH] OR neoplasm[MeSH]) "
    "AND (2023[PDAT]:3000[PDAT])"
)


class PubMedConnector(BaseConnector):
    async def fetch(self) -> list[dict]:
        settings = get_settings()
        params = {
            "db": "pubmed",
            "term": ONCOLOGY_QUERY,
            "retmax": 500,
            "retmode": "json",
            "api_key": settings.ncbi_api_key,
            "email": settings.ncbi_email,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            search = await client.get(f"{BASE_URL}/esearch.fcgi", params=params)
            search.raise_for_status()
            ids = search.json()["esearchresult"]["idlist"]

            if not ids:
                return []

            fetch_params = {
                "db": "pubmed",
                "id": ",".join(ids),
                "retmode": "json",
                "api_key": settings.ncbi_api_key,
            }
            detail = await client.get(f"{BASE_URL}/efetch.fcgi", params=fetch_params)
            detail.raise_for_status()
            articles = detail.json().get("PubmedArticle", [])

        return self._parse(articles)

    def _parse(self, articles: list) -> list[dict]:
        out = []
        for art in articles:
            try:
                medline = art["MedlineCitation"]
                article = medline["Article"]
                pmid = str(medline["PMID"]["#text"])
                title = article.get("ArticleTitle", "")
                abstract_texts = (
                    article.get("Abstract", {}).get("AbstractText", []) or []
                )
                abstract = " ".join(
                    t if isinstance(t, str) else t.get("#text", "") for t in abstract_texts
                )
                authors = [
                    f"{a.get('LastName', '')} {a.get('ForeName', '')}".strip()
                    for a in article.get("AuthorList", {}).get("Author", [])
                    if isinstance(a, dict)
                ]
                journal = article.get("Journal", {}).get("Title", "")
                out.append({
                    "pubmed_id": pmid,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "journal": journal,
                    "raw_json": art,
                })
            except (KeyError, TypeError):
                continue
        return out

    async def store(self, records: list[dict]) -> None:
        # Upsert into PostgreSQL publications table
        from shared.db import get_session_factory
        from sqlalchemy import text

        factory = get_session_factory()
        async with factory() as session:
            for rec in records:
                await session.execute(
                    text("""
                        INSERT INTO publications (pubmed_id, title, abstract, journal, raw_json)
                        VALUES (:pubmed_id, :title, :abstract, :journal, :raw_json)
                        ON CONFLICT (pubmed_id) DO UPDATE
                        SET title = EXCLUDED.title,
                            abstract = EXCLUDED.abstract,
                            journal = EXCLUDED.journal
                    """),
                    {
                        "pubmed_id": rec["pubmed_id"],
                        "title": rec["title"],
                        "abstract": rec["abstract"],
                        "journal": rec["journal"],
                        "raw_json": str(rec["raw_json"]),
                    },
                )
            await session.commit()
