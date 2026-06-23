"""Entity resolution service — deduplicates and unifies HCP identities."""
import asyncio
import logging
from identity.resolver import HCPResolver

logging.basicConfig(level=logging.INFO)


async def main():
    resolver = HCPResolver()
    await resolver.run()


if __name__ == "__main__":
    asyncio.run(main())
