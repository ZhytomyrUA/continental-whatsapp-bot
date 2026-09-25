import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import requests

MAX_POSTS = 12
LOOKBACK_HOURS = 72
TIMEOUT = 20

SEARCH_QUERIES = [
    "Continental Korbach Reifen Werk",
    "Continental Korbach Reifen Produktion",
    "Continental Werk Deutschland Reifen Produktion",
    "Continental Reifen Fabrik Deutschland",
    "Continental Reifen Investition Werk",
    "Continental Reifen neue Produktion",
    "Continental Reifen Werk news",
    "Continental factory production tires Germany",
    "Continental plant Germany tire production",
    "Continental tires news",
]

KORBACH_TERMS = (
    "korbach",
    "korbachs",
    "reifenwerk korbach",
    "werk korbach",
)
FACTORY_TERMS = (
    "werk",
    "fabrik",
    "produktion",
    "produktions",
    "fertigung",
    "plant",
    "factory",
    "manufacturing",
    "production",
    "reifenerzeugung",
    "reifenproduktion",
    "production site",
)
PRODUCTION_TERMS = (
    "produziert",
    "produktion",
    "fertigt",
    "fertigung",
    "produced",
    "production",
    "manufacturing",
    "manufactures",
    "capacity",
    "kapazität",
    "anlage",
    "investment",
    "investition",
)
TIRE_TERMS = (
    "reifen",
    "reifenwerk",
    "tire",
    "tires",
    "tyre",
    "tyres",
)

GENERIC_WORDS = {
    "continental", "reuters", "dpa", "press", "release", "news",
    "für", "den", "die", "das", "der", "und", "von", "mit", "ein",
    "eine", "einen", "in", "im", "auf", "am", "an", "zu", "ist",
    "wird", "werden", "the", "a", "an", "and", "of", "to", "in",
    "on", "for", "with", "new", "news",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ContinentalNewsBot/1.1)"
}


def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\wäöüß-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(entry):
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    return datetime.now(timezone.utc)


def fetch_feed(query):
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=de&gl=DE&ceid=DE:de"
    )
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return feedparser.parse(response.content)


def score_item(title, summary):
    text = normalize(title + " " + summary)

    score = 0
    category = "COMPANY"

    if "continental" in text:
        score += 150
    else:
        score -= 200

    if any(term in text for term in KORBACH_TERMS):
        score += 1000
        category = "KORBACH_FACTORY"
    elif any(term in text for term in FACTORY_TERMS):
        score += 500
        category = "FACTORY"

    score += sum(250 for term in PRODUCTION_TERMS if term in text)
    score += sum(50 for term in TIRE_TERMS if term in text)

    return score, category


def event_tokens(title, summary):
    text = normalize(title + " " + summary)
    words = []
    for word in text.split():
        if word in GENERIC_WORDS or len(word) < 3:
            continue
        words.append(word)
    return set(words)


def canonical_event_family(title, summary):
    text = normalize(title + " " + summary)

    # The first test exposed three articles about exactly the same
    # Continental wind-park event around Korbach/Twistetal/North Hesse.
    if (
        "continental" in text
        and "windpark" in text
        and any(place in text for place in ("korbach", "twistetal", "nordhessen"))
    ):
        return "continental_windpark_korbach_nordhessen"

    return ""


def same_event(a, b):
    family_a = canonical_event_family(a["title"], a["summary"])
    family_b = canonical_event_family(b["title"], b["summary"])

    if family_a or family_b:
        return bool(family_a and family_a == family_b)

    ta = event_tokens(a["title"], a["summary"])
    tb = event_tokens(b["title"], b["summary"])

    if not ta or not tb:
        return False

    shared = ta & tb
    union = ta | tb
    jaccard = len(shared) / len(union)

    # Conservative generic grouping: require several meaningful shared
    # terms plus either a strong overlap or the same factory/place anchor.
    strong_anchors = {
        "korbach", "werk", "reifenwerk", "fabrik", "factory",
        "plant", "windpark", "produktion", "production",
        "investition", "investment", "anlage",
    }
    shared_strong = shared & strong_anchors

    return (
        len(shared) >= 4
        and jaccard >= 0.38
    ) or (
        len(shared) >= 3
        and len(shared_strong) >= 2
        and jaccard >= 0.25
    )


