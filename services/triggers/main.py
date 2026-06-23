"""Trigger and buying signal detection service."""
import asyncio
import logging
from triggers.detector import TriggerDetector

logging.basicConfig(level=logging.INFO)


async def main():
    detector = TriggerDetector()
    await detector.run()


if __name__ == "__main__":
    asyncio.run(main())
