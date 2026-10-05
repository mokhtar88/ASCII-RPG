"""Mutate extracted names so the world feels unique, not copied."""
from __future__ import annotations

import random

VOWELS = "aeiou"
CONSONANTS = "bcdfghklmnprstvwz"

SUFFIXES = ["dor", "mar", "wyn", "thor", "glen", "holm", "ford", "burg", "wick",
            "shire", "mere", "fall", "crest", "helm", "gar", "ric", "lan", "mir"]
PREFIXES = ["Al", "Bel", "Cor", "Dal", "Eld", "Fal", "Gal", "Har", "Kel", "Mor",
            "Nor", "Ost", "Rav", "Tor", "Vel", "Wyn"]

FALLBACK_CITY_STEMS = ["Ald", "Bren", "Cal", "Dun", "Esh", "Fell", "Glim", "Harth",
                       "Iln", "Kel", "Lorn", "Mith", "Nol", "Ostr", "Pell", "Rath"]
FALLBACK_NAME_STEMS = ["Ara", "Bel", "Cas", "Dor", "Elen", "Fen", "Gor", "Hal",
                       "Is", "Jor", "Kael", "Lira", "Marek", "Nyra", "Orin", "Sella"]


def _mutate_token(token: str, rng: random.Random) -> str:
    if len(token) < 3:
        return token
    # Very short roots (Men, Orc...) read best with a suffix, not mangling.
    if len(token) <= 4:
        return token + rng.choice(SUFFIXES).lower()
    chars = list(token)
    # Keep the first letter stable so names stay recognizable/pronounceable.
    op = rng.choice(["vowel_shift", "consonant_tweak", "swap", "suffix", "suffix"])
    if op == "vowel_shift":
        for i in range(1, len(chars)):
            ch = chars[i]
            if ch.lower() in VOWELS and rng.random() < 0.6:
                new_v = rng.choice(VOWELS)
                chars[i] = new_v.upper() if ch.isupper() else new_v
    elif op == "consonant_tweak":
        for i in range(1, len(chars)):
            ch = chars[i]
            if ch.lower() in CONSONANTS and rng.random() < 0.25:
                new_c = rng.choice(CONSONANTS)
                chars[i] = new_c.upper() if ch.isupper() else new_c
    elif op == "swap":
        if len(chars) >= 6:
            i = rng.randrange(1, len(chars) - 1)
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
    elif op == "suffix":
        stem = "".join(chars)
        return stem + rng.choice(SUFFIXES).lower()
    elif op == "prefix":
        stem = "".join(chars)
        return rng.choice(PREFIXES) + stem.lower()
    return "".join(chars)


def mutate_name(name: str, rng: random.Random) -> str:
    """Mutate each word in a name, guaranteeing a change."""
    parts = name.split()
    out = []
    for p in parts:
        # keep titles (King, Lord...) readable
        if p.lower() in {"king", "queen", "lord", "lady", "sir", "captain", "prince", "princess"}:
            out.append(p)
            continue
        mutated = _mutate_token(p, rng)
        if mutated.lower() == p.lower():
            mutated = p + rng.choice(SUFFIXES).lower()[:3]
        # Preserve capitalization
        if p[0].isupper():
            mutated = mutated[0].upper() + mutated[1:]
        out.append(mutated)
    result = " ".join(out)
    if result.lower() == name.lower():
        result = name + rng.choice(["ia", "or", "en"])
    return result


def unique_names(base: list[str], count: int, rng: random.Random,
                 fallback_stems: list[str] | None = None) -> list[str]:
    """Produce `count` unique mutated names from base list + fallback generator."""
    seen: set[str] = set()
    result: list[str] = []
    stems = fallback_stems or FALLBACK_CITY_STEMS
    pool = list(base)
    rng.shuffle(pool)
    i = 0
    guard = 0
    while len(result) < count and guard < count * 50:
        guard += 1
        if i < len(pool):
            raw = pool[i]
            i += 1
        else:
            stem = rng.choice(stems)
            raw = stem if rng.random() < 0.5 else stem + rng.choice(SUFFIXES)
        mutated = mutate_name(raw, rng)
        key = mutated.lower()
        if key not in seen:
            seen.add(key)
            result.append(mutated)
    return result
