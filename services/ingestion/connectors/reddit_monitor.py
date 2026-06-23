"""Reddit oncology community monitor (r/oncology, r/cancer, r/leukemia, etc.)."""
import httpx
from ingestion.connectors.base import BaseConnector

SUBREDDITS = ["oncology", "cancer", "leukemia", "breastcancer", "lungcancer", "prostatecancer"]
HEADERS = {"User-Agent": "OncologyIntelBot/1.0"}


class RedditMonitor(BaseConnector):
    async def fetch(self) -> list[dict]:
        records = []
        async with httpx.AsyncClient(timeout=20) as client:
            for sub in SUBREDDITS:
                try:
                    resp = await client.get(
                        f"https://www.reddit.com/r/{sub}/new.json",
                        headers=HEADERS,
                        params={"limit": 25},
                    )
                    if resp.status_code == 200:
                        posts = resp.json()["data"]["children"]
                        for post in posts:
                            d = post["data"]
                            records.append({
                                "source": f"reddit/{sub}",
                                "title": d.get("title", ""),
                                "selftext": d.get("selftext", "")[:1000],
                                "url": d.get("url", ""),
                                "score": d.get("score", 0),
                                "created_utc": d.get("created_utc"),
                            })
                except Exception as e:
                    self.log.warning("Reddit %s error: %s", sub, e)
        return records

    async def store(self, records: list[dict]) -> None:
        from elasticsearch import AsyncElasticsearch
        from shared.config import get_settings
        es = AsyncElasticsearch(get_settings().elasticsearch_url)
        for rec in records:
            await es.index(index="oncology_social", document=rec)
        await es.close()
