"""Lever public postings API client. Docs: https://github.com/lever/postings-api"""
from __future__ import annotations

import json
from typing import Iterator

from careerconductor.scrapers.base import BaseBoardScraper, RawJobPosting

_ENDPOINT = "https://api.lever.co/v0/postings/{token}?mode=json"


class LeverScraper(BaseBoardScraper):
    board_type = "lever"

    def fetch(self, company_name: str, board_token: str) -> Iterator[RawJobPosting]:
        response = self.client.get(_ENDPOINT.format(token=board_token))
        postings = response.json()
        for job in postings:
            categories = job.get("categories", {})
            location = categories.get("location", "")
            yield RawJobPosting(
                company_name=company_name,
                job_id=str(job["id"]),
                title=job.get("text", ""),
                location=location,
                url=job.get("hostedUrl", ""),
                raw_payload=json.dumps(job),
            )
