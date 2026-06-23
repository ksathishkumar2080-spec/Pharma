"""System health and connector status endpoints."""
from fastapi import APIRouter
import httpx
from shared.config import get_settings

router = APIRouter()


@router.get("/health")
async def system_health():
    settings = get_settings()
    checks = {}

    async with httpx.AsyncClient(timeout=5) as client:
        # PostgreSQL (via dashboard itself being alive)
        checks["api"] = "ok"

        # Elasticsearch
        try:
            resp = await client.get(f"{settings.elasticsearch_url}/_cluster/health")
            checks["elasticsearch"] = resp.json().get("status", "unknown")
        except Exception:
            checks["elasticsearch"] = "unreachable"

        # Neo4j
        try:
            resp = await client.get(f"http://neo4j:7474")
            checks["neo4j"] = "ok" if resp.status_code < 400 else "degraded"
        except Exception:
            checks["neo4j"] = "unreachable"

        # Redis
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            checks["redis"] = "ok"
            await r.aclose()
        except Exception:
            checks["redis"] = "unreachable"

    return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded", "checks": checks}


@router.get("/connectors")
async def connector_status():
    """Live status of all ingestion connectors."""
    try:
        from ingestion.scheduler import get_connector_status
        return get_connector_status()
    except ImportError:
        return {"error": "Ingestion service not co-located. Query ingestion service directly."}


@router.get("/indices")
async def elasticsearch_indices():
    """List Elasticsearch indices and document counts."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{settings.elasticsearch_url}/_cat/indices?format=json")
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
