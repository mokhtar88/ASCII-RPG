"""Gear economy (Drop 3 + SRD harvest): items, shops, loot, quest rewards.

Items are plain dicts (JSON-safe) shaped like:
  {"id","name","kind","slot","atk","hp","attrs","skills","value"}
Slots: weapon | armor | ring | amulet (one each).
attrs/skills grant attribute points / skill LEVELS while worn.
"""
from __future__ import annotations

import random

SLOTS = ("weapon", "armor", "ring", "amulet")

WEAPON_NOUNS = ["Blade", "Axe", "Dagger", "Sword", "Spear", "Mace"]
BOW_NOUNS = ["Bow", "Longbow", "Shortbow"]
BOW_MIN, BOW_MAX = 2, 4

# Loot scaling: common < keen < runed < mythic. Higher tiers roll luckier;
# bosses and deep hoards set a floor. (atk, hp) bumps + value multiplier.
RARITIES = ("common", "keen", "runed", "mythic")
RARITY_MULT = {"common": 1.0, "keen": 1.5, "runed": 2.2, "mythic": 3.5}
RARITY_BONUS = {"common": (0, 0), "keen": (1, 4), "runed": (2, 8), "mythic": (3, 12)}
RARITY_PREFIX = {"common": "", "keen": "Keen ", "runed": "Runed ", "mythic": "Mythic "}


def rarity_rank(r: str) -> int:
    try:
        return RARITIES.index(r)
    except ValueError:
        return 0


def roll_rarity(rng: random.Random, tier: int = 1, min_rarity: str = "common") -> str:
    """Tier-weighted roll: tier 1 finds mythic 4% of the time, tier 5 ~20%."""
    x = rng.random() - 0.04 * (max(1, tier) - 1)
    rolled = "mythic" if x < 0.04 else ("runed" if x < 0.15 else ("keen" if x < 0.38 else "common"))
    if rarity_rank(rolled) < rarity_rank(min_rarity):
        return min_rarity if min_rarity in RARITIES else "common"
    return rolled


def _apply_rarity(item: dict, rarity: str) -> dict:
    """Name, stat bump, and price for one rolled rarity (pure, no rng)."""
    if rarity not in RARITIES or rarity == "common":
        item["rarity"] = "common"
        return item
    atk_b, hp_b = RARITY_BONUS[rarity]
    slot = item.get("slot", "")
    if slot == "weapon":
        item["atk"] = int(item.get("atk", 0)) + atk_b
    elif slot in ("armor", "amulet"):
        item["hp"] = int(item.get("hp", 0)) + hp_b
    elif slot == "ring":
        attrs = dict(item.get("attrs") or {})
        if attrs:
            k = sorted(attrs)[0]
            attrs[k] = int(attrs[k]) + 1
        else:
            attrs["LUK"] = 1
        item["attrs"] = attrs
    item["name"] = f"{RARITY_PREFIX[rarity]}{item['name']}"
    item["rarity"] = rarity
    base_value = int(item.get("value", 5))
    item["value"] = max(base_value + 2, round(base_value * RARITY_MULT[rarity]))
    return item
ARMOR_NOUNS = ["Mail", "Plate", "Cloak", "Hide", "Guard", "Shroud"]
FALLBACK_TERMS = ["Ember", "Thorn", "Wolf", "Raven", "Iron", "Oak", "Storm", "Ash"]

_attr_for = ["STR", "SPD", "CHA", "WIS", "LUK"]
_skill_for = {"ring": ["speech", "sneak", "arcana"],
              "amulet": ["lore", "medicine", "arcana"],
              "weapon": ["blades"], "armor": ["survival", "medicine"]}


def _term(terms: list[str], rng: random.Random) -> str:
    pool = [t.capitalize() for t in terms[:12]] or FALLBACK_TERMS
    return rng.choice(pool)


