"""Minimum-viable magic, SRD-harvested: a lore-named spellbook.

Spell definitions are a pure function of lore terms, so no save space is
needed. Players store known spell ids; shrines teach the rest.
"""
from __future__ import annotations


def spellbook(terms: list[str]) -> list[dict]:
    """Bolt/spark/smite (burn at three prices), mend (heal), blink (teleport),
    ward (shield), charm (turn a blade), sight (sense wild sites) — plus the
    five road-signs: igni (fire that takes the whole pack), aard (a push that
    staggers), yrden (a snare that steals steps), fury (turns a foe on its
    pack), frostbite (ice that slows the blood)."""
    t = [(w.capitalize() if w else "Ember") for w in (list(terms[:18]) + ["Ember"] * 18)]
    return [
        {"id": "bolt", "name": f"{t[0]}bolt", "cost": 6,
         "desc": f"Hurl {t[0].lower()} at the nearest foe (7 tiles)."},
        {"id": "spark", "name": f"{t[1]}spark", "cost": 3,
         "desc": "A cheap crackle. Wont kill giants."},
        {"id": "smite", "name": f"{t[2]}smite", "cost": 10,
         "desc": "The expensive answer (near foe, 5 tiles)."},
        {"id": "mend", "name": f"{t[3]}mending", "cost": 8,
         "desc": "Knit flesh whole again."},
        {"id": "blink", "name": f"{t[4]}step", "cost": 7,
         "desc": "Unravel up to 5 tiles away."},
        {"id": "ward", "name": f"{t[5]}ward", "cost": 6,
         "desc": "A shield that drinks blows until rest."},
        {"id": "charm", "name": f"{t[6]}charm", "cost": 5,
         "desc": "The nearest foe forgets you (30 steps)."},
        {"id": "sight", "name": f"{t[7]}sight", "cost": 5,
         "desc": "Sense the three nearest wild sites."},
        {"id": "igni", "name": f"{t[8]}surge", "cost": 9,
         "desc": "Fire takes every foe within 2 steps (burns)."},
        {"id": "aard", "name": f"{t[9]}push", "cost": 6,
         "desc": "Hurl the nearest foe 2 tiles back, staggered."},
        {"id": "yrden", "name": f"{t[10]}snare", "cost": 7,
         "desc": "Slow every foe within 4 steps (10 steps)."},
        {"id": "fury", "name": f"{t[11]}fury", "cost": 6,
         "desc": "Turn the nearest foe on its pack (8 steps)."},
        {"id": "frostbite", "name": f"{t[12]}bite", "cost": 7,
         "desc": "Ice bites the nearest foe and slows its blood."},
        {"id": "summon", "name": f"{t[13]}call", "cost": 10,
         "desc": "Call a spectral wolf to fight beside you (25 steps)."},
        {"id": "turn", "name": f"{t[14]}cry", "cost": 7,
         "desc": "Turn the dead within 3 steps — they flee."},
        {"id": "blizzard", "name": f"{t[15]}fall", "cost": 14,
         "desc": "A storm takes every foe within 4 steps."},
        {"id": "invis", "name": f"{t[16]}veil", "cost": 8,
         "desc": "Walk unseen 12 steps (foes lose you)."},
        {"id": "mark", "name": f"{t[17]}mark", "cost": 10,
         "desc": "Mark this ground; cast again to return."},
    ]


def bloodprice_def() -> dict:
    """The wild perk's spell: fixed name, blood cost, ruin damage. Shown in
    the book only while the perk is held."""
    return {"id": "bloodprice", "name": "Bloodprice", "cost": 0,
            "desc": "Pay half your blood: ruin the nearest foe (4 tiles)."}


def spell_def(terms: list[str], spell_id: str) -> dict | None:
    if spell_id == "bloodprice":
        return bloodprice_def()
    if "-" in spell_id:
        base, _, element = spell_id.partition("-")
        if element in ELEMENTS:
            return fused_def(terms, base, element)
        return None
    for s in spellbook(terms):
        if s["id"] == spell_id:
            return s
    return None


ELEMENTS = ["ember", "frost", "storm", "umbral"]

# shrine fusion fee per element (material sub -> count)
FUSE_FEE = {"ember": ("scale", 2), "frost": ("venom", 2),
            "storm": ("dust", 2), "umbral": ("fang", 2)}

# only these bases take an element (blades of damage, mending, warding)
FUSABLE = ("bolt", "spark", "smite", "mend", "ward")


def fused_def(terms: list[str], base_id: str, element: str) -> dict | None:
    """A shrine-fused variant: known spell x element (ember-ward, frost-bolt...)."""
    if base_id not in FUSABLE or element not in ELEMENTS:
        return None
    base = next((s for s in spellbook(terms) if s["id"] == base_id), None)
    if base is None:
        return None
    return {"id": f"{base_id}-{element}",
            "name": f"{element.capitalize()} {base['name']}",
            "cost": int(base["cost"]) + 2,
            "desc": f"{base['desc'][:48]} Tongued with {element}.",
            "base": base_id, "element": element}
