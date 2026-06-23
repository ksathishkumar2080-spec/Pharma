"""Enrichment pipeline — extracts structured data from raw text using Claude."""
import asyncio
import logging
from enrichment.pipelines.publication import PublicationEnrichmentPipeline
from enrichment.pipelines.hcp_profile import HCPProfilePipeline

logging.basicConfig(level=logging.INFO)


async def main():
    await asyncio.gather(
        PublicationEnrichmentPipeline().run(),
        HCPProfilePipeline().run(),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