def name_pool(world) -> list[str]:
    """Noun-safe naming pool: book entities first, lore terms as backup."""
    rel = list(getattr(world, "relic_words", None) or [])
    if rel:
        return rel
    return list(getattr(world, "lore_terms", None) or [])


def gen_item(kind: str, terms: list[str], rng: random.Random, tier: int = 1,
             climate: dict | None = None, rarity: str | None = None,
             min_rarity: str = "common") -> dict:
    """Make one item. Higher tier = bigger numbers AND luckier rarity rolls.
    Jewels (and odd steel) sometimes carry skill-craft. Elements/resists
    follow the shelf's weather."""
    tier = max(1, tier)
    els = ["ember", "frost", "storm", "umbral"]

    def _el() -> str:
        if not climate:
            return rng.choice(els)
        bag = sorted(climate)
        r = rng.random() * sum(climate[e] for e in bag)
        for e in bag:
            r -= climate[e]
            if r <= 0:
                return e
        return bag[-1]
    if kind == "weapon":
        if rng.random() < 0.35:
            name = f"{_term(terms, rng)} {rng.choice(BOW_NOUNS)}"
            atk = max(1, tier - 1 + rng.randint(0, 2))
            item = {"atk": atk, "hp": 0, "attrs": {}, "skills": {},
                    "ranged": True}
            if rng.random() < 0.15:
                item["skills"] = {"blades": 1}
            if rng.random() < 0.2:
                item["element"] = _el()
        else:
            style = rng.choices(["sword", "swift", "heavy", "spear"],
                                weights=[40, 20, 20, 20])[0]
            prefix = {"sword": "", "swift": "Swift ", "heavy": "Great ",
                      "spear": "Long "}[style]
            name = f"{prefix}{_term(terms, rng)} {rng.choice(WEAPON_NOUNS)}"
            atk = tier + rng.randint(0, 3)
            if style == "heavy":
                atk += 1
            if style == "spear":
                atk = max(1, atk - 1)
            item = {"atk": atk, "hp": 0, "attrs": {}, "skills": {}, "style": style}
            if rng.random() < 0.15:
                item["skills"] = {"blades": 1}
            if rng.random() < 0.2:
                item["element"] = _el()
    elif kind == "armor":
        name = f"{_term(terms, rng)} {rng.choice(ARMOR_NOUNS)}"
        item = {"atk": 0, "hp": 4 * tier + rng.randint(0, 6), "attrs": {}, "skills": {}}
        if rng.random() < 0.15:
            item["skills"] = {"survival": 1}
        if rng.random() < 0.2:
            item["resist"] = _el()
    elif kind == "ring":
        name = f"Ring of {_term(terms, rng)}"
        item = {"atk": 0, "hp": 0, "attrs": {rng.choice(_attr_for): 2}, "skills": {}}
        if rng.random() < 0.3:
            item["skills"] = {rng.choice(_skill_for["ring"]): rng.randint(1, 2)}
    else:  # amulet
        name = f"Amulet of {_term(terms, rng)}"
        item = {"atk": 0, "hp": 6, "attrs": {rng.choice(_attr_for): 2}, "skills": {}}
        if rng.random() < 0.3:
            item["skills"] = {rng.choice(_skill_for["amulet"]): rng.randint(1, 2)}
    item.update({
        "id": f"{kind}-{name.lower().replace(' ', '-')}-{rng.randint(100, 999)}",
        "name": name, "kind": kind, "slot": kind, "tier": tier, "base": name,
    })
    item["value"] = (5 + item["atk"] * 8 + item["hp"] * 2
                     + sum(item["attrs"].values()) * 10
                     + sum(item["skills"].values()) * 12)
    return _apply_rarity(item, rarity or roll_rarity(rng, tier, min_rarity))