def event_key(title, summary):
    family = canonical_event_family(title, summary)
    if family:
        return family

    tokens = sorted(event_tokens(title, summary))
    return hashlib.sha1(" ".join(tokens[:32]).encode("utf-8")).hexdigest()


def clean_summary(summary):
    text = re.sub(r"<[^>]+>", " ", summary or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:700]


def collect_items():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items = []
    seen_urls = set()

    for query in SEARCH_QUERIES:
        try:
            feed = fetch_feed(query)
            print(f"OK: {query} -> {len(feed.entries)} items")
        except Exception as exc:
            print(f"ERROR: {query} -> {exc}")
            continue

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link or link in seen_urls:
                continue

            published_at = parse_date(entry)
            if published_at < cutoff:
                continue

            summary = clean_summary(entry.get("summary") or entry.get("description") or "")
            score, category = score_item(title, summary)

            if "continental" not in normalize(title + " " + summary):
                continue

            seen_urls.add(link)
            items.append({
                "title": title,
                "summary": summary,
                "url": link,
                "published_at": published_at.isoformat(),
                "score": score,
                "category": category,
                "event_key": event_key(title, summary),
            })

    return items


def choose_items(items):
    # First collapse exact event families / semantically identical stories.
    groups = []
    for item in sorted(
        items,
        key=lambda x: (x["score"], x["published_at"]),
        reverse=True,
    ):
        placed = False
        for group in groups:
            if same_event(item, group[0]):
                group.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])

    representatives = []
    for group in groups:
        best = max(group, key=lambda x: (x["score"], x["published_at"]))
        best["source_count"] = len(group)
        best["sources"] = [
            {
                "title": x["title"],
                "url": x["url"],
            }
            for x in group[:5]
        ]
        representatives.append(best)

    # Factory/Korbach events are always selected before other Continental news.
    representatives.sort(
        key=lambda x: (
            2 if x["category"] == "KORBACH_FACTORY"
            else 1 if x["category"] == "FACTORY"
            else 0,
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )

    return representatives[:MAX_POSTS]


def load_seen():
    try:
        with open("whatsapp_seen.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data if isinstance(data, list) else [])
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open("whatsapp_seen.json", "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def format_post(item):
    published = item["published_at"].replace("T", " ").replace("+00:00", " UTC")
    source_note = ""
    if item.get("source_count", 1) > 1:
        source_note = f"\n\n📰 Sources: {item['source_count']}"

    return (
        f"🟡 {item['category']}\n\n"
        f"**{item['title']}**\n\n"
        f"{item['summary']}\n\n"
        f"🔗 {item['url']}\n"
        f"🕒 {published}"
        f"{source_note}"
    )


def main():
    items = collect_items()
    selected = choose_items(items)

    seen = load_seen()
    new_items = []

    for item in selected:
        key = item["event_key"]
        if key in seen:
            continue
        new_items.append(item)
        seen.add(key)

    print(f"Selected {len(new_items)} new posts.")

    posts = []
    for index, item in enumerate(new_items, 1):
        print(
            f"{index:02d}. [{item['category']}] "
            f"{item['title']}"
        )
        posts.append(format_post(item))

    with open("whatsapp_posts.json", "w", encoding="utf-8") as f:
        json.dump(new_items, f, ensure_ascii=False, indent=2)

    with open("whatsapp_posts.txt", "w", encoding="utf-8") as f:
        f.write("\n\n" + ("\n\n" + ("-" * 72) + "\n\n").join(posts))

    save_seen(seen)


if __name__ == "__main__":
    main()
