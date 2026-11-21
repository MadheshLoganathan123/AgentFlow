import html
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from packages.contracts.base import utc_now
from packages.contracts.job import JobSourceType, RawJobPayload
from services.api.services.job_adapters.base import BaseJobSourceAdapter

logger = logging.getLogger("agentflow.adapters.greenhouse")

# Default public tech companies using Greenhouse ATS boards
DEFAULT_GREENHOUSE_BOARDS = ["cloudflare", "canonical", "elastic"]


class GreenhouseJobSourceAdapter(BaseJobSourceAdapter):
    """
    Ingests live public job postings directly from Greenhouse ATS boards
    via the public Greenhouse Boards API (https://boards-api.greenhouse.io).
    """

    source_id = "src_greenhouse_01"
    source_name = "greenhouse"
    source_type = JobSourceType.API
    rate_limit_per_minute = 60
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        boards: Optional[List[str]] = None,
        timeout: float = 8.0,
    ):
        self.boards = boards or DEFAULT_GREENHOUSE_BOARDS
        self.timeout = timeout

    async def is_available(self) -> bool:
        """Check if Greenhouse public board API responds."""
        test_board = self.boards[0] if self.boards else "cloudflare"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/{test_board}")
                return res.status_code == 200
        except Exception:
            return False

    async def fetch_raw_jobs(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[RawJobPayload]:
        """
        Fetch public jobs across configured Greenhouse boards.
        Extracts title, location, html/plain text content, and application URL.
        """
        results: List[RawJobPayload] = []
        now = utc_now()
        query_norm = (query or "").lower().strip()
        loc_norm = (location or "").lower().strip()

        for board in self.boards:
            if len(results) >= limit:
                break

            board_url = f"{self.base_url}/{board}/jobs?content=true"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(board_url)
                    if resp.status_code != 200:
                        logger.warning(
                            "Greenhouse board '%s' returned status %s: %s",
                            board,
                            resp.status_code,
                            resp.text[:100],
                        )
                        continue

                    data = resp.json()
                    jobs_list = data.get("jobs", [])

                    for item in jobs_list:
                        title = item.get("title", "").strip()
                        raw_loc = (item.get("location") or {}).get("name", "Unspecified").strip()
                        content_html = item.get("content", "")
                        dest_url = item.get("absolute_url", f"https://boards.greenhouse.io/{board}/jobs/{item.get('id')}")

                        # Strip HTML tags to produce clean raw text
                        clean_text = self._strip_html(content_html) if content_html else title

                        # Query filtering
                        if query_norm:
                            searchable = f"{title} {clean_text} {board}".lower()
                            if query_norm not in searchable:
                                continue

                        if loc_norm:
                            if loc_norm not in raw_loc.lower():
                                continue

                        posted_at = None
                        if item.get("updated_at"):
                            try:
                                posted_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                            except (ValueError, TypeError):
                                pass

                        raw_payload = RawJobPayload(
                            source_name=self.source_name,
                            source_job_id=f"gh_{board}_{item.get('id')}",
                            source_url=f"{self.base_url}/{board}/jobs/{item.get('id')}",
                            title=title,
                            organization=board.replace("-", " ").title(),
                            location_raw=raw_loc,
                            description_raw=clean_text,
                            description_html=content_html,
                            destination_url=dest_url,
                            retrieved_at=now,
                            posted_at=posted_at,
                            extra_metadata={
                                "greenhouse_board": board,
                                "departments": [d.get("name") for d in item.get("departments", []) if d.get("name")],
                                "offices": [o.get("name") for o in item.get("offices", []) if o.get("name")],
                            },
                        )
                        results.append(raw_payload)

                        if len(results) >= limit:
                            break

            except httpx.TimeoutException:
                logger.warning("Greenhouse request for board '%s' timed out.", board)
                continue
            except Exception as e:
                logger.warning("Greenhouse ingestion error on board '%s': %s", board, e)
                continue

        return results

    @staticmethod
    def _strip_html(html_str: str) -> str:
        """Convert HTML description to plain text cleanly without native C dependencies."""
        unescaped = html.unescape(html_str)
        # Replace breaks and paragraphs with newlines
        formatted = re.sub(r"<(?:br|p|div|li)[^>]*>", "\n", unescaped, flags=re.IGNORECASE)
        # Strip all remaining tags
        stripped = re.sub(r"<[^>]+>", "", formatted)
        # Normalize excessive newlines
        return re.sub(r"\n\s*\n+", "\n\n", stripped).strip()