def gen_bow(terms: list[str], rng: random.Random, tier: int = 1,
            climate: dict | None = None, rarity: str | None = None,
            min_rarity: str = "common") -> dict:
    """One ranged weapon outright: bows shoot 2-4 tiles, slightly soft up close."""
    tier = max(1, tier)
    item: dict = {"atk": max(1, tier - 1 + rng.randint(0, 2)), "hp": 0,
                  "attrs": {}, "skills": {}, "ranged": True}
    if rng.random() < 0.15:
        item["skills"] = {"blades": 1}
    if rng.random() < 0.2:
        els = ["ember", "frost", "storm", "umbral"]
        if not climate:
            item["element"] = rng.choice(els)
        else:
            bag = sorted(climate)
            r = rng.random() * sum(climate[e] for e in bag)
            for e in bag:
                r -= climate[e]
                if r <= 0:
                    item["element"] = e
                    break
            else:
                item["element"] = bag[-1]
    name = f"{_term(terms, rng)} {rng.choice(BOW_NOUNS)}"
    item.update({
        "id": f"bow-{name.lower().replace(' ', '-')}-{rng.randint(100, 999)}",
        "name": name, "kind": "weapon", "slot": "weapon", "tier": tier, "base": name,
    })
    item["value"] = (5 + item["atk"] * 8 + item["hp"] * 2
                     + sum(item["attrs"].values()) * 10
                     + sum(item["skills"].values()) * 12)
    return _apply_rarity(item, rarity or roll_rarity(rng, tier, min_rarity))


def base_name(item: dict) -> str:
    """Pre-rarity name: stored at forging, else strip a legacy prefix."""
    if item.get("base"):
        return str(item["base"])
    name = str(item.get("name", ""))
    for pre in ("Mythic ", "Runed ", "Keen "):
        if name.startswith(pre):
            return name[len(pre):]
    return name


REFORGE_MAX = 5


def reforge_cost(item: dict) -> int:
    """Smith's price: grows with tier and rarity. The realm's gold sink."""
    tier = int(item.get("tier", 1))
    mult = RARITY_MULT.get(item.get("rarity", "common"), 1.0)
    return max(10, round((10 + 15 * tier) * mult))


def reforge_item(item: dict, rng: random.Random) -> tuple[bool, str]:
    """Raise one gear piece a tier (cap 5), rerolling rarity never downward.
    Mutates in place. Returns (ok, note)."""
    if (item.get("kind") or "") == "consumable" or not item.get("slot"):
        return False, "only steel and jewels take the hammer"
    tier = int(item.get("tier", 1))
    if tier >= REFORGE_MAX:
        return False, "it cannot be improved further"
    old_r = item.get("rarity", "common") if item.get("rarity") in RARITIES else "common"
    base = base_name(item)
    # strip the old rarity's craft, hammer in the tier's worth
    atk_b, hp_b = RARITY_BONUS[old_r]
    slot = item.get("slot", "")
    if slot == "weapon":
        item["atk"] = max(1, int(item.get("atk", 1)) - atk_b + 1)
    elif slot in ("armor", "amulet"):
        item["hp"] = max(0, int(item.get("hp", 0)) - hp_b + 4)
    elif slot == "ring":
        attrs = dict(item.get("attrs") or {})
        if attrs:
            k = sorted(attrs)[0]
            had = 1 if old_r != "common" else 0
            attrs[k] = max(1, int(attrs[k]) - had) + 1
        else:
            attrs["LUK"] = 1
        item["attrs"] = attrs
    item["tier"] = tier + 1
    item["base"] = base
    item["name"] = base
    item["value"] = (5 + int(item.get("atk", 0)) * 8 + int(item.get("hp", 0)) * 2
                     + sum(int(v) for v in (item.get("attrs") or {}).values()) * 10
                     + sum(int(v) for v in (item.get("skills") or {}).values()) * 12)
    new_r = roll_rarity(rng, item["tier"], min_rarity=old_r)
    _apply_rarity(item, new_r)
    return True, f"reforged to tier {item['tier']} ({new_r})"


def is_bow(item: dict | None) -> bool:
    return bool(item) and (item or {}).get("slot") == "weapon" and bool((item or {}).get("ranged"))


