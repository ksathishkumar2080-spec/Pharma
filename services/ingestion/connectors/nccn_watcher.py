"""NCCN guideline change watcher — detects updates and diffs guideline versions."""
import hashlib
import httpx
from playwright.async_api import async_playwright
from ingestion.connectors.base import BaseConnector
from shared.db import get_session_factory
from sqlalchemy import text
import uuid
from datetime import datetime, timezone

NCCN_GUIDELINES_URL = "https://www.nccn.org/guidelines/category_1"


class NCCNWatcher(BaseConnector):
    """Polls NCCN guidelines page and fires trigger events when content changes."""

    async def fetch(self) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(NCCN_GUIDELINES_URL, wait_until="networkidle", timeout=30000)
            try:
                await page.wait_for_selector(".guideline-item, .nccn-guideline, tr", timeout=10000)
                items = await page.query_selector_all(".guideline-item, .nccn-guideline, tr")
                for item in items:
                    name_el = await item.query_selector("td:first-child, .guideline-name, a")
                    version_el = await item.query_selector(".version, .guideline-version, td:nth-child(2)")
                    date_el = await item.query_selector(".update-date, td:nth-child(3)")
                    name = (await name_el.inner_text()).strip() if name_el else ""
                    version = (await version_el.inner_text()).strip() if version_el else ""
                    update_date = (await date_el.inner_text()).strip() if date_el else ""
                    if name and len(name) > 3:
                        records.append({
                            "source": "NCCN",
                            "guideline": name,
                            "version": version,
                            "update_date": update_date,
                            "content_hash": hashlib.sha256(f"{name}{version}".encode()).hexdigest(),
                        })
            except Exception as e:
                self.log.warning("NCCN parse error: %s", e)
            finally:
                await browser.close()
        return records

    async def store(self, records: list[dict]) -> None:
        from shared.db import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            for rec in records:
                # Check if this guideline version is already known
                existing = (await session.execute(
                    text("SELECT id FROM trigger_events WHERE event_type = 'guideline_update' AND event_data->>'content_hash' = :hash"),
                    {"hash": rec["content_hash"]},
                )).fetchone()
                if not existing:
                    self.log.info("New NCCN guideline version detected: %s %s", rec["guideline"], rec["version"])
                    await session.execute(
                        text("""
                            INSERT INTO trigger_events (id, event_type, event_data, source, occurred_at)
                            VALUES (:id, 'guideline_update', :data, 'nccn', :now)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "data": str(rec),
                            "now": datetime.now(timezone.utc),
                        },
                    )
            await session.commit()
