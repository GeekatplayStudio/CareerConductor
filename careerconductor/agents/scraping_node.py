"""Scraping node: pulls postings from whitelisted official board APIs, dedupes via the DB."""
from __future__ import annotations

from careerconductor.config.settings import settings
from careerconductor.db.repository import CareerConductorDB, JobRecord, compute_job_hash
from careerconductor.scrapers import SCRAPERS_BY_BOARD_TYPE
from careerconductor.scrapers.base import PoliteClient

from .state import CareerEngineState, JobOpportunity


def run_scraping(state: CareerEngineState, db: CareerConductorDB) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    discovered: list[JobOpportunity] = []
    client = PoliteClient()

    try:
        for target in settings.whitelist_targets:
            scraper_cls = SCRAPERS_BY_BOARD_TYPE.get(target.board_type)
            if scraper_cls is None:
                logs.append(f"skip {target.company_name}: unknown board_type {target.board_type}")
                continue
            scraper = scraper_cls(client=client)
            try:
                for posting in scraper.fetch(target.company_name, target.board_token):
                    job_hash = compute_job_hash(posting.company_name, posting.job_id or posting.url)
                    if db.job_exists(job_hash):
                        continue  # idempotency: already seen, skip silently
                    db.insert_job(JobRecord(
                        job_hash=job_hash,
                        company_name=posting.company_name,
                        job_title=posting.title,
                        location=posting.location,
                        source_url=posting.url,
                        raw_payload=posting.raw_payload,
                    ))
                    discovered.append(JobOpportunity(
                        job_id=posting.job_id,
                        job_hash=job_hash,
                        title=posting.title,
                        company=posting.company_name,
                        location=posting.location,
                        source_url=posting.url,
                        raw_text=posting.raw_payload,
                    ))
                logs.append(f"{target.company_name}: {len(discovered)} new postings")
            except Exception as exc:  # noqa: BLE001 - log and continue to next target
                logs.append(f"{target.company_name}: scrape failed ({exc})")
    finally:
        client.close()

    return {
        **state,
        "discovered_jobs": state.get("discovered_jobs", []) + discovered,
        "execution_logs": logs,
    }
