"""Temporal workflow definitions for the intelligence pipeline."""
# Requires: pip install temporalio
# Start worker: python -m workflows.worker

try:
    from temporalio import workflow, activity
    from temporalio.client import Client
    from temporalio.worker import Worker
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False

import asyncio
import logging

log = logging.getLogger(__name__)


if TEMPORAL_AVAILABLE:
    @workflow.defn
    class OncologyIntelPipeline:
        @workflow.run
        async def run(self) -> str:
            await workflow.execute_activity(
                ingest_all_sources,
                schedule_to_close_timeout=workflow.timedelta(minutes=30),
            )
            await workflow.execute_activity(
                resolve_identities,
                schedule_to_close_timeout=workflow.timedelta(minutes=10),
            )
            await workflow.execute_activity(
                sync_knowledge_graph,
                schedule_to_close_timeout=workflow.timedelta(minutes=10),
            )
            await workflow.execute_activity(
                enrich_entities,
                schedule_to_close_timeout=workflow.timedelta(minutes=20),
            )
            await workflow.execute_activity(
                score_hcps,
                schedule_to_close_timeout=workflow.timedelta(minutes=10),
            )
            await workflow.execute_activity(
                detect_triggers,
                schedule_to_close_timeout=workflow.timedelta(minutes=10),
            )
            return "Pipeline complete"

    @activity.defn
    async def ingest_all_sources() -> None:
        from ingestion.main import run_all
        await run_all()

    @activity.defn
    async def resolve_identities() -> None:
        from identity.resolver import HCPResolver
        await HCPResolver().run()

    @activity.defn
    async def sync_knowledge_graph() -> None:
        from graph.builder import GraphBuilder
        await GraphBuilder().sync()

    @activity.defn
    async def enrich_entities() -> None:
        from enrichment.main import main
        await main()

    @activity.defn
    async def score_hcps() -> None:
        from scoring.engine import ScoringEngine
        await ScoringEngine().score_all()

    @activity.defn
    async def detect_triggers() -> None:
        from triggers.detector import TriggerDetector
        await TriggerDetector().run()

    async def start_worker():
        client = await Client.connect("localhost:7233")
        worker = Worker(
            client,
            task_queue="oncology-intel",
            workflows=[OncologyIntelPipeline],
            activities=[ingest_all_sources, resolve_identities, sync_knowledge_graph,
                        enrich_entities, score_hcps, detect_triggers],
        )
        await worker.run()

    if __name__ == "__main__":
        asyncio.run(start_worker())
else:
    log.warning("temporalio not installed — workflow orchestration disabled")
