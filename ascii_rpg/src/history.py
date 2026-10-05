"""Deep history (phase 1 of enrichment): 800 years before play.

Simulates foundings, faction wars, battles, sacks, heroes, and artifacts so
the map is retro-explained: ruins fell for a reason, bosses have pasts,
heirlooms wait in specific dungeon chests. Pure data; quests spend it later.
"""
from __future__ import annotations

import random

EPITHETS = ["the Bold", "the Grim", "the Twice-Born", "the Oathkeeper",
            "the Red", "the Patient", "the Stormcrow", "the Unburnt",
            "One-Eye", "the Bell-Ringer", "the Last", "the Kind"]
ARTIFACT_FORMS = ["Blade", "Crown", "Seal", "Horn", "Banner", "Chalice"]


def _ev(year: int, kind: str, text: str, place: str = "",
        people: list | None = None) -> dict:
    return {"year": year, "kind": kind, "text": text, "place": place,
            "people": people or []}


def simulate(world, rng: random.Random) -> list[dict]:
    """Fill world.history, ruin backstories, and placed artifacts."""
    from .worldgen import faction_name
    events: list[dict] = []
    fnames = {f.id: faction_name(world, f.id) for f in world.factions}

    # foundings honor the cities as generated
    for c in world.cities:
        events.append(_ev(c.founded or 100, "founding",
                          f"{c.name} raised by {c.founder or 'unknown hands'}.",
                          place=c.name,
                          people=[c.founder] if c.founder else []))

    # wars between the powers, with battles and sacks
    wars_done = 0
    for f in world.factions:
        for foe in f.at_war:
            if foe < f.id:  # each pair once (ids sort the mirror away)
                continue
            for _ in range(rng.randint(1, 2)):
                start = rng.randint(120, 700)
                end = min(900, start + rng.randint(20, 120))
                events.append(_ev(start, "war",
                                  f"The {fnames.get(f.id, f.id)}-{fnames.get(foe, foe)} War begins."))
                events.append(_ev(end, "peace",
                                  f"The {fnames.get(f.id, f.id)}-{fnames.get(foe, foe)} War ends."))
                for _ in range(rng.randint(1, 3)):
                    field = rng.choice(world.cities).name if world.cities else "the field"
                    events.append(_ev(rng.randint(start, end), "battle",
                                      f"Battle of {field}: {fnames.get(f.id, f.id)} meets {fnames.get(foe, foe)}.",
                                      place=field))
                # sacked and rebuilt: scars on living cities
                if world.cities and rng.random() < 0.6:
                    victim = rng.choice(world.cities)
                    events.append(_ev(rng.randint(start, end), "sack",
                                      f"{victim.name} sacked, and rebuilt from the ash.",
                                      place=victim.name))
                wars_done += 1

    # ruins: each one fell and stayed fallen
    dungeons = [s for s in world.sites if s.kind in ("dungeon", "ruin")]
    for s in [x for x in world.sites if x.kind == "ruin"]:
        sacker = rng.choice(list(fnames.values())) if fnames else "the wilds"
        year = rng.randint(150, 850)
        fallen = s.origin_name or s.name.replace("Ruins of ", "")
        s.lore = f"Once {fallen}, sacked in {year} by {sacker}; never rebuilt."
        events.append(_ev(year, "fall", f"{fallen} falls to {sacker}; never rebuilt.",
                          place=s.name))

    # heroes: born, epithet'd, mostly slain
    pool = [c.name for c in world.characters][:12] or ["the Nameless"]
    heroes = []
    for _ in range(rng.randint(8, 14)):
        name = rng.choice(pool)
        born = rng.randint(100, 750)
        epi = rng.choice(EPITHETS)
        home = rng.choice(world.cities).name if world.cities else ""
        heroes.append((name, epi, home))
        events.append(_ev(born, "birth", f"{name} {epi} born" + (f" in {home}." if home else ".")))
        if rng.random() < 0.7:
            events.append(_ev(min(900, born + rng.randint(20, 120)), "death",
                              f"{name} {epi} falls" + (f" near {home}." if home else "."),
                              place=home, people=[name]))

    # artifacts: forged, lost, waiting in specific dungeon chests
    artifacts = []
    terms = world.lore_terms[:8] or ["ember"]
    for i in range(min(4, max(2, len(dungeons) // 2))):
        if not dungeons:
            break
        form = rng.choice(ARTIFACT_FORMS)
        term = terms[i % len(terms)].capitalize()
        name = f"The {term} {form}"
        forged = rng.randint(120, 600)
        home = dungeons[i % len(dungeons)].name
        events.append(_ev(forged, "forging", f"{name} forged."))
        lost = min(900, forged + rng.randint(30, 200))
        events.append(_ev(lost, "loss", f"{name} lost in {home}.", place=home))
        artifacts.append({"name": name, "dungeon": home, "claimed": False,
                          "year": forged})
    world.artifacts = artifacts

    # book-mined happenings seed the annals (frequency-voted, capped)
    try:
        mined = list(getattr(world, "book_events", []) or [])[:20]
        city_names = {c.name for c in world.cities}
        site_names = {s.name for s in world.sites}
        for b in mined:
            kind = str(b.get("kind", "tale")) or "tale"
            names = [str(x) for x in b.get("names", []) if x][:2]
            snip = str(b.get("snippet", ""))[:160]
            if not snip:
                continue
            place = ""
            for n in names:
                if n in city_names or n in site_names:
                    place = n
                    break
                for cn in city_names:
                    if n.lower() in cn.lower() or cn.lower() in n.lower():
                        place = cn
                        break
                if place:
                    break
            year = rng.randint(120, 850)
            text = snip if len(snip) > 20 else f"Old {kind}: {', '.join(names) or 'nameless'}."
            events.append(_ev(year, kind, text, place=place, people=names))
    except Exception:
        pass
    events.sort(key=lambda e: (e["year"], e["kind"]))
    world.history = events[-220:]
    return world.history


def events_at(world, place_name: str) -> list[dict]:
    return [e for e in world.history if e.get("place") == place_name]


def boss_legend(world, rng: random.Random) -> str:
    """A past for the thing in the dark: died at a real battle, or old hate."""
    battles = [e for e in world.history if e["kind"] in ("battle", "sack", "fall")]
    if battles:
        b = rng.choice(battles)
        return f"who broke at {b['text'].split(':')[0].replace('Battle of ', '')} in {b['year']}"
    if world.history:
        b = rng.choice(world.history)
        return f"bound here since {b['year']}"
    return "older than the stones"
