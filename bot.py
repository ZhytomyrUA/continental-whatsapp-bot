#!/usr/bin/env python3
"""Continental News collector for a normal WhatsApp Channel.

Normal mode prepares up to 12 DIFFERENT news events. Factory/production stories
are prioritized. Multiple articles about the same event are grouped together.
Bootstrap mode scans the previous 60 days and builds a backlog so the channel
can be populated before switching to the normal rolling search.
The script does not publish to WhatsApp.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser

MAX_EVENTS = 12
LOOKBACK_HOURS = 72
BOOTSTRAP_LOOKBACK_HOURS = 60 * 24
BOOTSTRAP_MAX_EVENTS = 250
SEEN_DAYS = 90

# Set BOOTSTRAP=1 for the first run. It scans 60 days and writes a backlog.
# After that, remove BOOTSTRAP or set it to 0 for the normal 72-hour / 12-event mode.
BOOTSTRAP_ENV = str(__import__("os").environ.get("BOOTSTRAP", "")).lower() in {"1", "true", "yes"}
# First run is automatically a 60-day bootstrap; later runs are normal.
BOOTSTRAP = BOOTSTRAP_ENV or not BOOTSTRAP_MARKER.exists()

SEEN_FILE = Path("whatsapp_seen.json")
POSTS_JSON = Path("whatsapp_posts.json")
POSTS_TXT = Path("whatsapp_posts.txt")
BOOTSTRAP_MARKER = Path("whatsapp_bootstrap_complete.json")

QUERIES = [
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
    "continental","reuters","dpa","press","release","worldwide","weltweit",
}

KORBACH_WORDS = ("korbach", "reifenwerk korbach", "werk korbach")
FACTORY_WORDS = (
    "werk", "reifenwerk", "fabrik", "produktion", "produktions", "fertigung",
    "plant", "factory", "manufacturing", "production", "reifenproduktion",
    "reifenerzeugung", "production site", "produktionsstandort",
    "werkstandort", "standort", "produktionsanlage", "produktionslinie",
    "fertigungsanlage", "werkserweiterung", "produktionskapazität",
    "produktionskapazitaet", "neubau", "arbeitsplätze", "arbeitsplaetze",
)
PRODUCTION_WORDS = (
    "produktion", "produziert", "produced", "production", "fertigung",
    "manufacturing", "manufactures", "kapazität", "kapazitaet", "capacity",
    "investition", "investitionen", "investment", "ausbau", "expansion",
    "erweiterung", "anlage", "modernisierung", "umbau", "verlagerung",
    "relocation", "schließung", "schliessung", "shutdown",
    "produktionsanlage", "produktionslinie", "fertigungsanlage",
    "werkserweiterung", "produktionskapazität", "produktionskapazitaet",
    "neubau", "standort", "werkstandort",
)
TIRE_WORDS = ("reifen", "tire", "tyre", "pkw-reifen", "lkw-reifen", "truckreifen")
HIGH_VALUE = (
    "stellenabbau", "arbeitsplätze", "arbeitsplaetze", "entlassung", "verlagerung",
    "schließung", "schliessung", "werksschließung", "werksschliessung",
    "investition", "investitionen", "ausbau", "erweiterung", "restrukturierung",
    "reorganisation", "betriebsrat", "ig metall", "tarifvertrag", "jobs",
    "quartalszahlen", "umsatz", "gewinn", "verlust", "vorstand", "aufsichtsrat",
)

# Terms that make two articles much more likely to describe the same event.
EVENT_ANCHORS = (
    "windpark", "windkraft", "reifenwerk", "reifenfabrik", "produktionsstandort",
    "produktion", "fertigung", "investition", "investitionen", "verlagerung",
    "schliessung", "schließung", "stellenabbau", "restrukturierung", "erweiterung",
    "ausbau", "neuer reifen", "neue reifen", "konzeptreifen", "ganzjahresreifen",
    "allseasoncontact", "ecogeneration", "trailer-reifen", "trailerreifen",
)

SOURCE_BONUS = {
    "continental.com": 120,
    "continental-reifen.de": 100,
    "reuters.com": 55,
    "tagesschau.de": 50,
    "hessenschau.de": 45,
    "hna.de": 50,
    "ffh.de": 35,
    "reifenpresse.de": 55,
    "automobilwoche.de": 45,
    "handelsblatt.com": 40,
    "faz.net": 35,
    "sueddeutsche.de": 35,
    "heise.de": 30,
    "logistra.de": 30,
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


def text_of(item: dict) -> str:
    return norm(f"{item.get('title','')} {item.get('summary','')}")


def tokens(item: dict) -> set[str]:
    text = text_of(item)
    return {w for w in text.split() if len(w) >= 4 and w not in STOPWORDS}


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


def has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def article_fingerprint(item: dict) -> set[str]:
    """Keep meaningful words but remove generic words that cause false merges."""
    generic = {
        "continental", "reifen", "tire", "tyre", "werk", "factory", "plant",
        "produktion", "production", "fertigung", "company", "unternehmen",
        "neuer", "neue", "neuen", "neuem", "setzt", "startet", "entwickelt",
        "erhalt", "erhaltet", "erhalten", "bekannt", "meldet", "berichtet",
        "jetzt", "heute", "jahr", "jahre", "million", "millionen",
    }
    return {w for w in tokens(item) if w not in generic and len(w) >= 5}


def special_family(item: dict) -> str | None:
    t = text_of(item)

    # One event: Continental wind farm serving the Korbach tire plant.
    if "continental" in t and "windpark" in t and has_any(t, ("korbach", "twistetal", "nordhessen")):
        return "windpark|korbach|continental"

    # One event: the same trailer-tire launch, including a photo gallery.
    if has_any(t, ("trailer-reifen", "trailerreifen")) and has_any(
        t, ("rollwiderstand", "laufleistung", "eco generation", "ecogeneration")
    ):
        return "trailerreifen|ecogeneration|continental"

    # Same product family even if one headline says "new trailer tire".
    if "eco generation 5" in t or "ecogeneration 5" in t:
        return "ecogeneration5|trailerreifen|continental"

    if "allseasoncontact 2" in t and has_any(t, ("test", "testet", "empfehlenswert")):
        return "allseasoncontact2|test|continental"

    if "konzeptreifen" in t and has_any(t, ("recycel", "recycelt", "recycling", "rohstoffen")):
        return "konzeptreifen|recycling|continental"

    return None


def event_family(item: dict) -> str:
    special = special_family(item)
    if special:
        return special

    t = text_of(item)
    parts = []
    if "continental" in t:
        parts.append("continental")
    if has_any(t, KORBACH_WORDS):
        parts.append("korbach")
    if has_any(t, HIGH_VALUE):
        # Use the concrete issue rather than a generic highvalue bucket.
        for key in ("schließung", "schliessung", "verlagerung", "stellenabbau", "investition", "erweiterung", "ausbau", "restrukturierung"):
            if key in t:
                parts.append(key)
                break

    # For product stories use distinctive product names when available.
    product_keys = [
        "allseasoncontact 2", "ecogeneration 5", "contiecontact", "ultracontact",
        "premiumcontact", "sportcontact", "vancontact", "contihybrid", "contitrailer",
    ]
    for key in product_keys:
        if key in t:
            parts.append(key.replace(" ", "-"))
            break

    # Use the strongest anchor plus a compact fingerprint. This avoids putting
    # unrelated generic Continental tire articles into one family.
    anchor = next((a for a in EVENT_ANCHORS if a in t), None)
    if anchor:
        parts.append(anchor.replace(" ", "-"))

    fp = sorted(article_fingerprint(item))[:5]
    parts.extend(fp)
    return "|".join(dict.fromkeys(parts)) or "continental|unknown"


def event_similarity(a: dict, b: dict) -> float:
    aa = article_fingerprint(a)
    bb = article_fingerprint(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, min(len(aa), len(bb)))


def same_event(a: dict, b: dict) -> bool:
    if a.get("event_family") == b.get("event_family"):
        return True

    # Explicit special families always merge.
    sa, sb = special_family(a), special_family(b)
    if sa and sa == sb:
        return True

    ta, tb = text_of(a), text_of(b)
    shared = article_fingerprint(a) & article_fingerprint(b)
    if not shared:
        return False

    # Photo gallery vs article: usually same story if the distinctive words match.
    if ("fotostrecke" in ta or "fotostrecke" in tb) and len(shared) >= 3:
        return event_similarity(a, b) >= 0.60

    # Product/event title overlap. Require at least two distinctive words so
    # generic "Continental Reifen" stories do not collapse together.
    if len(shared) >= 3 and event_similarity(a, b) >= 0.60:
        strong = set(EVENT_ANCHORS)
        return bool(shared & strong) or any(x in ta and x in tb for x in (
            "allseasoncontact", "ecogeneration", "konzeptreifen", "trailerreifen",
            "windpark", "korbach",
        ))

    return False


def score(item: dict) -> tuple[int, str]:
    t = text_of(item)
    s = SOURCE_BONUS.get(source(item["url"]), 0)

    if "continental" in t:
        s += 150
    else:
        s -= 200

    if has_any(t, KORBACH_WORDS):
        s += 1400
        category = "KORBACH_FACTORY"
    elif has_any(t, FACTORY_WORDS):
        s += 850
        # Distinguish actual production/plant stories from generic mentions.
        if has_any(t, PRODUCTION_WORDS):
            category = "FACTORY_PRODUCTION"
        elif has_any(t, ("mitarbeiter", "beschäftigte", "beschaeftigte", "arbeitsplätze", "arbeitsplaetze", "betriebsrat")):
            category = "EMPLOYEES_FACTORY"
        else:
            category = "FACTORY"
    elif has_any(t, PRODUCTION_WORDS):
        s += 350
        category = "PRODUCTION"
    elif has_any(t, ("mitarbeiter", "beschäftigte", "beschaeftigte", "arbeitsplätze", "arbeitsplaetze", "jobs")):
        category = "EMPLOYEES_FACTORY"
    elif has_any(t, ("test", "vergleich", "reifentest", "ganzjahresreifen-test")):
        category = "TIRE_TEST"
    elif has_any(t, ("technologie", "innovation", "konzeptreifen", "recycel", "nachhaltigkeit")):
        category = "CONTINENTAL_TECHNOLOGY"
    elif has_any(t, TIRE_WORDS):
        category = "CONTINENTAL_TIRE"
    else:
        category = "COMPANY"

    if has_any(t, PRODUCTION_WORDS):
        s += 250
    if has_any(t, TIRE_WORDS):
        s += 50
    if has_any(t, HIGH_VALUE):
        s += 80

    return s, category


def fetch_candidates() -> list[dict]:
    lookback = BOOTSTRAP_LOOKBACK_HOURS if BOOTSTRAP else LOOKBACK_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback)
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
            # Do not discard factory/production stories merely because their
            # numeric score is low. Classification is handled after collection.
            # Only reject results that are clearly not Continental-related.
            t = text_of(item)
            if "continental" not in t:
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
    canonical = item.get("event_family") or norm(item["title"])
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def choose_events(candidates: list[dict], seen: dict[str, str]) -> list[dict]:
    candidates.sort(
        key=lambda x: (
            x["category"] == "KORBACH_FACTORY",
            x["category"] == "FACTORY",
            x["category"] == "PRODUCTION",
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )

    groups: list[dict] = []
    for item in candidates:
        # First use canonical family IDs where available.
        eid = event_id(item)
        if eid in seen:
            continue

        matched = next((g for g in groups if same_event(item, g)), None)
        if matched is not None:
            matched.setdefault("alternate_sources", []).append({
                "source": item["source"],
                "title": item["title"],
                "url": item["url"],
                "published_at": item["published_at"],
            })
            # If this article is newer or from a stronger source, keep it as
            # the representative while preserving the old representative too.
            if (item["score"], item["published_at"]) > (matched["score"], matched["published_at"]):
                old_rep = {k: matched[k] for k in ("source", "title", "url", "published_at")}
                matched.update({k: item[k] for k in ("source", "title", "url", "published_at", "summary", "score", "category", "event_family")})
                matched["alternate_sources"].append(old_rep)
            continue

        item["event_id"] = eid
        item["alternate_sources"] = []
        groups.append(item)

    groups.sort(
        key=lambda x: (
            x["category"] == "KORBACH_FACTORY",
            x["category"] == "FACTORY",
            x["category"] == "PRODUCTION",
            x["score"],
            x["published_at"],
        ),
        reverse=True,
    )
    return groups[:(BOOTSTRAP_MAX_EVENTS if BOOTSTRAP else MAX_EVENTS)]


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
    print("=== Continental WhatsApp Channel News v4 ===")
    if BOOTSTRAP:
        print(f"MODE: BOOTSTRAP | Lookback: {BOOTSTRAP_LOOKBACK_HOURS // 24} days | Max DIFFERENT EVENTS: {BOOTSTRAP_MAX_EVENTS}")
    else:
        print(f"MODE: NORMAL | Lookback: {LOOKBACK_HOURS}h | Max DIFFERENT EVENTS: {MAX_EVENTS}")

    candidates = fetch_candidates()
    print(f"Unique article candidates: {len(candidates)}")

    seen = load_seen()
    selected = choose_events(candidates, seen)

    counts = {}
    for x in selected:
        counts[x["category"]] = counts.get(x["category"], 0) + 1
    print("Category counts:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Selected {len(selected)} DIFFERENT events.")
    for i, item in enumerate(selected, 1):
        print(f"{i:02d}. [{item['category']}] {item['title']} - {item['source']}")
        if item.get("alternate_sources"):
            print(f"    grouped alternative sources: {len(item['alternate_sources'])}")

    POSTS_JSON.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    if BOOTSTRAP:
        Path("whatsapp_backlog.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
        Path("whatsapp_backlog.txt").write_text(
            "\n\n".join(post_text(x, i) for i, x in enumerate(selected, 1)) + ("\n" if selected else ""),
            encoding="utf-8",
        )
        BOOTSTRAP_MARKER.write_text(
            json.dumps({"completed_at": datetime.now(timezone.utc).isoformat(), "events": len(selected)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    POSTS_TXT.write_text(
        "\n\n".join(post_text(x, i) for i, x in enumerate(selected, 1)) + ("\n" if selected else ""),
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).isoformat()
    for item in selected:
        seen[item["event_id"]] = now
    save_seen(seen)

    print("Created: whatsapp_posts.json")
    if BOOTSTRAP:
        print("Created: whatsapp_backlog.json")
        print("Created: whatsapp_backlog.txt")
        print("Created: whatsapp_bootstrap_complete.json")
    print("Created: whatsapp_posts.txt")
    print("Updated: whatsapp_seen.json")


if __name__ == "__main__":
    main()
