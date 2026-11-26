import contextlib
import html
import logging
import re
from datetime import datetime
from typing import List, Optional

import httpx

from packages.contracts.base import utc_now
from packages.contracts.job import JobSourceType, RawJobPayload
from services.api.services.job_adapters.base import BaseJobSourceAdapter

logger = logging.getLogger("agentflow.adapters.remoteok")


class RemoteOKJobSourceAdapter(BaseJobSourceAdapter):
    """
    Ingests live remote technology job postings from RemoteOK (https://remoteok.com/api).
    Specializes in remote developer roles with explicit tech tags and salary bounds.
    """

    source_id = "src_remoteok_01"
    source_name = "remoteok"
    source_type = JobSourceType.FEED
    rate_limit_per_minute = 30
    base_url = "https://remoteok.com/api"

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "AgentFlow-Copilot/1.0 (https://agentflow.dev; info@agentflow.dev)",
            "Accept": "application/json",
        }

    async def is_available(self) -> bool:
        """Check if RemoteOK feed endpoint responds."""
        try:
            async with httpx.AsyncClient(timeout=3.0, headers=self.headers) as client:
                res = await client.get(self.base_url)
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
        Fetch remote jobs from the RemoteOK public JSON feed.
        Skips index 0 (legal/terms object) and converts job entries into RawJobPayload.
        """
        results: List[RawJobPayload] = []
        now = utc_now()
        query_norm = (query or "").lower().strip()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                resp = await client.get(self.base_url)
                if resp.status_code != 200:
                    logger.warning("RemoteOK API returned status %s", resp.status_code)
                    return results

                data = resp.json()
                if not isinstance(data, list):
                    return results

                # RemoteOK index 0 is typically legal terms/disclaimer
                job_items = [item for item in data if isinstance(item, dict) and "id" in item and "position" in item]

                for item in job_items:
                    position = item.get("position", "").strip()
                    company = item.get("company", "Confidential").strip()
                    tags = item.get("tags") or []
                    desc_html = item.get("description", "")
                    clean_desc = self._strip_html(desc_html) if desc_html else position
                    dest_url = item.get("apply_url") or item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}"

                    # Filter by query if specified
                    if query_norm:
                        searchable = f"{position} {company} {' '.join(tags)} {clean_desc}".lower()
                        if query_norm not in searchable:
                            continue

                    posted_at = None
                    if item.get("date"):
                        with contextlib.suppress(ValueError, TypeError):
                            posted_at = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))

                    # Extract salary string if available
                    salary_raw = None
                    sal_min = item.get("salary_min")
                    sal_max = item.get("salary_max")
                    if sal_min and sal_max:
                        salary_raw = f"${sal_min:,} - ${sal_max:,} USD"
                    elif sal_min:
                        salary_raw = f"From ${sal_min:,} USD"

                    payload = RawJobPayload(
                        source_name=self.source_name,
                        source_job_id=f"rok_{item.get('id')}",
                        source_url=item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}",
                        title=position,
                        organization=company,
                        location_raw=item.get("location") or "Remote",
                        description_raw=clean_desc,
                        description_html=desc_html,
                        salary_raw=salary_raw,
                        work_mode_raw="remote",
                        destination_url=dest_url,
                        retrieved_at=now,
                        posted_at=posted_at,
                        extra_metadata={
                            "tags": tags,
                            "salary_min": sal_min,
                            "salary_max": sal_max,
                            "remoteok_slug": item.get("slug"),
                        },
                    )
                    results.append(payload)

                    if len(results) >= limit:
                        break

        except httpx.TimeoutException:
            logger.warning("RemoteOK API call timed out after %s seconds.", self.timeout)
        except Exception as e:
            logger.warning("Error fetching RemoteOK jobs: %s", e)

        return results

    @staticmethod
    def _strip_html(html_str: str) -> str:
        """Convert HTML description to plain text cleanly."""
        unescaped = html.unescape(html_str)
        formatted = re.sub(r"<(?:br|p|div|li)[^>]*>", "\n", unescaped, flags=re.IGNORECASE)
        stripped = re.sub(r"<[^>]+>", "", formatted)
        return re.sub(r"\n\s*\n+", "\n\n", stripped).strip()
