"""Perk drafts: a world-rolled pool of ~30 concrete perks from 17 frames.

Every 5th level earns one draft: 3 class-weighted offers + 1 wild. Pick one,
the rest dissolve back into the pool (they may surface again). Repeats stack
to rank III. The pool is a pure function of world seed + lore terms: stable
across loads, zero save space. Taken perks persist as world-stable ids.
"""
from __future__ import annotations

import random

# frame, class tag, min draft level, magnitude band (rolled per world variant)
FRAMES = [
    # martial
    {"frame": "thorns", "tag": "martial", "min_level": 5, "mag": (2, 4),
     "noun": "Thorns", "flavor": "Replies bite back."},
    {"frame": "steady", "tag": "martial", "min_level": 5, "mag": (8, 12),
     "noun": "Hands", "flavor": "Heavy swings land surer (+acc%)."},
    {"frame": "windrunner", "tag": "martial", "min_level": 10, "mag": (1, 1),
     "noun": "Wind", "flavor": "Heavies never leave you winded."},
    {"frame": "bulwark", "tag": "martial", "min_level": 5, "mag": (8, 12),
     "noun": "Wall", "flavor": "Your guard drinks deeper (-reply%)."},
    {"frame": "executioner", "tag": "martial", "min_level": 10, "mag": (2, 4),
     "noun": "Edge", "flavor": "The wounded (<35%) bleed extra."},
    {"frame": "keeneye", "tag": "martial", "min_level": 5, "mag": (2, 4),
     "noun": "Eye", "flavor": "Crits come easier (+%)."},
    {"frame": "fleetfoot", "tag": "martial", "min_level": 5, "mag": (6, 10),
     "noun": "Stride", "flavor": "Flight favors you (+flee%)."},
    {"frame": "fletcher", "tag": "martial", "min_level": 5, "mag": (3, 5),
     "noun": "Quiver", "flavor": "Quivers stuff fuller (+arrows)."},
    # spellish
    {"frame": "mendpower", "tag": "spell", "min_level": 5, "mag": (2, 4),
     "noun": "Mending", "flavor": "Mend knits deeper (+hp)."},
    {"frame": "emberwake", "tag": "spell", "min_level": 5, "mag": (1, 2),
     "noun": "Wake", "flavor": "Your burns burn longer (+turns)."},
    {"frame": "manafont", "tag": "spell", "min_level": 5, "mag": (5, 8),
     "noun": "Font", "flavor": "A deeper well (+max mana, +regen)."},
    # wild
    {"frame": "scavenger", "tag": "wild", "min_level": 5, "mag": (4, 8),
     "noun": "Eyes", "flavor": "The slain drop richer (+loot%)."},
    {"frame": "ruinlord", "tag": "wild", "min_level": 10, "mag": (1, 1),
     "noun": "Delve", "flavor": "Ruin chests pay double gold, better steel."},
    {"frame": "beastfriend", "tag": "wild", "min_level": 15, "mag": (1, 1),
     "noun": "Scent", "flavor": "Beasts and spiders sleep till provoked."},
    {"frame": "warprofiteer", "tag": "wild", "min_level": 5, "mag": (1, 2),
     "noun": "Tide", "flavor": "War-kills turn the tide harder (+)."},
    {"frame": "bloodprice", "tag": "wild", "min_level": 10, "mag": (60, 80),
     "noun": "Price", "flavor": "Teaches Bloodprice: half your blood for ruin."},
    {"frame": "hoarder", "tag": "wild", "min_level": 5, "mag": (8, 12),
     "noun": "Pack", "flavor": "The pack holds more (+slots)."},
    {"frame": "slip", "tag": "wild", "min_level": 5, "mag": (6, 10),
     "noun": "Shadow", "flavor": "Replies sometimes miss outright (+%)."},
    {"frame": "windfall", "tag": "wild", "min_level": 5, "mag": (60, 100),
     "noun": "Fortune", "flavor": "Take-time tribute in gold."},
]

RANKS = ("", "-ii", "-iii")


def _term(terms: list[str], rng: random.Random) -> str:
    pool = [t.capitalize() for t in terms[:16] if t] or ["Ember"]
    return rng.choice(pool)


def gen_pool(seed: int, terms: list[str]) -> list[dict]:
    """Two lore-named variants per frame (~34 concrete perks). Deterministic."""
    rng = random.Random(seed + 717171)
    out = []
    for f in FRAMES:
        for v in range(2):
            lo, hi = f["mag"]
            mag = lo if lo == hi else rng.randint(lo, hi)
            name = f"{_term(terms, rng)}{f['noun'].lower()}" if v == 0 else \
                f"{_term(terms, rng)} {f['noun']}"
            out.append({"id": f"perk-{f['frame']}-{v}-{name.lower().replace(' ', '-')}",
                        "base": f["frame"], "frame": f["frame"],
                        "name": name, "mag": mag, "tag": f["tag"],
                        "min_level": f["min_level"], "flavor": f["flavor"]})
    return out


