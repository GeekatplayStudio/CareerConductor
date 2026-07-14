"""Read/write helpers for the editable JSON config files (whitelist, thresholds).

Kept separate from settings.py so the UI can load and persist changes without
restarting the process — settings.py reads these at import time for the CLI path.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WHITELIST_PATH = PROJECT_ROOT / "careerconductor" / "config" / "whitelist.json"
THRESHOLDS_PATH = PROJECT_ROOT / "careerconductor" / "config" / "thresholds.json"


@dataclass
class ScrapeTarget:
    company_name: str
    board_type: str  # "greenhouse" | "lever"
    board_token: str


@dataclass
class Thresholds:
    max_friction: float = 6.0
    min_stability: float = 5.0
    min_location_fit: float = 5.0
    max_artifacts_per_run: int = 10


def load_whitelist() -> list[ScrapeTarget]:
    if not WHITELIST_PATH.exists():
        return []
    data = json.loads(WHITELIST_PATH.read_text())
    return [ScrapeTarget(**t) for t in data.get("targets", [])]


def save_whitelist(targets: list[ScrapeTarget]) -> None:
    WHITELIST_PATH.write_text(json.dumps({"targets": [asdict(t) for t in targets]}, indent=2))


def load_thresholds() -> Thresholds:
    if not THRESHOLDS_PATH.exists():
        return Thresholds()
    return Thresholds(**json.loads(THRESHOLDS_PATH.read_text()))


def save_thresholds(thresholds: Thresholds) -> None:
    THRESHOLDS_PATH.write_text(json.dumps(asdict(thresholds), indent=2))
