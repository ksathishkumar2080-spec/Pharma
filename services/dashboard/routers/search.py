from fastapi import APIRouter, Query
from elasticsearch import AsyncElasticsearch
from shared.config import get_settings

router = APIRouter()


@router.get("/")
async def semantic_search(
    q: str = Query(..., description="Full-text search query"),
    index: str = Query("oncology_news", description="Elasticsearch index to search"),
    size: int = Query(10, le=50),
):
    settings = get_settings()
    es = AsyncElasticsearch(settings.elasticsearch_url)
    try:
        result = await es.search(
            index=index,
            body={"query": {"multi_match": {"query": q, "fields": ["title^2", "abstract", "content"]}}, "size": size},
        )
        hits = result["hits"]["hits"]
        return [{"score": h["_score"], "source": h["_source"]} for h in hits]
    finally:
        await es.close()
