"""Initialize Elasticsearch indices with proper mappings on startup."""
import asyncio
import json
from pathlib import Path
from elasticsearch import AsyncElasticsearch
from shared.config import get_settings

MAPPINGS_DIR = Path(__file__).parent / "mappings"

INDICES = [
    "oncology_biomarkers",
    "conference_abstracts",
    "publication_fulltext",
    "oncology_news",
    "oncology_social",
]


async def init_indices():
    settings = get_settings()
    es = AsyncElasticsearch(settings.elasticsearch_url)

    for index in INDICES:
        mapping_file = MAPPINGS_DIR / f"{index}.json"
        mapping = json.loads(mapping_file.read_text()) if mapping_file.exists() else {}

        if not await es.indices.exists(index=index):
            await es.indices.create(index=index, body=mapping)
            print(f"Created index: {index}")
        else:
            print(f"Index already exists: {index}")

    await es.close()


if __name__ == "__main__":
    asyncio.run(init_indices())
