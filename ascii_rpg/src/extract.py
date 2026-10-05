"""Lightweight lore extraction without heavy NLP deps.

Strategy: proper-noun candidates via regex, ranked by frequency,
classified by surrounding context keywords into people / places / groups.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\b")

STOPWORDS = {
    "The", "This", "That", "These", "Those", "There", "Here", "When", "Where",
    "Which", "While", "After", "Before", "Because", "However", "Although",
    "Chapter", "Part", "Page", "Book", "Volume", "Then", "Thus", "And", "But",
    "For", "With", "From", "Into", "Over", "Under", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "June", "July", "August",
    "September", "October", "November", "December", "His", "Her", "Their",
    "Your", "Our", "Its", "She", "You", "They", "One", "Two", "Three",
    "Chronicle", "King", "Queen", "Lord", "Lady", "Captain", "Prince",
    "Princess", "Master", "Sir",
}

LEADING_ARTICLES_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

KNOWN_GROUPS = {
    "elves", "dwarves", "dwarf", "orcs", "orc", "men", "humans", "human",
    "elvesfolk", "fae", "goblins", "goblin", "trolls", "undead", "gods",
}

PLACE_HINTS = {
    "city", "town", "village", "kingdom", "land", "empire", "castle", "port",
    "realm", "province", "harbor", "harbour", "forest", "mountain", "river",
    "island", "desert", "capital", "fort", "shire", "hold", "gate", "wall",
    "tower", "bridge", "valley", "bay", "coast", "docks", "market", "temple",
    "of", "in", "from", "to", "at", "near",
}

PERSON_HINTS = {
    "said", "asked", "replied", "shouted", "whispered", "cried", "laughed",
    "king", "queen", "lord", "lady", "sir", "captain", "prince", "princess",
    "wizard", "witch", "knight", "master", "brother", "sister", "father",
    "mother", "son", "daughter", "he", "she", "his", "her", "him",
}

GROUP_HINTS = {
    "people", "tribe", "clan", "race", "folk", "army", "horde", "order",
    "guild", "council", "men", "women", "children", "warriors", "soldiers",
    "elves", "dwarves", "orcs", "gods",
}


@dataclass
class Lore:
    people: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)  # frequent lore nouns
    flavor_lines: list[str] = field(default_factory=list)
    relic_words: list[str] = field(default_factory=list)  # name-safe nouns
    book_events: list = field(default_factory=list)  # {kind, names, snippet}


TITLES_LOW = {"king", "queen", "lord", "lady", "sir", "captain", "prince",
              "princess", "master", "chronicle"}


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20][:5000]


def extract_entities(text: str, top_n: int = 40) -> Lore:
    lore = Lore()
    if not text or not text.strip():
        return lore

    candidates = PROPER_NOUN_RE.findall(text)
    # Normalize whitespace, drop stopwords / single common words
    cleaned: list[str] = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        c = LEADING_ARTICLES_RE.sub("", c).strip()
        if not c:
            continue
        words = c.split()
        if any(w in STOPWORDS for w in words):
            # Allow "King Aldor" style but drop lone "The"
            if len(words) == 1:
                continue
        if len(c) < 3:
            continue
        cleaned.append(c)

    freq = Counter(cleaned)
    # Drop single words that ONLY ever appear as the first word of a sentence
    # (e.g. "Beyond the forest..." -> "Beyond" is not a name).
    non_initial: Counter = Counter()
    for m in PROPER_NOUN_RE.finditer(text):
        raw = re.sub(r"\s+", " ", m.group(0)).strip()
        cand = LEADING_ARTICLES_RE.sub("", raw).strip()
        if not cand or " " in cand:
            continue  # multi-word names are rarely sentence-start artifacts
        prefix = text[max(0, m.start() - 3):m.start()]
        if not re.search(r"(^|[.!?]\s*)$", prefix):
            non_initial[cand] += 1
    ranked = [name for name, _ in freq.most_common(top_n * 3)
              if " " in name or freq[name] > 1 or non_initial.get(name, 0) > 0]

    sentences = _split_sentences(text)
    # index sentences containing each candidate for context + flavor
    sent_index: dict[str, list[str]] = {name: [] for name in ranked}
    lower_sents = [s.lower() for s in sentences]
    for name in ranked:
        nl = name.lower()
        for s, ls in zip(sentences, lower_sents):
            if nl in ls:
                sent_index[name].append(s)
                if len(sent_index[name]) >= 5:
                    break

    people, places, groups = [], [], []
    for name in ranked:
        first = name.split()[0].lower() if name.split() else ""
        if first in {"king", "queen", "lord", "lady", "sir", "captain",
                     "prince", "princess", "master"}:
            if name not in people:
                people.append(name)
            continue
        contexts = " ".join(sent_index.get(name, [])).lower()
        words = set(re.findall(r"[a-z]+", contexts))
        # Known fantasy peoples always count as groups
        if name.lower() in KNOWN_GROUPS or name.lower().rstrip("s") in KNOWN_GROUPS:
            if name not in groups:
                groups.append(name)
            continue
        place_score = len(words & PLACE_HINTS)
        # boost if preceded by "city of X" pattern in raw text
        if re.search(r"(city|town|village|kingdom|land|empire|castle|port|realm)\s+of\s+" + re.escape(name),
                     text, re.IGNORECASE):
            place_score += 3
        # boost if "X castle / X city" pattern
        if re.search(re.escape(name) + r"\s+(city|town|castle|port|forest|river|mountain|kingdom|gate|wall|tower)",
                     text, re.IGNORECASE):
            place_score += 2
        person_score = len(words & PERSON_HINTS)
        if re.search(r"(King|Queen|Lord|Lady|Sir|Captain|Prince|Princess|Master)\s+" + re.escape(name.split()[-1]), text):
            person_score += 3
        group_score = len(words & GROUP_HINTS)
        if name.endswith("s") and len(name.split()) == 1:
            group_score += 1

        # Multi-word names default to people unless place signals dominate
        if place_score >= 2 and place_score >= person_score:
            if name not in places:
                places.append(name)
        elif person_score >= 1 or len(name.split()) > 1:
            if name not in people:
                people.append(name)
        elif group_score >= 1:
            if name not in groups:
                groups.append(name)
        else:
            # single-word unknowns: alternate to keep pools filled
            if len(places) <= len(people):
                places.append(name)
            else:
                people.append(name)

        if len(people) >= top_n and len(places) >= top_n // 2:
            break

    # frequent lowercase lore nouns (magic, sword, dragon...)
    words = re.findall(r"[a-z]{4,}", text.lower())
    common = Counter(words)
    boring = {"that", "this", "with", "from", "have", "were", "been", "they",
              "them", "then", "than", "when", "what", "where", "there", "here",
              "would", "could", "should", "your", "their", "about", "into",
              "ruled", "said", "asked", "replied", "whispered", "shouted",
              "cried", "laughed", "traveled", "carried", "knew", "met",
              "spoke", "promised", "guard", "king", "queen", "city",
              "kingdom", "lord", "captain"}
    terms = [w for w, _ in common.most_common(60) if w not in boring][:20]

    # flavor lines: sentences mentioning top people/places
    flavor = []
    top_keys = (people[:8] + places[:8]) or ranked[:8]
    for s in sentences:
        sl = s.lower()
        if any(k.lower() in sl for k in top_keys):
            flavor.append(s.strip()[:220])
            if len(flavor) >= 30:
                break

    lore.people = people[:top_n]
    lore.places = places[: max(10, top_n // 2)]
    lore.groups = groups[:10]
    lore.terms = terms
    lore.flavor_lines = flavor
    # relic words: name-safe NOUNS only (entity fragments + curated fallbacks).
    # This is the pool for blades, rings, foes, and spells — never verbs.
    seen: set[str] = set()
    relics: list[str] = []
    for ent in lore.people + lore.places + lore.groups:
        for tok in re.findall(r"[A-Za-z]{4,}", ent):
            word = tok.capitalize()
            if word in STOPWORDS or word.lower() in TITLES_LOW:
                continue
            if word.lower() not in seen:
                seen.add(word.lower())
                relics.append(word)
    lore.relic_words = relics[:24]
    lore.book_events = extract_book_events(text)
    return lore


# ---------------- book-event mining ----------------
# Verb-frame extraction: happenings in the books become {kind, names, snippet}
# events that feed quest seeds, history seeds, and the director deck.
# Frequency voting over single parses: common kinds rank first.

BOOK_EVENT_FRAMES: dict[str, list[str]] = {
    "battle": [r"\bslew\b", r"\bslay\b", r"\bslays\b", r"\bslain\b",
               r"\bbattle\b", r"\bfought\b", r"\bfight\b", r"\bkilled\b",
               r"\bkill\b", r"\bwar\b"],
    "siege": [r"\bsiege\b", r"\bbesieged\b", r"\bsacked\b", r"\bsack\b",
              r"\bstormed\b", r"\brazed\b"],
    "exodus": [r"\bfled\b", r"\bflee\b", r"\bflees\b", r"\bexile\b",
               r"\bbanished\b", r"\bescaped\b"],
    "union": [r"\bwed\b", r"\bwedding\b", r"\bmarried\b", r"\bmarriage\b",
              r"\balliance\b", r"\bcouncil\b"],
    "betrayal": [r"\bbetrayed\b", r"\bbetray\b", r"\bbetrayal\b",
                 r"\btreason\b", r"\btreachery\b"],
    "storm": [r"\bstorm\b", r"\btempest\b", r"\bflood\b", r"\bdrought\b"],
    "plague": [r"\bplague\b", r"\bpestilence\b", r"\bfever\b", r"\bfamine\b"],
    "voyage": [r"\bvoyage\b", r"\bsailed\b", r"\bsail\b", r"\bvoyager\b",
               r"\bexpedition\b", r"\bjourney\b"],
}


def extract_book_events(text: str, limit: int = 40) -> list[dict]:
    """Mine verb-frame happenings: [{kind, names, snippet}]."""
    if not text or not text.strip():
        return []
    sents = _split_sentences(text)
    found: list[dict] = []
    pats: dict[str, list] = {}
    for kind, words in BOOK_EVENT_FRAMES.items():
        pats[kind] = [re.compile(w, re.IGNORECASE) for w in words]
    for s in sents:
        low = s.lower()
        hit = ""
        for kind, regs in pats.items():
            for rx in regs:
                if rx.search(low):
                    hit = kind
                    break
            if hit:
                break
        if not hit:
            continue
        names = []
        for m in PROPER_NOUN_RE.finditer(s):
            raw = re.sub(r"\s+", " ", m.group(0)).strip()
            cand = LEADING_ARTICLES_RE.sub("", raw).strip()
            if not cand or len(cand) < 3:
                continue
            words = cand.split()
            if len(words) == 1 and words[0] in STOPWORDS:
                continue
            if cand not in names:
                names.append(cand)
            if len(names) >= 3:
                break
        snippet = re.sub(r"\s+", " ", s.strip().replace("\x00", ""))[:220]
        if snippet:
            found.append({"kind": hit, "names": names[:3], "snippet": snippet})
        if len(found) >= 400:
            break
    # frequency voting over single parses, but keep diversity: kinds ordered
    # by count, then round-robin so the deck sees sieges and voyages too
    from collections import Counter as _C
    counts = _C(e["kind"] for e in found)
    by_kind: dict[str, list[dict]] = {}
    for e in found:
        by_kind.setdefault(e["kind"], []).append(e)
    ranked_kinds = sorted(by_kind, key=lambda k: -counts.get(k, 0))
    out: list[dict] = []
    i = 0
    while len(out) < limit and any(by_kind.values()):
        for k in ranked_kinds:
            if by_kind[k] and len(out) < limit:
                out.append(by_kind[k].pop(0))
        i += 1
        if i > limit * 2:
            break
    return out
