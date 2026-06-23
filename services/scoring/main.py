"""Lead and opportunity scoring service."""
import asyncio
import logging
from scoring.engine import ScoringEngine

logging.basicConfig(level=logging.INFO)


async def main():
    engine = ScoringEngine()
    await engine.score_all()


if __name__ == "__main__":
    asyncio.run(main())
