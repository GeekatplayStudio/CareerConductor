"""Scraping node: pulls postings from whitelisted official board APIs, dedupes via the DB."""
from __future__ import annotations

from careerconductor.config.store import load_whitelist
from careerconductor.db.repository import CareerConductorDB, JobRecord, compute_job_hash
from careerconductor.scrapers import SCRAPERS_BY_BOARD_TYPE
from careerconductor.scrapers.base import PoliteClient

from .state import CareerEngineState, JobOpportunity


def run_scraping(state: CareerEngineState, db: CareerConductorDB) -> CareerEngineState:
    logs = list(state.get("execution_logs", []))
    discovered: list[JobOpportunity] = []
    client = PoliteClient()

    try:
        for target in load_whitelist():
            scraper_cls = SCRAPERS_BY_BOARD_TYPE.get(target.board_type)
            if scraper_cls is None:
                logs.append(f"skip {target.company_name}: unknown board_type {target.board_type}")
                continue
            scraper = scraper_cls(client=client)
            new_for_target = 0
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
                    new_for_target += 1
                logs.append(f"{target.company_name}: {new_for_target} new postings")
            except Exception as exc:  # noqa: BLE001 - log and continue to next target
                logs.append(f"{target.company_name}: scrape failed ({exc})")
    finally:
        client.close()

    # Second chance for jobs scraped in an EARLIER run whose analysis failed
    # (transient API error, malformed response). They sit in the DB with status
    # 'discovered'; without this re-queue the hash dedup above would skip them
    # forever and they'd never be scored. Idempotent: once analysis succeeds,
    # their status flips to 'analyzed' and they stop matching.
    already_queued = {j["job_hash"] for j in discovered}
    requeued = 0
    for row in db.unanalyzed_jobs():
        if row["job_hash"] in already_queued:
            continue
        discovered.append(JobOpportunity(
            job_id="",
            job_hash=row["job_hash"],
            title=row["job_title"],
            company=row["company_name"],
            location=row["location"] or "",
            source_url=row["source_url"] or "",
            raw_text=row["raw_payload"] or "",
        ))
        requeued += 1
    if requeued:
        logs.append(f"requeued {requeued} previously scraped but never-analyzed job(s)")

    return {
        **state,
        "discovered_jobs": state.get("discovered_jobs", []) + discovered,
        "execution_logs": logs,
    }
