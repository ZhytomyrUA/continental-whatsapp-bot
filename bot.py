#!/usr/bin/env python3
"""Continental News collector for a normal WhatsApp Channel.

v5.6 FACTORY-FIRST: Korbach and real factory/production events are selected first.
Normal mode prepares up to 12 DIFFERENT news events. v5.6 uses article evidence first, with narrowly-scoped search-query context only as a secondary confirmation for highly specific factory searches. Multiple articles about the same
event are grouped together, but distinct factory events are never collapsed merely
because they share a broad factory family.
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
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

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
BOOTSTRAP_MARKER = Path("whatsapp_bootstrap_complete.json")
BOOTSTRAP = BOOTSTRAP_ENV or not BOOTSTRAP_MARKER.exists()

SEEN_FILE = Path("whatsapp_seen.json")
POSTS_JSON = Path("whatsapp_posts.json")
POSTS_TXT = Path("whatsapp_posts.txt")
PLANT_QUERIES = [
    "Continental Korbach Werk Produktion",
    "Continental Korbach Reifenwerk Windpark",
    "Continental Hannover Reifenwerk Produktion",
    "Continental Aachen Reifenwerk Produktion",
    "Continental Roding Reifenwerk Produktion",
    "Continental Regensburg Reifenwerk Produktion",
    "Continental Fürstenwalde Reifenwerk Produktion",
    "Continental Stöcken Werk Produktion",
    "Continental Deutschland Reifenwerk Mitarbeiter",
    "Continental Deutschland Werk Stellenabbau",
    "Continental Deutschland Werk Investition",
    "Continental Deutschland Werk Verlagerung",
    "Continental Deutschland Werk Schließung",
]

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

KORBACH_FACTORY_CONTEXT_WORDS = (
    "reifenwerk", "reifenfabrik", "produktionsstandort", "produktionsanlage",
    "produktionslinie", "fertigungsanlage", "fertigungsstandort", "werkserweiterung",
    "werksschließung", "werksschliessung", "werkschließung", "werkschliessung",
    "werksschliessung", "werksschließung", "werk in ", "werk korbach",
    "werk hannover", "werk stöcken", "werk stoecken", "werk aachen",
    "werk roding", "werk regensburg", "werk fürstenwalde",
    "werk produktion", "werk fertigung", "werk mitarbeiter", "werk beschäftigte",
    "werk beschaeftigte", "werk investition", "werk modernisierung",
    "werk erweiterung", "werk verlag", "werk schließung", "werk schliessung",
    "werk stellenabbau", "werk betriebsrat",
)

FACTORY_ACTION_WORDS = (
    "produktion", "produktions", "fertigung", "fertigungs", "produktionslinie",
    "produktionsanlage", "investition", "investitionen", "modernisierung",
    "ausbau", "erweiterung", "werkserweiterung", "verlagerung",
    "schließung", "schliessung", "stellenabbau", "mitarbeiter",
    "beschäftigte", "beschaeftigte", "betriebsrat", "kapazität", "kapazitaet",
    "windpark", "windkraft", "energieversorgung", "stromversorgung",
)

FACTORY_WORDS = (
    "reifenwerk", "reifenfabrik", "produktionsstandort", "produktionsanlage",
    "produktionslinie", "fertigungsanlage", "fertigungsstandort", "werkserweiterung",
    "werksschließung", "werksschliessung", "werkschließung", "werkschliessung",
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


def search_context(item: dict) -> str:
    return norm(" ".join(item.get("matched_queries", []) or []))


def title_tokens(item: dict) -> set[str]:
    generic = {"continental","reifen","reifenhersteller","tire","tyre","news","aktuell",
               "neue","neuer","neuen","macht","setzt","startet","entwickelt",
               "profitiert","hersteller"}
    return {w for w in norm(item.get("title","")).split() if len(w) >= 5 and w not in generic}


def title_similarity(a: dict, b: dict) -> float:
    aa, bb = title_tokens(a), title_tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, min(len(aa), len(bb)))


def tokens(item: dict) -> set[str]:
    text = text_of(item)
    return {w for w in text.split() if len(w) >= 4 and w not in STOPWORDS}


def source(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1).lower() if m else "unknown"


def google_rss(query: str, after: str | None = None, before: str | None = None) -> str:
    q = query
    if after:
        q += f" after:{after}"
    if before:
        q += f" before:{before}"
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=de&gl=DE&ceid=DE:de"

def original_url(url: str) -> str:
    # Google News RSS often wraps the publisher URL. Keep the publisher URL
    # when it is exposed in the RSS entry; otherwise retain the RSS link.
    parsed = urlparse(url or "")
    qs = parse_qs(parsed.query)
    for key in ("url", "u", "target"):
        if qs.get(key):
            candidate = unquote(qs[key][0])
            if candidate.startswith("http") and "news.google.com" not in urlparse(candidate).netloc:
                return candidate
    return url


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

    # Same Gravity MTB launch can appear under slightly different headlines
    # (e.g. Continental vs. Velomotion).
    if has_any(t, ("gravity-mtb", "gravity mtb")) and has_any(t, ("argotal", "kryptotal", "xynotal")):
        return "gravity-mtb|argotal-kryptotal-xynotal|continental"

    # Same ADAC WinterContact TS 870 result can be repeated with different
    # verbs/headlines by Continental and media outlets.
    if "wintercontact ts 870" in t and has_any(t, ("adac", "winterreifentest")) and has_any(t, ("test", "überzeugt", "gewinnt", "empfehlung")):
        return "wintercontact-ts870|adac|test|continental"

    return None


def event_family(item: dict) -> str:
    special = special_family(item)
    if special:
        return special

    t = text_of(item)
    if is_korbach_factory(item):
        if has_any(t, ("windpark", "windkraft")):
            return "korbach|windpark"
        if has_any(t, ("schließung", "schliessung")):
            return "korbach|closure"
        if "verlagerung" in t:
            return "korbach|relocation"
        if has_any(t, ("stellenabbau", "arbeitsplätze", "arbeitsplaetze", "mitarbeiter", "beschäftigte", "beschaeftigte", "betriebsrat", "ig metall")):
            return "korbach|employment"
        if has_any(t, ("investition", "investitionen", "investment")):
            return "korbach|investment"
        if has_any(t, ("modernisierung", "umbau", "ausbau", "erweiterung")):
            return "korbach|modernization"
        if has_any(t, ("produktion", "fertigung", "produktionslinie", "produktionsanlage")):
            return "korbach|production"
        return "korbach|general"

    parts = []
    if "continental" in t:
        parts.append("continental")
    if has_any(t, HIGH_VALUE):
        for key in ("schließung", "schliessung", "verlagerung", "stellenabbau", "investition", "erweiterung", "ausbau", "restrukturierung"):
            if key in t:
                parts.append(key)
                break
    product_keys = [
        "allseasoncontact 2", "ecogeneration 5", "contiecontact", "ultracontact",
        "premiumcontact", "sportcontact", "vancontact", "contihybrid", "contitrailer",
    ]
    for key in product_keys:
        if key in t:
            parts.append(key.replace(" ", "-"))
            break
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
        family = a.get("event_family") or ""
        if family.startswith("korbach|"):
            if special_family(a) and special_family(a) == special_family(b):
                return True
            return title_similarity(a, b) >= 0.75 or (
                len(article_fingerprint(a) & article_fingerprint(b)) >= 4
                and event_similarity(a, b) >= 0.70
            )
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

    # Near-identical headlines from different publishers are one event.
    if title_similarity(a, b) >= 0.78:
        return True

    # Product/event title overlap. Require distinctive words so generic
    # "Continental Reifen" stories do not collapse together.
    if len(shared) >= 3 and event_similarity(a, b) >= 0.60:
        strong = set(EVENT_ANCHORS)
        return bool(shared & strong) or any(x in ta and x in tb for x in (
            "allseasoncontact", "ecogeneration", "konzeptreifen", "trailerreifen",
            "windpark", "korbach",
        ))

    return False


CATEGORY_PRIORITY = {
    "KORBACH_FACTORY": 100, "FACTORY_PRODUCTION": 85, "FACTORY": 80,
    "EMPLOYEES_FACTORY": 70, "PRODUCTION": 60, "CONTINENTAL_TECHNOLOGY": 40,
    "CONTINENTAL_TIRE": 30, "TIRE_TEST": 20, "COMPANY": 10,
}

FACTORY_NOUNS = (
    "reifenwerk", "reifenfabrik", "produktionsstandort", "produktionsanlage",
    "produktionslinie", "fertigungsanlage", "fertigungsstandort", "werk",
    "fabrik", "werkstandort", "produktionsstätte", "produktionsstaette",
)

FACTORY_ACTIONS_STRONG = (
    "produktion", "produktions", "produziert", "fertigung", "fertigt",
    "investition", "investitionen", "investment", "modernisierung", "modernisiert",
    "ausbau", "erweiterung", "werkserweiterung", "verlagerung", "verlagert",
    "schließung", "schliessung", "stellenabbau", "betriebsrat", "mitarbeiter",
    "beschäftigte", "beschaeftigte", "arbeitsplätze", "arbeitsplaetze",
    "windpark", "windkraft", "energieversorgung", "stromversorgung",
    "kapazität", "kapazitaet", "neubau", "bau eines", "spatenstich",
)

GENERIC_PRODUCT_SIGNALS = (
    "reifentest", "winterreifentest", "ganzjahresreifentest", "vergleich",
    "test", "empfehlung", "empfehlenswert", "profi-werkstatt-marke",
    "deal", "rabatt", "preisvergleich", "angebot", "aktie", "börsen",
    "boerse", "kursziel", "analyst",
)


def _has_nearby(text: str, left_words: tuple[str, ...], right_words: tuple[str, ...], window: int = 140) -> bool:
    """True when a factory noun and a factory action occur close to each other."""
    for left in left_words:
        for m in re.finditer(re.escape(left), text):
            chunk = text[max(0, m.start() - window): min(len(text), m.end() + window)]
            if any(r in chunk for r in right_words):
                return True
    return False


def _factory_evidence(item: dict, location: str | None = None) -> dict[str, bool]:
    """Evaluate the article itself. Search-query context is deliberately excluded."""
    t = text_of(item)
    title = norm(item.get("title", ""))
    loc = bool(location and location in t) if location else False
    factory_noun = has_any(t, FACTORY_NOUNS)
    action = has_any(t, FACTORY_ACTIONS_STRONG)
    nearby = _has_nearby(t, FACTORY_NOUNS, FACTORY_ACTIONS_STRONG)
    title_factory = has_any(title, FACTORY_NOUNS)
    title_action = has_any(title, FACTORY_ACTIONS_STRONG)
    generic_product = has_any(title, GENERIC_PRODUCT_SIGNALS)
    return {
        "location": loc,
        "factory_noun": factory_noun,
        "action": action,
        "nearby": nearby,
        "title_factory": title_factory,
        "title_action": title_action,
        "generic_product": generic_product,
    }


def is_korbach_factory(item: dict) -> bool:
    """Classify a genuine Korbach factory event.

    v5.6 uses a two-layer proof:
    1) article evidence is preferred;
    2) a highly specific Korbach factory search may confirm a strong factory
       headline even when the RSS summary omits the word Korbach.

    The query can NEVER promote a generic tire/product/test story by itself.
    """
    t = text_of(item)
    title = norm(item.get("title", ""))
    if "continental" not in t:
        return False

    e = _factory_evidence(item, "korbach")
    if e["location"]:
        # Strong article-side evidence.
        if e["factory_noun"] and e["action"] and e["nearby"]:
            return True
        if "korbach" in title and e["title_factory"] and e["title_action"]:
            return True
        if e["action"] and not e["generic_product"] and has_any(t, (
            "reifenwerk", "reifenfabrik", "produktionsstandort", "produktionsanlage",
            "werk korbach", "werk in korbach", "standort korbach",
            "industriereifen", "reifenproduktion", "reifenfertigung",
        )):
            return True

    # Secondary confirmation: only use query context when BOTH the query and
    # the article strongly indicate a local factory event.
    q = search_context(item)
    query_local = (
        "korbach" in q
        and has_any(q, ("reifenwerk", "reifen werk", "werk produktion", "reifen produktion", "windpark", "investition", "schließung", "schliessung", "verlagerung", "mitarbeiter"))
    )
    article_factory_action = has_any(title, FACTORY_ACTIONS_STRONG) or _has_nearby(t, FACTORY_NOUNS, FACTORY_ACTIONS_STRONG)
    article_factory_subject = has_any(title, (
        "windpark", "windkraft", "reifenwerk", "reifenfabrik", "produktionsstandort",
        "produktion", "fertigung", "verlagert", "verlagerung", "investition",
        "modernisierung", "ausbau", "erweiterung", "schließung", "schliessung",
        "stellenabbau", "mitarbeiter", "beschäftigte", "spatenstich", "bau eines",
    ))
    generic_product = has_any(title, GENERIC_PRODUCT_SIGNALS)

    if query_local and article_factory_action and article_factory_subject and not generic_product:
        return True

    return False


def is_factory_story(item: dict) -> bool:
    """Classify a real factory/production story without trusting broad queries."""
    t = text_of(item)
    title = norm(item.get("title", ""))
    if "continental" not in t:
        return False

    e = _factory_evidence(item)
    if e["nearby"] and e["action"]:
        return True

    explicit = bool(re.search(
        r"continental.{0,120}(werk|fabrik|standort).{0,140}(produktion|fertigung|investition|mitarbeiter|beschaeftigte|beschäftigte|modernisierung|ausbau|erweiterung|verlagerung|schliessung|schließung|stellenabbau|windpark|energie)",
        t,
    ))
    if explicit:
        return True

    # Narrow secondary query confirmation for plant-specific searches.
    q = search_context(item)
    query_factory = has_any(q, ("reifenwerk", "werk produktion", "werk investition", "werk schließung", "werk schliessung", "werk verlagerung", "werk mitarbeiter"))
    strong_title_action = has_any(title, FACTORY_ACTIONS_STRONG)
    title_plant = has_any(title, FACTORY_NOUNS)
    return bool(query_factory and strong_title_action and (title_plant or has_any(title, (
        "produktion", "fertigung", "verlagert", "verlagerung", "investition", "schließung", "schliessung", "stellenabbau", "windpark", "spatenstich"
    ))) and not has_any(title, GENERIC_PRODUCT_SIGNALS))


def is_real_production_story(item: dict) -> bool:
    t = text_of(item)
    title = norm(item.get("title", ""))
    if "continental" not in t:
        return False
    if is_factory_story(item):
        return True
    if has_any(t, ("reifenproduktion", "reifenerzeugung", "industriereifen-produktion",
                   "produktionskapazität", "produktionskapazitaet", "fertigungsstandort")):
        return True
    # "Industriereifen" alone is not enough: it must be tied to an actual
    # production action in the Continental headline.
    if re.search(r"continental.{0,100}(produziert|produzieren|fertigt|fertigen|verlagert|verlagern).{0,100}(reifenproduktion|industriereifen|werk|fabrik|anlage|kapazität|kapazitaet)", title):
        return True
    return bool(re.search(r"continental.{0,80}(produktion|fertigung|manufacturing|production).{0,80}(reifen|werk|fabrik|anlage|kapazität|kapazitaet|standort)", title))

def score(item: dict) -> tuple[int, str]:
    t = text_of(item)
    s = SOURCE_BONUS.get(source(item["url"]), 0)

    if "continental" in t:
        s += 150
    else:
        s -= 200

    korbach = is_korbach_factory(item)
    factory = is_factory_story(item)
    production = is_real_production_story(item)

    if korbach:
        s += 2200
        category = "KORBACH_FACTORY"
    elif factory and production:
        s += 1000
        category = "FACTORY_PRODUCTION"
    elif factory:
        s += 900
        if has_any(t, ("mitarbeiter", "beschäftigte", "beschaeftigte", "arbeitsplätze", "arbeitsplaetze", "betriebsrat", "stellenabbau")):
            category = "EMPLOYEES_FACTORY"
        else:
            category = "FACTORY"
    elif production:
        s += 500
        category = "PRODUCTION"
    elif has_any(t, ("aktie", "aktien", "börse", "boerse", "dax", "mdax", "aumovio",
                     "contitech", "strategische partnerschaft", "verkauft", "verkauf",
                     "retail", "ausbildungsbetrieb", "werkstatt-marke", "übernimmt",
                     "uebernimmt", "übernahme", "uebernahme")):
        category = "COMPANY"
    elif has_any(t, ("test", "vergleich", "reifentest", "ganzjahresreifen-test")):
        category = "TIRE_TEST"
    elif has_any(t, ("technologie", "innovation", "konzeptreifen", "recycel", "nachhaltigkeit")):
        category = "CONTINENTAL_TECHNOLOGY"
    elif has_any(t, ("mitarbeiter", "beschäftigte", "beschaeftigte", "arbeitsplätze", "arbeitsplaetze", "jobs")):
        category = "EMPLOYEES_FACTORY"
    elif has_any(t, TIRE_WORDS):
        category = "CONTINENTAL_TIRE"
    else:
        category = "COMPANY"

    if factory:
        s += 300
    if production:
        s += 200
    if has_any(t, TIRE_WORDS):
        s += 50
    if has_any(t, HIGH_VALUE):
        s += 80
    return s, category


def fetch_candidates() -> list[dict]:
    lookback = BOOTSTRAP_LOOKBACK_HOURS if BOOTSTRAP else LOOKBACK_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback)
    found: dict[str, dict] = {}

    queries = QUERIES + (PLANT_QUERIES if BOOTSTRAP else [])
    now = datetime.now(timezone.utc)
    windows = [(None, None)]
    if BOOTSTRAP:
        windows = []
        for days_ago_start, days_ago_end in [(0,7),(7,14),(14,21),(21,30),(30,45),(45,60)]:
            before_dt = now - timedelta(days=days_ago_start)
            after_dt = now - timedelta(days=days_ago_end)
            windows.append((after_dt.strftime("%Y-%m-%d"), before_dt.strftime("%Y-%m-%d")))

    for query in queries:
        for after, before in windows:
            label = f"{query} [{after or 'all'}..{before or 'all'}]" if BOOTSTRAP else query
            print(f"SEARCH: {label}")
            try:
                feed = feedparser.parse(google_rss(query, after, before))
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
                url = original_url(getattr(entry, "link", "") or "")
                summary = clean(getattr(entry, "summary", ""))
                if not title or not url:
                    continue

                item = {
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source": source(url),
                    "published_at": dt.isoformat(),
                    "matched_queries": [query],
                }
                item["score"], item["category"] = score(item)
                item["korbach_priority"] = is_korbach_factory(item)
                item["factory_evidence"] = _factory_evidence(item, "korbach" if item["korbach_priority"] else None)
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
                if old is None:
                    found[key] = item
                else:
                    old.setdefault("matched_queries", [])
                    for mq in item.get("matched_queries", []):
                        if mq not in old["matched_queries"]:
                            old["matched_queries"].append(mq)
                    if item["score"] > old["score"]:
                        item["matched_queries"] = old["matched_queries"]
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
    # Do not use the broad event_family alone: e.g. several different
    # Korbach production stories must remain separate across runs.
    special = special_family(item)
    if special:
        canonical = special
    else:
        fp = sorted(article_fingerprint(item))
        # Keep a compact but distinctive fingerprint for seen-state stability.
        canonical = (item.get("event_family") or "continental|unknown") + "|" + "|".join(fp[:8])
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


FACTORY_CATEGORIES = {"KORBACH_FACTORY", "FACTORY_PRODUCTION", "FACTORY", "EMPLOYEES_FACTORY", "PRODUCTION"}

EXCLUDED_LOW_VALUE = (
    "aktie", "aktien", "analyst", "kursziel", "börsen", "boerse", "dax", "mdax",
    "aktienkurs", "deal", "angebot", "rabatt", "sale", "preisvergleich",
)

def is_low_value_company_story(item: dict) -> bool:
    t = text_of(item)
    title = norm(item.get("title", ""))
    factory = item.get("category") in FACTORY_CATEGORIES
    if factory:
        # A factory label must survive a second article-evidence check. This is
        # intentionally redundant: it protects against future classifier changes.
        if item.get("category") == "KORBACH_FACTORY" and not is_korbach_factory(item):
            return True
        if item.get("category") != "KORBACH_FACTORY" and not is_factory_story(item):
            return True
        return False
    if has_any(title, ("aktie","aktien","kursziel","analyst","börse","boerse","dax","mdax","aktienkurs")):
        return True
    if has_any(title, ("deal","rabatt","preisvergleich","angebot","sale")):
        return True
    if item.get("category") == "COMPANY" and has_any(t, EXCLUDED_LOW_VALUE):
        return True
    return False


def selection_bucket(item: dict) -> int:
    cat = item.get("category", "COMPANY")
    if cat == "KORBACH_FACTORY": return 0
    if cat in {"FACTORY_PRODUCTION", "FACTORY", "EMPLOYEES_FACTORY", "PRODUCTION"}: return 1
    if cat == "CONTINENTAL_TECHNOLOGY": return 2
    if cat == "CONTINENTAL_TIRE": return 3
    if cat == "TIRE_TEST": return 4
    return 5

def factory_priority(item: dict) -> tuple:
    # Within the factory tiers, prefer Korbach, then concrete production/
    # investment/closure/relocation events, then employment/general plant news.
    t = text_of(item)
    action = 0
    for n, words in enumerate((
        ("produktion", "fertigung", "produktionslinie", "produktionsanlage"),
        ("investition", "ausbau", "erweiterung", "modernisierung"),
        ("schließung", "schliessung", "verlagerung", "stellenabbau"),
        ("mitarbeiter", "beschäftigte", "beschaeftigte", "betriebsrat"),
    ), start=4):
        if has_any(t, words):
            action = max(action, n)
    return (bool(item.get("korbach_priority")), action, item.get("score", 0), item.get("published_at", ""))

def choose_events(candidates: list[dict], seen: dict[str, str]) -> list[dict]:
    # Bootstrap builds the full archive; normal mode produces the editorial top 12.
    respect_seen = not BOOTSTRAP

    candidates = [x for x in candidates if not is_low_value_company_story(x)]
    candidates.sort(key=lambda x: (selection_bucket(x), not bool(x.get("korbach_priority")), -x.get("score", 0), x.get("published_at", "")), reverse=False)

    groups: list[dict] = []
    for item in candidates:
        eid = event_id(item)
        if respect_seen and eid in seen:
            continue

        matched = None
        for g in groups:
            # Never let a Korbach factory story merge with a non-Korbach story.
            if item.get("korbach_priority") or g.get("korbach_priority"):
                if not (item.get("korbach_priority") and g.get("korbach_priority")):
                    continue
                if "korbach" not in text_of(item) or "korbach" not in text_of(g):
                    continue
                shared = article_fingerprint(item) & article_fingerprint(g)
                if len(shared) < 3 or event_similarity(item, g) < 0.60:
                    continue
            if same_event(item, g):
                matched = g
                break

        if matched is not None:
            matched.setdefault("alternate_sources", []).append({
                "source": item["source"], "title": item["title"],
                "url": item["url"], "published_at": item["published_at"],
            })
            if (item["score"], item["published_at"]) > (matched["score"], matched["published_at"]):
                old_rep = {k: matched[k] for k in ("source", "title", "url", "published_at")}
                matched.update({k: item[k] for k in ("source", "title", "url", "published_at", "summary", "score", "category", "event_family")})
                matched["alternate_sources"].append(old_rep)
            continue

        item["event_id"] = eid
        item["alternate_sources"] = []
        groups.append(item)

    if BOOTSTRAP:
        # Archive: keep up to 250 genuinely different events, factory-first.
        groups.sort(key=lambda x: (selection_bucket(x), not bool(x.get("korbach_priority")), -x.get("score", 0), x.get("published_at", "")), reverse=False)
        return groups[:BOOTSTRAP_MAX_EVENTS]

    # Normal editorial mix: quotas prevent generic tire/company news from
    # crowding out factories. Quotas are ceilings, not requirements.
    korbach = sorted((g for g in groups if g.get("category") == "KORBACH_FACTORY"), key=factory_priority, reverse=True)
    factory = sorted((g for g in groups if g.get("category") in FACTORY_CATEGORIES and g.get("category") != "KORBACH_FACTORY"), key=factory_priority, reverse=True)
    tech = sorted((g for g in groups if g.get("category") == "CONTINENTAL_TECHNOLOGY"), key=lambda x: (x.get("score",0), x.get("published_at","")), reverse=True)
    tire = sorted((g for g in groups if g.get("category") == "CONTINENTAL_TIRE"), key=lambda x: (x.get("score",0), x.get("published_at","")), reverse=True)
    tests = sorted((g for g in groups if g.get("category") == "TIRE_TEST"), key=lambda x: (x.get("score",0), x.get("published_at","")), reverse=True)
    company = sorted((g for g in groups if g.get("category") == "COMPANY"), key=lambda x: (x.get("score",0), x.get("published_at","")), reverse=True)

    selected: list[dict] = []
    def take(pool, n):
        for x in pool:
            if x not in selected and len(selected) < MAX_EVENTS and n > 0:
                selected.append(x); n -= 1

    take(korbach, 6)
    take(factory, 4)
    take(tech, 1)
    take(tire, 1)
    take(tests, 1)
    take(company, 1)

    # If the preferred mix has fewer than 12 events, fill remaining slots from
    # all remaining non-low-value events, still respecting the factory-first order.
    if len(selected) < MAX_EVENTS:
        remaining = [g for g in groups if g not in selected]
        remaining.sort(key=lambda x: (selection_bucket(x), not bool(x.get("korbach_priority")), -x.get("score",0), x.get("published_at","")))
        for x in remaining:
            if len(selected) >= MAX_EVENTS:
                break
            selected.append(x)

    # Final presentation order is editorial: Korbach -> other factories -> tech -> tire -> test -> company.
    selected.sort(key=lambda x: (selection_bucket(x), not bool(x.get("korbach_priority")), -x.get("score",0), x.get("published_at","")))
    return selected[:MAX_EVENTS]




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
    print("=== Continental WhatsApp Channel News v5.6 FACTORY-FIRST ===")
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
