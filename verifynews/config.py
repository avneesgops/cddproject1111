"""Shared paths and app constants."""
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MIN_ARTICLE_CHARS = 80
CACHE_DIR = BASE_DIR / ".verifynews_cache"
CURRENT_NEWS_PATH = BASE_DIR / "datasets" / "current_news.json"
BRAND_MARK_PATH = BASE_DIR / "assets" / "verifynews-mark.svg"
BRAND_MARK_SVG = BRAND_MARK_PATH.read_text(encoding="utf-8").strip()
BRAND_MARK_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(BRAND_MARK_SVG.encode("utf-8")).decode("ascii")
CASE_DB_PATH = BASE_DIR / "data" / "verifynews_cases.sqlite3"
CASE_STATUSES = ["New", "Assigned for review", "Evidence found", "Needs follow-up", "Closed"]
