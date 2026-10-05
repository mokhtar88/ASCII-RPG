"""Unique, non-repeatable quest generation from book lore.

Six kinds:
  deliver - carry word to a city (complete via E in target city)
  bounty  - slay a named bandit (complete on kill)
  explore - discover a dungeon site (complete by stepping on it)
  escort  - see a companion safely to a city (complete by entering it)
  hunt    - slay N foes anywhere (progress counts kills)
  tribute - bring gold to a city (complete via E there, deducts gold)

Every quest gets a stable id (kind + slug). Completed ids are stored on the
world so regen/refresh never offers the same quest twice.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, asdict


@dataclass
class Quest:
    id: str
    kind: str  # deliver | bounty | explore | escort | hunt | tribute | relic | finale
    title: str
    giver: str
    target_city: str = ""
    target_enemy: str = ""
    target_site: str = ""
    flavor: str = ""
    reward_gold: int = 15
    reward_xp: int = 25
    # hunt: amount = raiders to slay, progress = slain. tribute: amount = gold.
    progress: int = 0
    amount: int = 0
    # escort: who follows you.
    companion: str = ""
    # escort: companion hurt carried in the save (0 = hale; max derives from hero level).
    comp_hp: int = 0
    # main-tale act (0 = side rumor).
    act: int = 0
    # urgent: absolute day number by which to finish (0 = whenever).
    deadline_day: int = 0
    # treasure: buried coordinates.
    target_x: int = -1
    target_y: int = -1
    # book saga: "" = standalone; else "saga-N" shared by its I/II/III parts.
    saga: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Quest":
        # tolerate legacy saves that only had title/giver/target_city/flavor
        if "id" not in d:
            slug = re.sub(r"[^a-z0-9]+", "-", d.get("title", "quest").lower()).strip("-")
            d = {**d, "id": f"deliver-{slug}", "kind": "deliver",
                 "target_enemy": "", "target_site": "",
                 "reward_gold": 15, "reward_xp": 25}
        return Quest(**{k: d.get(k, getattr(Quest, k, "")) for k in
                        ("id", "kind", "title", "giver", "target_city",
                         "target_enemy", "target_site", "flavor",
                         "reward_gold", "reward_xp", "progress", "amount",
                         "companion", "comp_hp", "act", "deadline_day", "target_x", "target_y",
                         "saga")})


def _slug(*parts: str) -> str:
    base = "-".join(parts).lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60]


# Every verb speaks in several voices; builders pick one.
FLAVOR = {
    "deliver": [
        "{giver} of {home} asks you to carry word of the {term} to {target}.",
        "{giver} seals a letter with shaking hands: the {term} must reach {target}.",
        "For a handful of coin, {giver} wants the {term} sung in {target} — discreetly.",
    ],
    "bounty": [
        "{giver} of {home} wants {foe} stopped. Find their band (E) and end it.",
        "{giver} has counted the cost of {foe} and will pay it in gold. Permanently.",
        "Someone should do something about {foe}, says {giver}. That someone is you.",
    ],
    "explore": [
        "{giver} begs you to uncover the secret of the {term} at {place}. Seek it out.",
        "{giver} dreamed of {place} three nights running. Go and see what squats there.",
        "Maps disagree about {place}. {giver} pays for certainty — and proof.",
    ],
    "escort": [
        "{giver} pays you to see {comp} safely to {target}. They follow you.",
        "{comp} must reach {target} breathing, says {giver}. Walk with them.",
    ],
    "hunt": [
        "{giver} of {home} wants {n} {foe} raiders slain. Any red blade (E) counts.",
        "The {foe} grow bold near {home}. {giver} wants {n} of them bled out.",
    ],
    "tribute": [
        "{giver} demands {due} gold tribute for {target}. Pay it there (E).",
        "{target} eats, says {giver}, and the price is {due} gold. Take it there.",
    ],
    "pilgrimage": [
        "{giver} asks {n} shrine prayers for a dying kin. Kneel (E) at each.",
        "Someone {giver} loves is fading. {n} shrines, {n} prayers. Go.",
    ],
    "treasure": [
        "{giver} buried it all and drew this map. Stand on the X.",
        "{giver} trusts you with a thief's honesty: the cache is real. Dig with your boots.",
    ],
}

BARKS = [
    "Mind the roads past dark.",
    "The wells went brackish before the troubles. Mark that.",
    "I knew the old {place}. Knew it well.",
    "Coin first, tales after. House rules.",
    "You have the look of someone the songs argue about.",
    "Nothing stirs beyond the walls. Nothing good, anyway.",
]


def build_quests(characters: list, cities: list, dungeons: list,
                 terms: list[str], flavor_lines: list[str],
                 rng: random.Random, exclude: set[str] | None = None,
                 count: int = 12, factions: list | None = None,
                 city_faction: dict | None = None,
                 grid: list | None = None) -> list[Quest]:
    exclude = exclude or set()
    factions = factions or []
    city_faction = city_faction or {}
    wars: dict[str, list[str]] = {}
    for f in factions:
        wars[getattr(f, "id", "")] = list(getattr(f, "at_war", []))
    non_bandits = [c for c in characters if c.role != "bandit"] or list(characters)
    bandits = [c for c in characters if c.role == "bandit"]
    if not cities and not dungeons and not bandits:
        return []
    fallback_terms = ["relic", "map", "blade", "oath", "crown", "lantern", "seal"]

    combos: list[Quest] = []
    # deliver quests: giver -> city
    for giver in non_bandits:
        for city in cities:
            if city.name == giver.city:
                continue
            term = rng.choice(terms) if terms else rng.choice(fallback_terms)
            qid = f"deliver-{_slug(giver.name, city.name)}"
            combos.append(Quest(
                id=qid, kind="deliver",
                title=f"Word of the {term.capitalize()} for {city.name}",
                giver=giver.name, target_city=city.name,
                flavor=rng.choice(FLAVOR["deliver"]).format(
                    giver=giver.name, home=giver.city, term=term, target=city.name),
                reward_gold=rng.randint(12, 22), reward_xp=rng.randint(20, 35)))
    # bounty quests: named bandit holed up in the nearest dungeon (their lair)
    def _lair_for(home_city: str) -> str:
        home = next((c for c in cities if c.name == home_city), None)
        dens = [d for d in dungeons if getattr(d, "kind", "dungeon") == "dungeon"]
        pool = dens or list(dungeons)
        if home and pool:
            return min(pool, key=lambda d: abs(d.x - home.x) + abs(d.y - home.y)).name
        return pool[0].name if pool else ""
    for giver in non_bandits:
        for b in bandits:
            qid = f"bounty-{_slug(b.name)}"
            lair = _lair_for(giver.city)
            gf = city_faction.get(giver.city, "")
            foes = wars.get(gf, [])
            if foes and rng.random() < 0.5:
                foe = rng.choice(foes)
                flavor = (f"{giver.name} of {giver.city} names {b.name} a {foe} war-hound. "
                          f"End them{' in ' + lair if lair else ''} for the war effort.")
            else:
                flavor = (f"{giver.name} of {giver.city} wants {b.name} stopped."
                          f"{' They lurk in ' + lair + '.' if lair else ' Find their band (E) and end it.'}")
            combos.append(Quest(
                id=qid, kind="bounty",
                title=f"Bounty: {b.name}",
                giver=giver.name, target_enemy=b.name, target_site=lair,
                flavor=flavor,
                reward_gold=rng.randint(18, 30), reward_xp=rng.randint(35, 55)))
    # explore quests: dungeon sites
    for giver in non_bandits:
        for d in dungeons:
            term = rng.choice(terms) if terms else rng.choice(fallback_terms)
            qid = f"explore-{_slug(d.name)}"
            combos.append(Quest(
                id=qid, kind="explore",
                title=f"Uncover {d.name}",
                giver=giver.name, target_site=d.name,
                flavor=rng.choice(FLAVOR["explore"]).format(
                    giver=giver.name, term=term, place=d.name),
                reward_gold=rng.randint(10, 18), reward_xp=rng.randint(25, 40)))
    # escort quests: walk a companion to another city (complete on entry)
    for giver in non_bandits:
        others = [c.name for c in non_bandits
                  if c.city == giver.city and c.name != giver.name]
        for city in cities:
            if city.name == giver.city:
                continue
            comp = rng.choice(others) if others else giver.name
            qid = f"escort-{_slug(comp, city.name)}"
            combos.append(Quest(
                id=qid, kind="escort",
                title=f"Guide {comp} to {city.name}",
                giver=giver.name, target_city=city.name, companion=comp,
                flavor=rng.choice(FLAVOR["escort"]).format(
                    giver=giver.name, comp=comp, target=city.name),
                reward_gold=rng.randint(14, 24), reward_xp=rng.randint(25, 40)))
    # hunt quests: cull N raiders of a hostile faction (any foe kill counts)
    foe_names = [getattr(f, "name", "") for f in factions] or ["bandit"]
    for giver in non_bandits:
        gf = city_faction.get(giver.city, "")
        foes = wars.get(gf, []) or [n for n in foe_names if n != gf] or foe_names
        foe = rng.choice(foes)
        need = rng.randint(3, 5)
        qid = f"hunt-{_slug(giver.name, foe)}"
        combos.append(Quest(
            id=qid, kind="hunt",
            title=f"Cull {need} {foe} raiders",
            giver=giver.name, target_enemy=foe, amount=need,
            flavor=rng.choice(FLAVOR["hunt"]).format(
                    giver=giver.name, home=giver.city, n=need, foe=foe),
            reward_gold=rng.randint(16, 26), reward_xp=rng.randint(30, 50)))
    # tribute quests: bring gold to a city (complete via E there)
    for giver in non_bandits:
        for city in cities:
            if city.name == giver.city:
                continue
            due = rng.randint(30, 80)
            qid = f"tribute-{_slug(giver.name, city.name)}"
            combos.append(Quest(
                id=qid, kind="tribute",
                title=f"Tribute of {due}g for {city.name}",
                giver=giver.name, target_city=city.name, amount=due,
                flavor=rng.choice(FLAVOR["tribute"]).format(
                    giver=giver.name, target=city.name, due=due),
                reward_gold=rng.randint(5, 10), reward_xp=rng.randint(25, 40)))
    # pilgrimage quests: pray at N shrines (progress on each visit)
    shrines = [d for d in dungeons if getattr(d, "kind", "") == "shrine"]
    if shrines:
        for giver in non_bandits:
            need = min(3, max(2, len(shrines)))
            qid = f"pilgrim-{_slug(giver.name)}"
            combos.append(Quest(
                id=qid, kind="pilgrimage",
                title=f"Pilgrimage of {need} Shrines",
                giver=giver.name, amount=need,
                flavor=rng.choice(FLAVOR["pilgrimage"]).format(giver=giver.name, n=need),
                reward_gold=rng.randint(15, 25), reward_xp=rng.randint(30, 50)))
    # treasure quests: a cache buried at real coordinates, described by landmark
    if grid:
        WALK = {".", "T", "s", "r", "=", "O", "D", "#", "*"}
        for giver in non_bandits:
            home = next((c for c in cities if c.name == giver.city), None)
            hx, hy = (home.x, home.y) if home else (0, 0)
            for _ in range(30):
                tx = hx + rng.randint(-60, 60)
                ty = hy + rng.randint(-60, 60)
                dist = abs(tx - hx) + abs(ty - hy)
                if not (20 <= dist <= 90):
                    continue
                if not (0 <= tx < len(grid[0]) and 0 <= ty < len(grid)):
                    continue
                if grid[ty][tx] not in WALK:
                    continue
                mark = min(cities, key=lambda c: abs(c.x - tx) + abs(c.y - ty)) if cities else None
                if mark is None:
                    continue
                dx, dy = tx - mark.x, ty - mark.y
                horiz = "east" if dx > 0 else "west" if dx < 0 else ""
                vert = "south" if dy > 0 else "north" if dy < 0 else ""
                qid = f"treasure-{_slug(giver.name, mark.name)}"
                combos.append(Quest(
                    id=qid, kind="treasure",
                    title=f"Cache {dist} Leagues {vert}{horiz} of {mark.name}",
                    giver=giver.name, target_x=tx, target_y=ty,
                    flavor=(f"{giver.name} buried it all {dist} leagues {vert}{horiz} of "
                            f"{mark.name} and drew this map. Stand on the X."),
                    reward_gold=rng.randint(20, 35), reward_xp=rng.randint(30, 50)))
                break
    # lore-flavored extras
    for fl in flavor_lines[:6]:
        if cities:
            city = rng.choice(cities)
            giver = rng.choice(non_bandits)
            qid = f"lore-{_slug(fl[:40])}"
            combos.append(Quest(
                id=qid, kind="deliver",
                title=f"Echoes over {city.name}",
                giver=giver.name, target_city=city.name,
                flavor=f"Tale tells: '{fl[:140]}' {giver.name} seeks proof near {city.name}.",
                reward_gold=rng.randint(12, 20), reward_xp=rng.randint(20, 30)))

    rng.shuffle(combos)
    # round-robin across kinds so the log is always mixed, never 12 deliveries
    by_kind: dict[str, list[Quest]] = {}
    for q in combos:
        by_kind.setdefault(q.kind, []).append(q)
    for v in by_kind.values():
        rng.shuffle(v)
    out, seen = [], set()
    kinds_cycle = [k for k in ("deliver", "bounty", "explore", "escort",
                                "hunt", "tribute", "pilgrimage", "treasure",
                                "lore") if k in by_kind]
    idx = 0
    while len(out) < count and any(by_kind.values()):
        kind = kinds_cycle[idx % len(kinds_cycle)]
        idx += 1
        bucket = by_kind.get(kind, [])
        while bucket:
            q = bucket.pop(0)
            if q.id in exclude or q.id in seen:
                continue
            seen.add(q.id)
            out.append(q)
            break
        else:
            continue
        if len(out) >= count:
            break
    return out