def _ranks(perks: list) -> dict:
    """Base frame -> times taken. Rank-1 ids are full pool ids
    (perk-<frame>-<variant>-<name>); later ranks ride as <base>@2/@3."""
    held: dict = {}
    for pid in perks or []:
        s = str(pid)
        if s.startswith("perk-"):
            parts = s.split("-")
            base = parts[1] if len(parts) > 2 else s
        elif "@" in s:
            base = s.split("@")[0]
        else:
            base = s
        held[base] = held.get(base, 0) + 1
    return held


def perk_rank(player, base: str) -> int:
    perks = player.perks if hasattr(player, "perks") else player.get("perks", [])
    return min(3, _ranks(perks).get(base, 0))


def perk_mag(state, base: str) -> int:
    """Magnitude of the taken variant (rank scales it); pool default if none."""
    pool = _pool_for(state)
    perks = state.player.perks if hasattr(state.player, "perks") else []
    for pid in perks or []:
        s = str(pid)
        if s.startswith("perk-"):
            hit = next((e for e in pool if e["id"] == s), None)
            if hit is not None:
                return int(hit["mag"])
    for e in pool:
        if e["base"] == base:
            return int(e["mag"])
    return 1


def has_perk(player, base: str) -> bool:
    return perk_rank(player, base) > 0


def drafts_pending(player) -> int:
    perks = player.perks if hasattr(player, "perks") else player.get("perks", [])
    drafts = player.perk_drafts if hasattr(player, "perk_drafts") else player.get("perk_drafts", 0)
    return max(0, int(drafts) - len(perks))


def class_tag(class_name: str) -> str:
    name = (class_name or "").lower()
    spell_keys = ("mage", "sorc", "witch", "wizard", "priest", "cleric", "druid",
                  "necro", "shaman", "warlock", "oracle", "paladin", "monk")
    martial_keys = ("warrior", "guard", "soldier", "knight", "captain", "ranger",
                    "hunter", "slayer", "blade", "fighter", "barbarian", "rogue",
                    "scout", "warden")
    if any(k in name for k in spell_keys):
        return "spell"
    if any(k in name for k in martial_keys):
        return "martial"
    return "mixed"


def _pool_for(state) -> list[dict]:
    terms = list(getattr(state.world, "relic_words", None) or []) or \
        list(getattr(state.world, "lore_terms", None) or [])
    return gen_pool(state.world.seed, terms)


def draft_offer(state, player=None) -> list[dict]:
    """The standing offer: 3 class-weighted + 1 wild, stable until picked."""
    p = player if player is not None else state.player
    if drafts_pending(p) <= 0:
        return []
    d = len(p.perks or [])
    level = 5 * (d + 1)
    rng = random.Random(f"{state.world.seed}|{p.name}|{d}")
    pool = _pool_for(state)
    held = _ranks(p.perks or [])
    avail = [e for e in pool if e["min_level"] <= level and held.get(e["base"], 0) < 3]
    if not avail:
        return []
    tag = class_tag(getattr(p, "class_name", ""))
    own = [e for e in avail if e["tag"] == tag] if tag != "mixed" else []
    if tag == "mixed":
        own = [e for e in avail if e["tag"] in ("martial", "spell")]
    triple, seen = [], set()
    for e in rng.sample(own, min(3, len(own))) if own else []:
        if e["base"] not in seen:
            seen.add(e["base"])
            triple.append(e)
    rest = [e for e in avail if e["base"] not in seen]
    while len(triple) < 3 and rest:
        e = rng.choice(rest)
        rest = [x for x in rest if x["base"] != e["base"]]
        seen.add(e["base"])
        triple.append(e)
    wilds = [e for e in avail if e["tag"] == "wild" and e["base"] not in seen]
    offer = list(triple[:3])
    if wilds:
        offer.append(rng.choice(wilds))
    else:
        more = [e for e in avail if e["base"] not in {x["base"] for x in offer}]
        if more:
            offer.append(rng.choice(more))
    out = []
    for e in offer:
        out.append({**e, "held": held.get(e["base"], 0)})
    return out


def take_draft(state, index: int, player=None,
               rng: random.Random | None = None) -> bool:
    """Take offer[index]: rank up, take-time tribute, log. The rest dissolve."""
    rng = rng or random.Random()
    p = player if player is not None else state.player
    offer = draft_offer(state, p)
    if not (0 <= index < len(offer)):
        return False
    e = offer[index]
    rank = min(3, _ranks(p.perks or []).get(e["base"], 0) + 1)
    pid = e["id"] if rank == 1 else f"{e['base']}@{rank}"
    p.perks.append(pid)
    if e["base"] == "manafont":
        p.max_mana += e["mag"]
        p.mana = min(p.max_mana, p.mana + e["mag"])
    if e["base"] == "windfall":
        p.gold += e["mag"] * rank
    if e["base"] == "bloodprice" and "bloodprice" not in (p.spells or []):
        p.spells.append("bloodprice")
    state.log(f"+ Perk taken: {e['name']} (rank {rank})! {e['flavor']}")
    return True