def wielded_bow(player) -> dict | None:
    """The equipped bow, if any (legacy steel without the flag counts as melee)."""
    eq = player.equipment if hasattr(player, "equipment") else player.get("equipment", {})
    w = (eq or {}).get("weapon")
    return w if is_bow(w) else None


def gen_shop_stock(terms: list[str], rng: random.Random, count: int = 5,
                   tier: int = 1, climate: dict | None = None) -> list[dict]:
    kinds = ["weapon", "weapon", "armor", "armor", "ring", "amulet"]
    stock = [gen_item(rng.choice(kinds), terms, rng, tier, climate) for _ in range(count)]
    # Every market racks at least one bow; the frontier favors archers.
    if not any(i.get("ranged") for i in stock if i.get("slot") == "weapon"):
        stock.append(gen_bow(terms, rng, tier=tier, climate=climate))
    # Combat slice one: every market also carries field consumables.
    for sub in ("potion", "bomb", "smoke", "quiver"):
        if rng.random() < 0.85:
            stock.append(gen_consumable(sub, terms, rng))
    return stock


def loot_drop(terms: list[str], rng: random.Random, enemy_atk: int, luck: int,
              tier: int | None = None, bonus: float = 0.0,
              climate: dict | None = None, min_rarity: str = "common") -> dict | None:
    """Roll a kill drop. Returns an item or None."""
    if rng.random() > 0.22 + luck * 0.01 + bonus:
        return None
    kind = rng.choice(["weapon", "weapon", "armor", "ring", "amulet"])
    return gen_item(kind, terms, rng, tier=tier if tier is not None else 1 + enemy_atk // 4,
                    climate=climate, min_rarity=min_rarity)


