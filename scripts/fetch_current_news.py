"""Fetch a small current-headlines snapshot using a NewsAPI secret."""

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


def fetch(country: str, category: str, api_key: str) -> dict:
    if api_key:
        query = urlencode({"country": country, "category": category, "pageSize": 12})
        request = Request(
            f"https://newsapi.org/v2/top-headlines?{query}",
            headers={"X-Api-Key": api_key, "User-Agent": "VerifyNews-Jenkins/1.0"},
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") != "ok":
            raise RuntimeError(payload.get("message", "News provider returned an error."))
        articles = [
            {
                "source": item.get("source") or {}, "title": item.get("title"),
                "description": item.get("description"), "url": item.get("url"),
                "urlToImage": item.get("urlToImage"), "publishedAt": item.get("publishedAt"),
            }
            for item in payload.get("articles", []) if item.get("title") and item.get("url")
        ]
        provider = "NewsAPI"
    else:
        locales = {
            "in": ("en-IN", "IN", "IN:en"), "us": ("en-US", "US", "US:en"),
            "gb": ("en-GB", "GB", "GB:en"), "ca": ("en-CA", "CA", "CA:en"),
            "au": ("en-AU", "AU", "AU:en"),
        }
        language, region, edition = locales.get(country, locales["in"])
        query = urlencode({"hl": language, "gl": region, "ceid": edition})
        request = Request(f"https://news.google.com/rss?{query}", headers={"User-Agent": "VerifyNews-Jenkins/1.0"})
        with urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
        articles = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            if not title or not link:
                continue
            source_element = item.find("source")
            source_name = source_element.text.strip() if source_element is not None and source_element.text else "Google News"
            published = item.findtext("pubDate", "")
            try:
                published = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                published = ""
            description = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description", ""))).strip()
            articles.append({
                "source": {"name": source_name}, "title": title, "description": description,
                "url": link, "publishedAt": published,
            })
        provider = "Google News RSS"
    articles.sort(key=lambda article: article.get("publishedAt") or "", reverse=True)
    return {
        "provider": provider,
        "country": country,
        "category": category,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": articles[:12],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default="in", help="Two-letter NewsAPI country code")
    parser.add_argument("--category", default="general")
    parser.add_argument("--output", default="datasets/current_news.json")
    args = parser.parse_args()
    api_key = os.getenv("NEWS_API_KEY", "").strip()
    try:
        payload = fetch(args.country.lower(), args.category, api_key)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
        print(f"Updated {output} with {len(payload['articles'])} {payload['provider']} headlines ({args.country.upper()}/{args.category}).")
        return 0
    except Exception as error:
        print(f"Headline refresh failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
