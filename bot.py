#!/usr/bin/env python3
"""
Continental WhatsApp Channel News Bot
v1.0.0

Purpose:
- Collect current Continental news from public RSS/Google News feeds.
- Put factory/production news first, with Korbach given the highest priority.
- Do NOT use machine translation (avoids Google Translate rate limits).
- Create ready-to-post WhatsApp Channel text files.
- This version intentionally does NOT automate WhatsApp Web login/posting.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests

MAX_POSTS = 12
LOOKBACK_HOURS = 72
TIMEOUT = 20
STATE_FILE = Path("whatsapp_seen.json")
OUTPUT_JSON = Path("whatsapp_posts.json")
OUTPUT_TXT = Path("whatsapp_posts.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ContinentalWhatsAppNewsBot/1.0)"
}

# Factory/production searches are deliberately first.
QUERIES = [
    "Continental Korbach Reifen Werk Produktion",
    "Continental Korbach factory plant production",
    "Continental Reifen Deutschland Werk Produktion",
    "Continental tire plant production Germany",
    "Continental factory production tires",
    "Continental Reifen Werk news",
    "Continental tires news",
]

KORBACH_TERMS = [
    "korbach", "korbachs", "reifenwerk korbach", "werk korbach",
]

FACTORY_TERMS = [
    "werk", "fabrik", "produktion", "produktions", "fertigung",
    "plant", "factory", "manufacturing", "production",
    "reifenerzeugung", "reifenproduktion", "production site",
]

CONTINENTAL_TERMS = [
    "continental", "continental tires", "continental tyre",
    "continental reifen",
]

PRODUCTION_TERMS = [
    "produziert", "produktion", "fertigt", "fertigung",
    "produced", "production", "manufacturing", "manufactures",
    "capacity", "kapazität", "anlage", "investment", "investition",
]

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def parse_date(entry) -> datetime:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return now_utc()

def clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def normalize(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^a-z0-9äöüß]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def event_key(title: str, summary: str) -> str:
    text = normalize(title + " " + summary)
    # Remove common boilerplate so duplicate articles about the same event
    # are more likely to collapse to one item.
    text = re.sub(r"\b(continental|reuters|dpa|press release|news)\b", "", text)
    words = text.split()
    key_text = " ".join(words[:28])
    return hashlib.sha1(key_text.encode("utf-8")).hexdigest()

def score_item(title: str, summary: str) -> tuple[int, str]:
    text = normalize(title + " " + summary)
    score = 0
    category = "COMPANY"

    if any(term in text for term in KORBACH_TERMS):
        score += 1000
        category = "KORBACH_FACTORY"

    if any(term in text for term in FACTORY_TERMS):
        score += 500
        category = "FACTORY"

    if any(term in text for term in PRODUCTION_TERMS):
        score += 250

    if any(term in text for term in CONTINENTAL_TERMS):
        score += 150
    else:
        # Google News can occasionally return a weakly related result.
        score -= 200

    if "reifen" in text or "tire" in text or "tyre" in text:
        score += 50

    return score, category

def make_feed_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=de&gl=DE&ceid=DE:de"
    )

def fetch_feed(query: str) -> list[dict]:
    url = make_feed_url(query)
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    result = []
    for entry in feed.entries:
        title = clean_html(entry.get("title", ""))
        link = entry.get("link", "").strip()
        summary = clean_html(entry.get("summary", ""))
        if not title or not link:
            continue

        published_at = parse_date(entry)
        age_hours = (now_utc() - published_at).total_seconds() / 3600
        if age_hours > LOOKBACK_HOURS:
            continue

        score, category = score_item(title, summary)
        result.append({
            "title": title,
            "link": link,
            "summary": summary[:700],
            "published_at": published_at.isoformat(),
            "score": score,
            "category": category,
            "event_key": event_key(title, summary),
            "source_query": query,
        })
    return result

def load_seen() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except Exception:
        return set()

def save_seen(seen: set[str]) -> None:
    # Keep the state bounded.
    values = list(seen)[-2000:]
    STATE_FILE.write_text(
        json.dumps(values, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def choose_items(items: list[dict], seen: set[str]) -> list[dict]:
    # Deduplicate by event, then rank.
    unique = {}
    for item in items:
        key = item["event_key"]
        current = unique.get(key)
        if current is None or item["score"] > current["score"]:
            unique[key] = item

    candidates = [x for x in unique.values() if x["event_key"] not in seen]
    candidates.sort(
        key=lambda x: (
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )

    # Never allow lower-priority categories to displace factory news.
    factory = [
        x for x in candidates
        if x["category"] in {"KORBACH_FACTORY", "FACTORY"}
    ]
    other = [
        x for x in candidates
        if x["category"] not in {"KORBACH_FACTORY", "FACTORY"}
    ]

    selected = (factory + other)[:MAX_POSTS]
    return selected

def format_post(item: dict, number: int) -> str:
    published = item["published_at"].replace("T", " ").replace("+00:00", " UTC")
    label = {
        "KORBACH_FACTORY": "🏭 KORBACH / WERK",
        "FACTORY": "🏭 CONTINENTAL WERK",
    }.get(item["category"], "📰 CONTINENTAL")

    summary = item["summary"].strip()
    if len(summary) > 420:
        summary = summary[:417].rsplit(" ", 1)[0] + "…"

    parts = [
        f"{label}",
        "",
        item["title"],
    ]

    if summary:
        parts += ["", summary]

    parts += [
        "",
        f"🔗 {item['link']}",
        f"🕒 {published}",
    ]

    return "\n".join(parts)

def main() -> None:
    seen = load_seen()
    all_items = []

    for query in QUERIES:
        try:
            batch = fetch_feed(query)
            all_items.extend(batch)
            print(f"OK: {query} -> {len(batch)} items")
        except Exception as exc:
            print(f"WARNING: {query}: {exc}")

    selected = choose_items(all_items, seen)

    posts = []
    for idx, item in enumerate(selected, start=1):
        post_text = format_post(item, idx)
        posts.append({
            "number": idx,
            "title": item["title"],
            "category": item["category"],
            "score": item["score"],
            "published_at": item["published_at"],
            "source_query": item["source_query"],
            "url": item["link"],
            "text": post_text,
        })
        seen.add(item["event_key"])

    OUTPUT_JSON.write_text(
        json.dumps(
            {
                "generated_at": now_utc().isoformat(),
                "count": len(posts),
                "posts": posts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    OUTPUT_TXT.write_text(
        "\n\n" + ("\n\n" + ("=" * 70) + "\n\n").join(
            p["text"] for p in posts
        ) if posts else "No new posts.",
        encoding="utf-8",
    )

    save_seen(seen)

    print(f"Selected {len(posts)} new posts.")
    for post in posts:
        print(f"{post['number']:02d}. [{post['category']}] {post['title']}")

if __name__ == "__main__":
    main()
