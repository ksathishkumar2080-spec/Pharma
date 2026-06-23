"""Citation verifier — validates message citations against DB records."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from anthropic import AsyncAnthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings

log = logging.getLogger(__name__)

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;)>]+", re.IGNORECASE)
_NCT_RE = re.compile(r"NCT\d{8}", re.IGNORECASE)


@dataclass
class CitationResult:
    text: str
    verified: bool
    source: str
    issue: Optional[str] = None


@dataclass
class VerificationReport:
    message_id: str
    total_claims: int
    verified: int
    unverified: int
    flagged: int
    results: list[CitationResult]
    compliant: bool
    score: float  # 0-1


class CitationVerifier:
    """Verifies that claims in outreach messages have backing evidence in DB."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._claude = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def verify_message(self, message_id: str, message_text: str) -> VerificationReport:
        claims = await self._extract_claims(message_text)
        results: list[CitationResult] = []

        for claim in claims:
            result = await self._verify_claim(claim)
            results.append(result)

        verified = sum(1 for r in results if r.verified)
        flagged = sum(1 for r in results if not r.verified and r.issue)

        total = max(len(results), 1)
        score = verified / total

        return VerificationReport(
            message_id=message_id,
            total_claims=len(results),
            verified=verified,
            unverified=total - verified,
            flagged=flagged,
            results=results,
            compliant=score >= 0.8,
            score=round(score, 3),
        )

    async def _extract_claims(self, text: str) -> list[str]:
        """Use Claude Haiku to extract verifiable factual claims from message."""
        resp = await self._claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract all verifiable factual claims from this medical outreach message. "
                        "Return one claim per line, no bullets or numbering.\n\n"
                        f"{text[:2000]}"
                    ),
                }
            ],
        )
        raw = resp.content[0].text.strip()
        return [c.strip() for c in raw.splitlines() if c.strip()]

    async def _verify_claim(self, claim: str) -> CitationResult:
        # Check for inline DOI
        doi_match = _DOI_RE.search(claim)
        if doi_match:
            doi = doi_match.group(0)
            row = await self.session.execute(
                text("SELECT id FROM publications WHERE doi = :doi LIMIT 1"),
                {"doi": doi},
            )
            if row.fetchone():
                return CitationResult(text=claim, verified=True, source="doi_match")
            return CitationResult(
                text=claim, verified=False, source="doi_not_found",
                issue=f"DOI {doi} not in publications table",
            )

        # Check for NCT ID
        nct_match = _NCT_RE.search(claim)
        if nct_match:
            nct = nct_match.group(0).upper()
            row = await self.session.execute(
                text("SELECT id FROM clinical_trials WHERE nct_id = :nct LIMIT 1"),
                {"nct": nct},
            )
            if row.fetchone():
                return CitationResult(text=claim, verified=True, source="nct_match")
            return CitationResult(
                text=claim, verified=False, source="nct_not_found",
                issue=f"{nct} not in clinical_trials table",
            )

        # Semantic similarity check against publication titles
        row = await self.session.execute(
            text("""
                SELECT title FROM publications
                WHERE title ILIKE :kw
                LIMIT 1
            """),
            {"kw": f"%{claim[:60]}%"},
        )
        if row.fetchone():
            return CitationResult(text=claim, verified=True, source="title_fuzzy")

        return CitationResult(
            text=claim,
            verified=False,
            source="unmatched",
            issue="No matching publication or trial found",
        )
