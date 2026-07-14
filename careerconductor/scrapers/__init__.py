from careerconductor.scrapers.greenhouse import GreenhouseScraper
from careerconductor.scrapers.lever import LeverScraper

SCRAPERS_BY_BOARD_TYPE = {
    "greenhouse": GreenhouseScraper,
    "lever": LeverScraper,
}

__all__ = ["GreenhouseScraper", "LeverScraper", "SCRAPERS_BY_BOARD_TYPE"]
