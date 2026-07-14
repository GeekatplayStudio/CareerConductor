"""Greenhouse public job board API client. Docs: https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

import json
from typing import Iterator

from careerconductor.scrapers.base import BaseBoardScraper, RawJobPosting

_ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


class GreenhouseScraper(BaseBoardScraper):
    board_type = "greenhouse"

    def fetch(self, company_name: str, board_token: str) -> Iterator[RawJobPosting]:
        response = self.client.get(_ENDPOINT.format(token=board_token))
        payload = response.json()
        for job in payload.get("jobs", []):
            location = (job.get("location") or {}).get("name", "")
            yield RawJobPosting(
                company_name=company_name,
                job_id=str(job["id"]),
                title=job.get("title", ""),
                location=location,
                url=job.get("absolute_url", ""),
                raw_payload=json.dumps(job),
            )
