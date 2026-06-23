"""Biomarker intelligence endpoints — queries ClinVar data from Elasticsearch."""
from fastapi import APIRouter, Query
from elasticsearch import AsyncElasticsearch
from shared.config import get_settings

router = APIRouter()


@router.get("/")
async def search_biomarkers(
    gene: str | None = None,
    significance: str | None = None,
    condition: str | None = None,
    size: int = Query(20, le=100),
):
    settings = get_settings()
    es = AsyncElasticsearch(settings.elasticsearch_url)
    try:
        must = []
        if gene:
            must.append({"term": {"gene": gene.upper()}})
        if significance:
            must.append({"term": {"clinical_significance": significance}})
        if condition:
            must.append({"match": {"conditions": condition}})

        query = {"bool": {"must": must}} if must else {"match_all": {}}
        result = await es.search(
            index="oncology_biomarkers",
            body={"query": query, "size": size, "sort": [{"last_evaluated": {"order": "desc"}}]},
        )
        return [{"score": h["_score"], **h["_source"]} for h in result["hits"]["hits"]]
    finally:
        await es.close()


@router.get("/genes")
async def gene_summary():
    """Aggregated count of variants per gene."""
    settings = get_settings()
    es = AsyncElasticsearch(settings.elasticsearch_url)
    try:
        result = await es.search(
            index="oncology_biomarkers",
            body={"aggs": {"by_gene": {"terms": {"field": "gene", "size": 50}}}, "size": 0},
        )
        buckets = result.get("aggregations", {}).get("by_gene", {}).get("buckets", [])
        return [{"gene": b["key"], "variant_count": b["doc_count"]} for b in buckets]
    finally:
        await es.close()
