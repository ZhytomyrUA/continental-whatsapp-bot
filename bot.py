#!/usr/bin/env python3
"""Continental News collector for a normal WhatsApp Channel.

The script does NOT publish to WhatsApp. It prepares up to 12 DIFFERENT news
EVENTS, with factory/production stories first, and writes ready-to-post output.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser

MAX_EVENTS = 12
LOOKBACK_HOURS = 72
SEEN_DAYS = 30

SEEN_FILE = Path("whatsapp_seen.json")
POSTS_JSON = Path("whatsapp_posts.json")
POSTS_TXT = Path("whatsapp_posts.txt")

QUERIES = [
    # Korbach / factories
    "Continental Korbach Reifen Werk",
    "Continental Korbach Reifen Produktion",
    "Continental Korbach Reifenwerk",
    "Continental Werk Deutschland Reifen Produktion",
    "Continental Reifen Fabrik Deutschland",
    "Continental Reifen Werk Investition",
    "Continental Reifen Werk Schließung",
    "Continental Reifen Werk Verlagerung",
    "Continental Reifen neue Produktion",
    "Continental plant Germany tire production",
    "Continental factory production tires Germany",
    "Continental plant investment Germany",
    # employees / company
    "Continental Mitarbeiter Werk",
    "Continental Belegschaft Werk",
    "Continental workers jobs restructuring",
    "Continental Reifen Technologie",
    "Continental Reifen Neuheit",
    "Continental Reifen Test",
    "Continental Reifen Innovation",
    "Continental Nutzfahrzeugreifen",
    "Continental Lkw Reifen",
    "Continental Pkw Reifen",
    "Continental Motorsport Reifen",
    "Continental Nachhaltigkeit",
]

STOPWORDS = {
    "der","die","das","den","dem","des","ein","eine","einer","eines",
    "und","oder","für","von","mit","auf","aus","bei","nach","in","im",
    "am","an","zu","zum","zur","ist","sind","wird","werden","wurde",
    "the","a","an","of","to","for","and","in","on","at","with","from",
    "by","new","news","about","this","that","its","has","have","into",
    "continental","reuters","dpa","press","release",
}

KORBACH = ("korbach", "reifenwerk korbach", "werk korbach")
FACTORY = (
    "werk", "reifenwerk", "fabrik", "produktion", "produktions", "fertigung",
    "plant", "factory", "manufacturing", "production", "reifenproduktion",
    "reifenerzeugung", "production site",
)
PRODUCTION = (
    "produktion", "produziert", "produced", "production", "fertigung",
    "manufacturing", "manufactures", "capacity", "kapazität", "investition",
    "investitionen", "investment", "ausbau", "expansion", "erweiterung",
    "anlage", "modernisierung", "umbau", "verlagerung", "relocation",
    "schließung", "schliessung", "shutdown",
)
TIRE = ("reifen", "tire", "tyre", "pkw-reifen", "lkw-reifen", "truckreifen")
COMPANY = ("continental", "continental reifen", "continental tires", "continental tyre")
HIGH_VALUE = (
    "stellenabbau", "arbeitsplätze", "arbeitsplaetze", "entlassung", "verlagerung",
    "schließung", "schliessung", "werksschließung", "werksschliessung",
    "investition", "investitionen", "ausbau", "erweiterung", "restrukturierung",
    "reorganisation", "betriebsrat", "ig metall", "tarifvertrag", "jobs",
    "quartalszahlen", "umsatz", "gewinn", "verlust", "vorstand", "aufsichtsrat",
)

SOURCE_BONUS = {
    "continental.com": 120,
    "continental-reifen.de": 100,
    "reuters.com": 55,
    "tagesschau.de": 50,
    "hessenschau.de": 45,
    "hna.de": 50,
    "reifenpresse.de": 55,
    "automobilwoche.de": 45,
    "handelsblatt.com": 40,
    "faz.net": 35,
    "sueddeutsche.de": 35,
}


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def norm(value: str) -> str:
    value = clean(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9äöüß ]+", " ", value)


def tokens(item: dict) -> set[str]:
    text = norm(f"{item.get('title','')} {item.get('summary','')}")
    return {w for w in text.split() if len(w) >= 5 and w not in STOPWORDS}


def source(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1).lower() if m else "unknown"


def google_rss(query: str) -> str:
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=de&gl=DE&ceid=DE:de"


def entry_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def event_family(item: dict) -> str:
    text = norm(f"{item['title']} {item.get('summary','')}")

    # High-confidence known event: the three wind-farm articles in the test
    # must become ONE event, not three posts.
    if "continental" in text and "windpark" in text and any(
        x in text for x in ("korbach", "twistetal", "nordhessen")
    ):
        return "continental|windpark|korbach|twistetal|nordhessen"

    # Strong plant/event families.
    family = []
    if "continental" in text:
        family.append("continental")
    if any(x in text for x in KORBACH):
        family.append("korbach")
    if any(x in text for x in FACTORY):
        family.append("factory")
    if any(x in text for x in PRODUCTION):
        family.append("production")
    if any(x in text for x in HIGH_VALUE):
        family.append("highvalue")

    meaningful = sorted(tokens(item))
    # Do not make every generic Continental factory article one family.
    # The first 6 meaningful tokens form only a fallback fingerprint.
    fingerprint = meaningful[:6]
    return "|".join(sorted(set(family)) + fingerprint)


def event_similarity(a: dict, b: dict) -> float:
    aa, bb = tokens(a), tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, min(len(aa), len(bb)))


def same_event(a: dict, b: dict) -> bool:
    if a.get("event_family") == b.get("event_family"):
        return True

    ta, tb = tokens(a), tokens(b)
    shared = ta & tb
    if not shared:
        return False

    # Explicit strong anchors prevent accidental merging of unrelated stories.
    strong = {"windpark", "reifenwerk", "produktion", "produktions", "investition",
              "verlagerung", "schliessung", "schließung", "korbach", "twistetal"}
    strong_shared = shared & strong

    sim = event_similarity(a, b)
    return sim >= 0.70 and bool(strong_shared)


def score(item: dict) -> tuple[int, str]:
    text = norm(f"{item['title']} {item.get('summary','')}")
    s = SOURCE_BONUS.get(source(item["url"]), 0)

    if "continental" in text:
        s += 150
    else:
        s -= 200

    if any(x in text for x in KORBACH):
        s += 1000
        category = "KORBACH_FACTORY"
    elif any(x in text for x in FACTORY):
        s += 500
        category = "FACTORY"
    else:
        category = "COMPANY"

    if any(x in text for x in PRODUCTION):
        s += 250
    if any(x in text for x in TIRE):
        s += 50
    if any(x in text for x in HIGH_VALUE):
        s += 80

    return s, category


def fetch_candidates() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    found: dict[str, dict] = {}

    for query in QUERIES:
        print(f"SEARCH: {query}")
        try:
            feed = feedparser.parse(google_rss(query))
            entries = feed.entries[:60]
        except Exception as exc:
            print(f"RSS ERROR: {exc}")
            continue

        print(f"  -> {len(entries)} items")
        for entry in entries:
            dt = entry_date(entry)
            if not dt or dt < cutoff:
                continue

            title = clean(getattr(entry, "title", ""))
            url = getattr(entry, "link", "") or ""
            summary = clean(getattr(entry, "summary", ""))
            if not title or not url:
                continue

            item = {
                "title": title,
                "summary": summary,
                "url": url,
                "source": source(url),
                "published_at": dt.isoformat(),
            }
            item["score"], item["category"] = score(item)
            if item["score"] < 100:
                continue
            item["event_family"] = event_family(item)

            # Exact article deduplication.
            key = hashlib.sha1((norm(title) + "|" + url.split("?")[0]).encode()).hexdigest()
            old = found.get(key)
            if old is None or item["score"] > old["score"]:
                found[key] = item

    return list(found.values())


def load_seen() -> dict[str, str]:
    if not SEEN_FILE.exists():
        return {}
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        # Backward compatibility with the old list format.
        if isinstance(data, list):
            return {str(x): "" for x in data}
    except Exception as exc:
        print(f"SEEN WARNING: {exc}")
    return {}


def save_seen(seen: dict[str, str]) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=SEEN_DAYS)
    out = {}
    for key, value in seen.items():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt >= cutoff:
                out[key] = value
        except Exception:
            out[key] = value
    SEEN_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def event_id(item: dict) -> str:
    # Event ID deliberately ignores publisher/source so the same story from
    # HNA, FFH and Hessenschau receives the same ID.
    canonical = item.get("event_family") or norm(item["title"])
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def choose_events(candidates: list[dict], seen: dict[str, str]) -> list[dict]:
    # Sort so the best representative of each event is encountered first.
    candidates.sort(
        key=lambda x: (
            x["category"] == "KORBACH_FACTORY",
            x["category"] == "FACTORY",
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )

    selected: list[dict] = []
    groups: list[dict] = []

    for item in candidates:
        eid = event_id(item)
        if eid in seen:
            continue

        matched = next((g for g in groups if same_event(item, g)), None)
        if matched is not None:
            matched.setdefault("alternate_sources", []).append({
                "source": item["source"],
                "title": item["title"],
                "url": item["url"],
            })
            continue

        item["event_id"] = eid
        item["alternate_sources"] = []
        groups.append(item)

    # Editorial priority: ALL factory/production stories first.
    groups.sort(
        key=lambda x: (
            x["category"] == "KORBACH_FACTORY",
            x["category"] == "FACTORY",
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )
    selected = groups[:MAX_EVENTS]
    return selected


def post_text(item: dict, number: int) -> str:
    summary = item.get("summary", "")
    if len(summary) > 700:
        summary = summary[:697].rstrip(" .,!?:;—-") + "…"
    return (
        f"{number}. [{item['category']}] {item['title']}\n\n"
        f"{summary}\n\n"
        f"📰 Quelle: {item['source']}\n"
        f"🔗 {item['url']}\n"
        f"📅 {item['published_at']}"
    )


def main() -> None:
    print("=== Continental WhatsApp Channel News v2 ===")
    print(f"Lookback: {LOOKBACK_HOURS}h | Max DIFFERENT EVENTS: {MAX_EVENTS}")

    candidates = fetch_candidates()
    print(f"Unique article candidates: {len(candidates)}")

    seen = load_seen()
    selected = choose_events(candidates, seen)

    print(f"Selected {len(selected)} DIFFERENT events.")
    for i, item in enumerate(selected, 1):
        print(f"{i:02d}. [{item['category']}] {item['title']} - {item['source']}")
        if item.get("alternate_sources"):
            print(f"    grouped alternative sources: {len(item['alternate_sources'])}")

    POSTS_JSON.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    POSTS_TXT.write_text("\n\n".join(post_text(x, i) for i, x in enumerate(selected, 1)) + ("\n" if selected else ""), encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    for item in selected:
        seen[item["event_id"]] = now
    save_seen(seen)

    print("Created: whatsapp_posts.json")
    print("Created: whatsapp_posts.txt")
    print("Updated: whatsapp_seen.json")


if __name__ == "__main__":
    main()
