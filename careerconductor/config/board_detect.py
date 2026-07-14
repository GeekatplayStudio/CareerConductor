"""Turn a pasted careers-page URL into a verified ScrapeTarget.

WHY: users shouldn't need to know what a "board token" is. They paste the URL
they see in their browser; we recognize the hosting platform from the URL shape,
extract the token, and then VERIFY it by calling the platform's official public
API once. Verification catches typos and wrong-platform pastes immediately, at
add time — not silently during the next scheduled scrape.

Supported patterns (the token is the <slug> segment):
  Greenhouse: boards.greenhouse.io/<slug>          (careers page)
              job-boards.greenhouse.io/<slug>      (newer hosted pages)
              boards.greenhouse.io/embed/job_board?for=<slug>
  Lever:      jobs.lever.co/<slug>
              jobs.eu.lever.co/<slug>
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from careerconductor.config.store import ScrapeTarget
from careerconductor.scrapers import SCRAPERS_BY_BOARD_TYPE
from careerconductor.scrapers.base import PoliteClient


@dataclass
class VerifyResult:
    ok: bool
    message: str
    target: ScrapeTarget | None = None
    job_count: int = 0


def detect_target(url: str) -> ScrapeTarget | None:
    """Recognize the board platform and token from a careers URL. None if unsupported."""
    parsed = urlparse(url.strip() if "://" in url else f"https://{url.strip()}")
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if host.endswith("greenhouse.io"):
        # embed form: /embed/job_board?for=<token>
        if path_parts and path_parts[0] == "embed":
            token = parse_qs(parsed.query).get("for", [None])[0]
        else:
            token = path_parts[0] if path_parts else None
        if token:
            return ScrapeTarget(company_name=_prettify(token), board_type="greenhouse", board_token=token)

    if host.endswith("lever.co"):
        token = path_parts[0] if path_parts else None
        if token:
            return ScrapeTarget(company_name=_prettify(token), board_type="lever", board_token=token)

    return None


def _prettify(token: str) -> str:
    """Best-effort company name from a URL slug ('acme-robotics' -> 'Acme Robotics')."""
    return re.sub(r"[-_]+", " ", token).strip().title()


def verify_target(target: ScrapeTarget) -> VerifyResult:
    """Hit the official public API once to prove the token is real and has postings.

    Reuses the same scraper classes the pipeline uses, so 'verified here' means
    'will work in the pipeline' — no separate code path that could drift.
    """
    scraper_cls = SCRAPERS_BY_BOARD_TYPE.get(target.board_type)
    if scraper_cls is None:
        return VerifyResult(ok=False, message=f"Unsupported board type: {target.board_type}")

    client = PoliteClient()
    try:
        postings = list(scraper_cls(client=client).fetch(target.company_name, target.board_token))
        return VerifyResult(
            ok=True,
            message=f"Verified: {len(postings)} live posting(s) on {target.board_type}.",
            target=target,
            job_count=len(postings),
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure as a user-readable message
        return VerifyResult(
            ok=False,
            message=f"Could not verify '{target.board_token}' on {target.board_type}: {exc}",
            target=target,
        )
    finally:
        client.close()
