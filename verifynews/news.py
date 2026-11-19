"""Current headline providers and feed loading."""
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

from .config import CURRENT_NEWS_PATH

@st.cache_data(ttl=900, show_spinner=False)
def load_current_news(country="in", category="general"):
    """Load current headlines from NewsAPI, a Jenkins snapshot, or free RSS."""
    api_key = os.getenv("NEWS_API_KEY", "").strip()
    if not api_key:
        try:
            api_key = str(st.secrets.get("NEWS_API_KEY", "")).strip()
        except Exception:
            api_key = ""

    if api_key:
        query = urlencode({"country": country.lower(), "category": category, "pageSize": 12})
        request = Request(
            f"https://newsapi.org/v2/top-headlines?{query}",
            headers={"X-Api-Key": api_key, "User-Agent": "VerifyNews/1.0"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") != "ok":
                raise RuntimeError(payload.get("message", "News provider returned an error."))
            articles = payload.get("articles", [])
            updated_at = pd.Timestamp.now(tz="UTC").isoformat()
            provider = "NewsAPI"
        except Exception:
            articles, updated_at = _fetch_google_news_rss(country)
            provider = "Google News RSS fallback"
    elif CURRENT_NEWS_PATH.exists():
        payload = json.loads(CURRENT_NEWS_PATH.read_text(encoding="utf-8"))
        articles = payload.get("articles", [])
        updated_at = payload.get("updated_at", "")
        provider = payload.get("provider", "Jenkins news snapshot")
    else:
        articles, updated_at = _fetch_google_news_rss(country)
        provider = "Google News RSS"

    articles = [article for article in articles if article.get("title") and article.get("url")]
    articles.sort(key=lambda article: article.get("publishedAt", ""), reverse=True)
    return {"articles": articles[:12], "updated_at": updated_at, "provider": provider, "configured": True}

def _fetch_google_news_rss(country="in"):
    """Retrieve current headlines from a public, keyless Google News RSS feed."""
    locales = {
        "in": ("en-IN", "IN", "IN:en"), "us": ("en-US", "US", "US:en"),
        "gb": ("en-GB", "GB", "GB:en"), "ca": ("en-CA", "CA", "CA:en"),
        "au": ("en-AU", "AU", "AU:en"),
    }
    language, region, edition = locales.get(country.lower(), locales["in"])
    query = urlencode({"hl": language, "gl": region, "ceid": edition})
    request = Request(f"https://news.google.com/rss?{query}", headers={"User-Agent": "VerifyNews/1.0"})
    with urlopen(request, timeout=12) as response:
        root = ET.fromstring(response.read())
    articles = []
    for item in root.findall("./channel/item")[:12]:
        title = item.findtext("title", "").strip()
        source_element = item.find("source")
        source_name = source_element.text.strip() if source_element is not None and source_element.text else "Google News"
        published = item.findtext("pubDate", "")
        try:
            published = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            published = ""
        description = item.findtext("description", "")
        description = html.unescape(re.sub(r"<[^>]+>", " ", description)).strip()
        articles.append({
            "source": {"name": source_name}, "title": title,
            "description": description, "url": item.findtext("link", "").strip(),
            "publishedAt": published,
        })
    return articles, pd.Timestamp.now(tz="UTC").isoformat()