def quest_reward_item(quest_kind: str, terms: list[str], rng: random.Random,
                      level: int, climate: dict | None = None) -> dict | None:
    """Occasional gear with a completed quest (35%). Bounties pay steel."""
    if rng.random() > 0.35:
        return None
    kind = {"bounty": "weapon", "explore": "ring", "deliver": "armor",
            "escort": "amulet", "hunt": "weapon", "tribute": "ring"}.get(quest_kind, "armor")
    if quest_kind == "explore" and rng.random() < 0.5:
        kind = "amulet"
    return gen_item(kind, terms, rng, tier=1 + level // 3, climate=climate)


CONSUMABLE_DEFS = {
    "potion": ("Draught", 15, "drink: +25hp, staunches bleed"),
    "bomb": ("Firebomb", 20, "throw: 25 AoE burn"),
    "smoke": ("Smokepowder", 12, "burn: sure flee"),
    "quiver": ("Quiver", 10, "fletch: +8 arrows"),
    "tonic": ("Stoneward Tonic", 18, "drink: +15 ward"),
    "swift": ("Swiftfoot Tonic", 16, "drink: +escape 30 steps"),
    "iron": ("Ironhide Brew", 20, "drink: -2 per reply 20 steps"),
    "focus": ("Focusing Tea", 16, "drink: next strike crits"),
    "secondwind": ("Second Wind", 30, "drink: cheat death once"),
    "love": ("Love Philtre", 22, "throw: charms nearest 30 steps"),
    "glitter": ("Glitterbomb", 18, "throw: blinds volleys 20 steps"),
    "berserk": ("Berserk Mushroom", 18, "eat: +6 ATK, wild aim 15 steps"),
    "ghost": ("Ghost Draught", 24, "drink: walk through foes 10 steps"),
    "greed": ("Greed Philter", 20, "drink: richer drops 60 steps"),
    "firebelch": ("Dragonbreath", 22, "drink: strikes burn 15 steps"),
}


MATERIAL_DEFS = {
    "herb": ("Wildherb", 3, "gathered in forests (T), brewed whole"),
    "fang": ("Fang", 4, "torn from beasts, fletched or fired"),
    "venom": ("Venom Sac", 6, "milked from spiders, brewed to burn"),
    "dust": ("Gravedust", 5, "swept from the dead, brewed to vanish"),
    "scale": ("Scale", 8, "pried from drakes and golems, brewed to stone"),
}


TRAP_DEFS = {
    "snare": ("Snare", 8, "lays: slows the first tread 6"),
    "dart": ("Dart Trap", 10, "lays: 12 at the first tread"),
    "ember": ("Ember Cache", 12, "lays: burn plus 8 at the first tread"),
    "oil": ("Oil Slick", 9, "lays: steals the tread's steps"),
}


def gen_trap(sub: str, terms: list[str], rng: random.Random) -> dict:
    """Rogue work: kettle-built traps, laid with X. JSON-safe."""
    noun, value, _hint = TRAP_DEFS.get(sub, ("Snare", 8, "lays"))
    term = _term(terms, rng)
    name = f"{term} {noun}"
    return {"id": f"trap-{sub}-{name.lower().replace(' ', '-')}-{rng.randint(100, 999)}",
            "name": name, "kind": "trap", "slot": "", "sub": sub,
            "atk": 0, "hp": 0, "attrs": {}, "skills": {}, "value": value}


def gen_material(sub: str, terms: list[str], rng: random.Random) -> dict:
    """Alchemy stock: herbs, fangs, venom, dust, scales. JSON-safe."""
    noun, value, _hint = MATERIAL_DEFS.get(sub, ("Trinket", 3, "brew it"))
    term = _term(terms, rng)
    name = f"{term} {noun}"
    return {"id": f"mat-{sub}-{name.lower().replace(' ', '-')}-{rng.randint(100, 999)}",
            "name": name, "kind": "material", "slot": "", "sub": sub,
            "atk": 0, "hp": 0, "attrs": {}, "skills": {}, "value": value}


def mat_count(player, sub: str) -> int:
    inv = getattr(player, "inventory", None)
    if not isinstance(inv, list):
        return 0
    return sum(1 for i in inv if (i.get("kind") or "") == "material"
               and i.get("sub") == sub)


def take_mats(player, sub: str, n: int) -> bool:
    """Remove n materials of one kind. False if short (nothing removed)."""
    inv = getattr(player, "inventory", None)
    if not isinstance(inv, list):
        return False
    idx = [i for i, it in enumerate(inv) if (it.get("kind") or "") == "material"
           and it.get("sub") == sub]
    if len(idx) < n:
        return False
    for i in sorted(idx[:n], reverse=True):
        del inv[i]
    return True


def gen_consumable(sub: str, terms: list[str], rng: random.Random) -> dict:
    """Combat slice one field goods: potion / fire bomb / smoke. JSON-safe."""
    noun, value, _hint = CONSUMABLE_DEFS.get(sub, ("Trinket", 10, "use"))
    term = _term(terms, rng)
    name = f"{term} {noun}"
    return {"id": f"use-{sub}-{name.lower().replace(' ', '-')}-{rng.randint(100, 999)}",
            "name": name, "kind": "consumable", "slot": "", "sub": sub,
            "atk": 0, "hp": 0, "attrs": {}, "skills": {}, "value": value}


def consumable_drop(terms: list[str], rng: random.Random) -> dict | None:
    """Kill loot side-roll for consumables (~18%): potions most common."""
    r = rng.random()
    if r > 0.18:
        return None
    if r > 0.10:
        sub = "potion"
    elif r > 0.07:
        sub = "quiver"
    elif r > 0.04:
        sub = "tonic"
    elif r > 0.02:
        sub = "bomb"
    else:
        sub = "smoke"
    return gen_consumable(sub, terms, rng)


def item_line(item: dict) -> str:
    # names are book-born and old saves may hold nulls; fonts raise on them.
    item = {**item, "name": str(item.get("name", "")).replace("\x00", "")}
    if (item.get("kind") or "") == "material":
        sub = item.get("sub", "")
        hint = {"herb": "brew it", "fang": "fletch or fire it",
                "venom": "brew it to burn", "dust": "brew it to vanish",
                "scale": "brew it to stone"}.get(sub, "brew it")
        return f"{item['name']} [mat: {hint}] ({item.get('value', 0)}g)"
    if (item.get("kind") or "") == "consumable":
        sub = item.get("sub", "")
        hint = {"potion": "drink: +25hp", "bomb": "throw: 25 AoE",
                "smoke": "burn: sure flee", "quiver": "fletch: +8 arrows",
                "tonic": "drink: +15 ward", "swift": "drink: +escape",
                "iron": "drink: -2/reply", "focus": "drink: next crits",
                "secondwind": "drink: cheat death", "love": "throw: charms",
                "glitter": "throw: blinds", "berserk": "eat: +6 wild",
                "ghost": "drink: pass through", "greed": "drink: richer",
                "firebelch": "drink: strikes burn"}.get(sub, "use")
        return f"{item['name']} [use: {hint}] ({item.get('value', 0)}g)"
    if (item.get("kind") or "") == "trap":
        sub = item.get("sub", "")
        hint = {"snare": "lay: slows 6", "dart": "lay: 12 dmg",
                "ember": "lay: burn + 8", "oil": "lay: steals steps"}.get(sub, "lay")
        return f"{item['name']} [trap: {hint}] ({item.get('value', 0)}g)"
    bits = []
    if is_bow(item):
        bits.append(f"bow {BOW_MIN}-{BOW_MAX}")
    rarity = item.get("rarity", "common")
    tag = f"{rarity} {item['kind']}" if rarity not in ("common", "") else item['kind']
    if item.get("atk"):
        bits.append(f"+{item['atk']} ATK")
    if item.get("hp"):
        bits.append(f"+{item['hp']} HP")
    if item.get("element"):
        bits.append(f"{item['element']}-tongued")
    if item.get("resist"):
        bits.append(f"wards {item['resist']}")
    for k, v in (item.get("attrs") or {}).items():
        bits.append(f"+{v} {k}")
    for k, v in (item.get("skills") or {}).items():
        bits.append(f"+{v} {k.capitalize()}")
    return f"{item['name']} [{tag}] {' '.join(bits)} ({item.get('value', 0)}g)"


# ---- effective stats (gear-aware). Players are duck-typed dicts/objects. ----

def _equipped(player) -> list[dict]:
    eq = player.equipment if hasattr(player, "equipment") else player.get("equipment", {})
    return [i for i in (eq or {}).values() if i]


def eff_atk(player) -> int:
    base = player.atk if hasattr(player, "atk") else player.get("atk", 0)
    buffs = player.buffs if hasattr(player, "buffs") else player.get("buffs", {})
    buff = 3 if (buffs or {}).get("triumph", 0) > 0 else 0
    return base + buff + sum(int(i.get("atk", 0)) for i in _equipped(player))


def eff_resists(player) -> set:
    out = set()
    for i in _equipped(player):
        if i.get("resist"):
            out.add(i["resist"])
    return out


def eff_max_hp(player) -> int:
    base = player.max_hp if hasattr(player, "max_hp") else player.get("max_hp", 0)
    return base + sum(int(i.get("hp", 0)) for i in _equipped(player))


def eff_attr(player, key: str) -> int:
    if hasattr(player, "attr"):
        base = player.attr(key)
    else:
        base = int(player.get("attrs", {}).get(key, 4))
    return base + sum(int(i.get("attrs", {}).get(key, 0)) for i in _equipped(player))


def eff_skill(player, key: str) -> int:
    """Skill LEVEL with worn craft applied (uncapped, like base mastery)."""
    if hasattr(player, "skill_level"):
        base = player.skill_level(key)
    else:
        base = int(player.get("skills", {}).get(key, 0)) // 25
    return base + sum(int(i.get("skills", {}).get(key, 0)) for i in _equipped(player))
