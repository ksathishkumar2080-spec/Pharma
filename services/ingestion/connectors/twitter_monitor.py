"""X/Twitter oncology community monitor via Twitter API v2."""
import httpx
from ingestion.connectors.base import BaseConnector
from shared.config import get_settings

ONCOLOGY_QUERY = "#oncology OR #ASCO2025 OR #ESMO2025 OR #cancerresearch -is:retweet lang:en"


class TwitterMonitor(BaseConnector):
    async def fetch(self) -> list[dict]:
        settings = get_settings()
        bearer = getattr(settings, "twitter_bearer_token", "")
        if not bearer:
            self.log.warning("No Twitter bearer token configured")
            return []

        headers = {"Authorization": f"Bearer {bearer}"}
        params = {
            "query": ONCOLOGY_QUERY,
            "max_results": 100,
            "tweet.fields": "author_id,created_at,entities,public_metrics",
            "expansions": "author_id",
            "user.fields": "name,username,description",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                self.log.warning("Twitter API error: %s", resp.status_code)
                return []
            data = resp.json()
        return data.get("data", [])

    async def store(self, records: list[dict]) -> None:
        from elasticsearch import AsyncElasticsearch
        from shared.config import get_settings
        es = AsyncElasticsearch(get_settings().elasticsearch_url)
        for tweet in records:
            await es.index(index="oncology_social", document={"source": "twitter", **tweet})
        await es.close()
