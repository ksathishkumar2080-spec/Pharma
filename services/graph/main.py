"""Knowledge graph sync — mirrors PostgreSQL entities into Neo4j."""
import asyncio
import logging
from graph.builder import GraphBuilder

logging.basicConfig(level=logging.INFO)


async def main():
    builder = GraphBuilder()
    await builder.sync()


if __name__ == "__main__":
    asyncio.run(main())
