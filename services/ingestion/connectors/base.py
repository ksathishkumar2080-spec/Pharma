from abc import ABC, abstractmethod
import logging


class BaseConnector(ABC):
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """Fetch raw records from source."""
        ...

    @abstractmethod
    async def store(self, records: list[dict]) -> None:
        """Persist records to PostgreSQL + Elasticsearch."""
        ...

    async def run(self):
        self.log.info("Starting ingestion")
        records = await self.fetch()
        self.log.info("Fetched %d records", len(records))
        await self.store(records)
        self.log.info("Ingestion complete")
