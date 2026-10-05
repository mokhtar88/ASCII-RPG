"""Pygame ASCII renderer + exploration + turn-based combat.

Controls:
  Arrows / WASD - move    E - talk/interact    A - attack in combat
  F - flee in combat      Q - quit             H - heal in city (costs gold)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .worldgen import World, CITY_TILE, WALKABLE, faction_name, OPPOSITE
from .items import eff_skill, name_pool
from .sfx import play

# Drop 2: attributes + skills. Every attribute does something from day one.
ATTRS = ["STR", "CON", "SPD", "CHA", "WIS", "LUK"]
ATTRS_BASE = {"STR": 4, "CON": 4, "SPD": 4, "CHA": 4, "WIS": 4, "LUK": 4}
SKILLS = ["blades", "speech", "survival", "lore", "sneak", "salvage",
          "medicine", "arcana"]


@dataclass
class Enemy:
    name: str
    x: int
    y: int
    hp: int
    atk: int
    boss: bool = False
    # bestiary: bandit | beast | undead | soldier | spider | wraith | golem | drake.
    # Trait: Savage/Towering/Cursed/Dread. charmed: turn stamp until which it wanders.
    kind: str = "bandit"
    trait: str = ""
    charmed: int = 0
    # elemental attunement (climate-born): resists one element, fears its opposite.
    attune: str = ""
    burn: int = 0
    # Combat slice one: telegraphed heavy (1 = heavy lands on next counter).
    windup: int = 0
    # Ranged drop: archers hold 2-4 tiles and loose arrows instead of closing.
    ranged: bool = False
    # Brain drop: bosses enrage at a third health (max_hp backfilled on first blood).
    enraged: bool = False
    max_hp: int = 0
    # Faction drop: sworn blades carry their power's colors.
    faction: str = ""
    # Full-kit brains: humanoids carry one draught; bosses cry for guards once.
    draught: bool = True
    cried: bool = False
    # Glitterbombs blind volleys (archers, breath, wails) for N steps.
    blind: int = 0
    # Morale + hexes: cowed blades drop tribute and stand down; routed beasts
    # flee N steps then melt away; slowed foes shamble; frenzied foes maul
    # their own pack. Shield is a chanter's ward buffer; aided spent its mend.
    cowed: bool = False
    routed: int = 0
    slowed: int = 0
    frenzied: int = 0
    shield: int = 0
    aided: bool = False
    # Spectral allies: fight for the hero until ally_ttl runs out.
    ally: bool = False
    ally_ttl: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0


def _hostile(e: "Enemy") -> bool:
    """Targetable by hero steel and spells: living, and not a sworn ally."""
    return e.alive and not getattr(e, "ally", False)


@dataclass
class Player:
    x: int
    y: int
    hp: int = 50
    max_hp: int = 50
    atk: int = 8
    gold: int = 20
    quests_done: int = 0
    name: str = "Wanderer"
    race: str = "Human"
    level: int = 1
    xp: int = 0
    # Attributes (STR/CON/SPD/CHA/WIS/LUK) and skill progress
    # (blades/speech/survival/lore). Unspent level-up points.
    attrs: dict = field(default_factory=lambda: dict(ATTRS_BASE))
    skills: dict = field(default_factory=lambda: {s: 0 for s in SKILLS})
    unspent: int = 0
    # Drop 3: gear. inventory = list of item dicts, equipment = slot -> item|None.
    inventory: list = field(default_factory=list)
    equipment: dict = field(default_factory=dict)
    # Drop 4: calling, spellbook, mana.
    class_name: str = ""
    spells: list = field(default_factory=list)
    mana: int = 20
    max_mana: int = 20
    # SRD harvest: abjuration ward buffer.
    shield: int = 0
    # Elemental saga: named buffs with turns left (triumph/feast).
    buffs: dict = field(default_factory=dict)
    # Combat slice one: poison turns left, guarding halves the next counter.
    poison: int = 0
    guarding: bool = False
    # Full-kit combat: arrows spent per volley, winded after heavies (+50% next
    # reply), bleeding ticks until staunched (potion/heal/rest, not mend).
    ammo: int = 20
    winded: bool = False
    bleed: int = 0
    # Faction drop: sworn power ("") and standing per faction id.
    oath: str = ""
    standing: dict = field(default_factory=dict)
    # Perk drafts: taken ids, earned draft count, last turn the hero struck.
    perks: list = field(default_factory=list)
    perk_drafts: int = 0
    last_strike: int = 0
    # Hearthmark: overworld [x, y] the recall sign returns to (None = unmarked).
    mark: list | None = None
    # Calling arts: template -> stride number when ready again.
    arts_cd: dict = field(default_factory=dict)

    @property
    def xp_needed(self) -> int:
        return self.level * 100

    def attr(self, key: str) -> int:
        return int(self.attrs.get(key, ATTRS_BASE.get(key, 4)))

    def skill_level(self, key: str) -> int:
        # uncapped: mastery has no ceiling, only slowing thresholds elsewhere
        return int(self.skills.get(key, 0)) // 25

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d: dict) -> "Player":
        p = Player(x=d.get("x", 0), y=d.get("y", 0))
        for k in ("hp", "max_hp", "atk", "gold", "quests_done",
                  "name", "race", "level", "xp", "unspent"):
            if k in d:
                setattr(p, k, d[k])
        if isinstance(d.get("attrs"), dict):
            base = dict(ATTRS_BASE)
            base.update({k: int(v) for k, v in d["attrs"].items() if k in base})
            p.attrs = base
        if isinstance(d.get("skills"), dict):
            p.skills = {s: int(d["skills"].get(s, 0)) for s in SKILLS}
        if isinstance(d.get("inventory"), list):
            p.inventory = [i for i in d["inventory"] if isinstance(i, dict)]
        if isinstance(d.get("equipment"), dict):
            p.equipment = {k: v for k, v in d["equipment"].items() if v is None or isinstance(v, dict)}
        p.class_name = str(d.get("class_name", ""))
        if isinstance(d.get("spells"), list):
            p.spells = [str(s) for s in d["spells"]]
        p.mana = int(d.get("mana", 8 + p.attr("WIS") * 4))
        p.max_mana = int(d.get("max_mana", 8 + p.attr("WIS") * 4))
        p.shield = int(d.get("shield", 0))
        if isinstance(d.get("buffs"), dict):
            p.buffs = {str(k): int(v) for k, v in d["buffs"].items()}
        p.poison = int(d.get("poison", 0))
        p.guarding = bool(d.get("guarding", False))
        p.ammo = int(d.get("ammo", 20))
        p.winded = bool(d.get("winded", False))
        p.bleed = int(d.get("bleed", 0))
        p.oath = str(d.get("oath", ""))
        if isinstance(d.get("standing"), dict):
            p.standing = {str(k): int(v) for k, v in d["standing"].items()}
        if isinstance(d.get("perks"), list):
            p.perks = [str(s) for s in d["perks"]]
        p.perk_drafts = int(d.get("perk_drafts", 0))
        p.last_strike = int(d.get("last_strike", 0))
        mk = d.get("mark")
        if isinstance(mk, (list, tuple)) and len(mk) == 2:
            try:
                p.mark = [int(mk[0]), int(mk[1])]
            except Exception:
                p.mark = None
        if isinstance(d.get("arts_cd"), dict):
            p.arts_cd = {str(k): int(v) for k, v in d["arts_cd"].items()}
        # stored hp may exceed gearless max after an unequip; real cap is computed
        return p


@dataclass
class GameState:
    world: World
    player: Player
    enemies: list[Enemy] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    in_combat_with: Enemy | None = None
    # All player characters of this save (same objects the save screen edits).
    # Needed so infinite-frontier growth can shift everyone's coords.
    roster: list[Player] = field(default_factory=list)
    # Last announced day-phase (clock announcements); not persisted.
    last_phase_announced: str = ""
    # Drop 4: live dungeon (None on the overworld). Layouts are seed-derived;
    # only flags persist (see world.site_states + world.active_interior).
    interior: dict | None = None
    # Enrichment 2: step counter (undead shamble every other step).
    turns: int = 0
    # Brain drop: escort companions ride here (quest id -> {"x","y"}; hurt lives
    # on the quest itself so saves keep it). Session-local, re-derived on load.
    companions: dict = field(default_factory=dict)
    # Game feel: floating numbers + tile flashes (rendered, decay per frame).
    floaters: list = field(default_factory=list)
    flashes: list = field(default_factory=list)

    def log(self, msg: str) -> None:
        # belt-and-braces: saves built from poisoned books may already hold
        # nulls; the font renderer raises on them, so scrub every message.
        self.messages.append(str(msg).replace("\x00", ""))
        del self.messages[:-8]

    def ping(self, x: int, y: int, text: str, color: tuple) -> None:
        self.floaters.append({"x": x, "y": y, "text": text, "color": color, "ttl": 26})
        del self.floaters[:-20]

    def flash(self, x: int, y: int, color: tuple = (255, 60, 60)) -> None:
        self.flashes.append({"x": x, "y": y, "color": color, "ttl": 8})
        del self.flashes[:-20]


def _near_site(world, x: int, y: int, kinds: tuple, radius: int) -> bool:
    return any(getattr(s, "kind", "") in kinds and abs(s.x - x) + abs(s.y - y) <= radius
               for s in world.sites)


def _near_war_city(world, x: int, y: int, radius: int) -> str:
    war = {f.id for f in world.factions if f.at_war}
    for c in world.cities:
        if c.faction in war and abs(c.x - x) + abs(c.y - y) <= radius:
            return c.faction
    return ""


def spawn_foe(world, x: int, y: int, rng: random.Random, pool: list,
              mult: float = 1.0, level_scale: int = 0, force: str = "") -> Enemy | None:
    """Bestiary placement: beasts in the deep woods, dead near old stones,
    soldiers where powers bleed, blades everywhere else."""
    from .worldgen import faction_name
    terms = world.relic_words or world.lore_terms or ["ash"]
    kind = force
    if not kind:
        r = rng.random()
        fac = _near_war_city(world, x, y, 12)
        hgt = len(world.grid)
        near_mountain = any(
            0 <= x + dx < len(world.grid[0]) and 0 <= y + dy < hgt
            and world.grid[y + dy][x + dx] == "^"
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if r < 0.08:
            kind = "drake"
        elif _near_site(world, x, y, ("dungeon", "ruin", "shrine"), 6) and r < 0.6:
            if r < 0.15:
                kind = "wraith"
            elif r < 0.3:
                kind = "mage"
            else:
                kind = "undead"
        elif world.grid[y][x] == "T" and r < 0.55:
            kind = "spider" if r < 0.3 else "beast"
        elif near_mountain and r < 0.6:
            kind = "golem"
        elif fac and r < 0.7:
            kind = "soldier"
        else:
            kind = "bandit"
    t = rng.choice(terms).capitalize()
    if kind == "beast":
        name = f"{t} {rng.choice(['Wolf', 'Fang', 'Claw', 'Boar'])}"
        hp, atk = rng.randint(18, 30), rng.randint(4, 7)
    elif kind == "spider":
        name = f"{t} {rng.choice(['Spinner', 'Web', 'Widow'])}"
        hp, atk = rng.randint(15, 26), rng.randint(6, 10)
    elif kind == "wraith":
        name = f"{t} {rng.choice(['Wraith', 'Specter', 'Shade'])}"
        hp, atk = rng.randint(24, 38), rng.randint(6, 10)
    elif kind == "golem":
        name = f"{t} {rng.choice(['Golem', 'Shaleborn', 'Crag'])}"
        hp, atk = rng.randint(45, 65), rng.randint(7, 11)
    elif kind == "drake":
        name = f"{t} {rng.choice(['Drake', 'Wyrm', 'Wyvern'])}"
        hp, atk = rng.randint(55, 80), rng.randint(10, 14)
    elif kind == "undead":
        name = f"{t} {rng.choice(['Wight', 'Husk', 'Barrow-born'])}"
        hp, atk = rng.randint(30, 45), rng.randint(5, 8)
    elif kind == "mage":
        name = f"{t} {rng.choice(['Hexer', 'Chanter', 'Witch'])}"
        hp, atk = rng.randint(20, 30), rng.randint(6, 9)
    elif kind == "soldier":
        fac = _near_war_city(world, x, y, 12)
        fname = faction_name(world, fac).split()[0] if fac else t
        name = f"{fname} {rng.choice(['Man-at-arms', 'Blade', 'Pike'])}"
        hp, atk = rng.randint(30, 40), rng.randint(8, 12)
    else:
        b = rng.choice(pool) if pool else None
        if b is None:
            name = f"{t} {rng.choice(['Rogue', 'Blade', 'Cutthroat'])}"
            hp, atk = rng.randint(25, 40), rng.randint(5, 9)
        else:
            name, hp, atk = b.name, b.hp, b.atk
    hp = max(1, round(hp + level_scale * 4))
    atk = max(1, round(atk * mult) + (level_scale + 1) // 2)
    foe = Enemy(name=name, x=x, y=y, hp=hp, atk=atk, kind=kind)
    if kind == "soldier":
        # sworn colors: soldiers march for the nearest warring power
        foe.faction = _near_war_city(world, x, y, 12)
    # one blade in four keeps a bowstring: soldiers and bandits shoot 2-4.
    if kind in ("bandit", "soldier") and not foe.boss and rng.random() < 0.25:
        foe.ranged = True
        foe.name = f"{name} Bowman" if kind == "bandit" else f"{name} Archer"
    # only humanoids think to carry a draught; beasts and horrors never do.
    foe.draught = kind in ("bandit", "soldier")
    # the shelf's weather lives in the flesh: attuned foes resist one element
    if kind in ("beast", "spider", "undead", "wraith", "golem", "drake"):
        from .worldgen import roll_climate
        climate = getattr(world, "climate", None) or {}
        if climate and rng.random() < 0.4:
            foe.attune = roll_climate(rng, climate)
    return foe


def trail_scale(level: int) -> int:
    """Wilds keep closer pace now: half your level trails you, not a third."""
    return max(0, (level - 1) // 2)


def new_game(world: World, seed: int | None = None,
             player: Player | None = None,
             difficulty: str = "normal") -> GameState:
    rng = random.Random(seed if seed is not None else world.seed + 999)
    # spawn player on a walkable tile near first city
    grid = [list(r) for r in world.grid]
    h, w = len(grid), len(grid[0])
    px, py = w // 2, h // 2
    for _ in range(500):
        x, y = rng.randrange(w), rng.randrange(h)
        if grid[y][x] in WALKABLE:
            px, py = x, y
            break
    state = GameState(world=world, player=player or Player(x=px, y=py))
    if player is not None:
        state.player.x, state.player.y = px, py
    # spawn enemies from bandit characters
    mult = {"easy": 0.7, "normal": 1.0, "hard": 1.35}.get(difficulty, 1.0)
    bandits = [c for c in world.characters if c.role == "bandit"] or world.characters[:4]
    # bounty targets with lairs dwell in their dungeons; only the unlaired roam
    laired = {q.target_enemy for q in list(world.quests) + list(world.dormant_quests)
              if q.kind == "bounty" and q.target_site}
    roamers = [b for b in bandits if b.name not in laired] or bandits
    scale = max(0.5, (world.width * world.height) / (150 * 85))
    target_foes = min(40, max(7, round((len(roamers) + 4) * scale)))
    # the wilds keep closer pace; the deep and frontier keep pace fully
    trail = trail_scale(state.player.level)
    for _ in range(target_foes):
        for _ in range(100):
            x, y = rng.randrange(w), rng.randrange(h)
            if grid[y][x] in WALKABLE and abs(x - px) + abs(y - py) > 5:
                foe = spawn_foe(world, x, y, rng, roamers, mult, level_scale=trail)
                if foe is not None:
                    state.enemies.append(foe)
                break
    # war breeds blades: extra bands prowl near cities of warring factions
    war_facs = {f.id for f in world.factions if f.at_war}
    war_cities = [c for c in world.cities if c.faction in war_facs]
    for _ in range(min(4, len(war_cities))):
        wc = rng.choice(war_cities)
        for _ in range(60):
            x = max(0, min(w - 1, wc.x + rng.randint(-12, 12)))
            y = max(0, min(h - 1, wc.y + rng.randint(-12, 12)))
            if world.grid[y][x] in WALKABLE and abs(x - px) + abs(y - py) > 5:
                foe = spawn_foe(world, x, y, rng, roamers, mult, level_scale=trail, force="soldier")
                if foe is not None:
                    state.enemies.append(foe)
                break
    # bandit camps post guards: two blades within two steps of each cache —
    # plus sown steel, so thief-work cuts both ways
    for camp in [s for s in world.sites if s.kind == "camp"]:
        placed = 0
        for _ in range(80):
            if placed >= 2:
                break
            x = max(0, min(w - 1, camp.x + rng.randint(-2, 2)))
            y = max(0, min(h - 1, camp.y + rng.randint(-2, 2)))
            if (world.grid[y][x] in WALKABLE and (x, y) != (camp.x, camp.y)
                    and abs(x - px) + abs(y - py) > 5
                    and not any(e.x == x and e.y == y for e in state.enemies)):
                foe = spawn_foe(world, x, y, rng, roamers, mult, level_scale=trail, force="bandit")
                if foe is not None:
                    state.enemies.append(foe)
                placed += 1
        if rng.random() < 0.6:
            if not hasattr(world, "traps") or not isinstance(world.traps, dict):
                world.traps = {}
            for _ in range(40):
                x = max(0, min(w - 1, camp.x + rng.randint(-3, 3)))
                y = max(0, min(h - 1, camp.y + rng.randint(-3, 3)))
                key = f"ow:{x}:{y}"
                if world.grid[y][x] in WALKABLE and key not in world.traps:
                    world.traps[key] = {"sub": rng.choice(["dart", "dart", "snare", "oil"]),
                                        "foe": True}
                    break
    state.log(f"Seed {world.seed}: {len(world.cities)} cities, "
                f"{len(world.sites)} wild sites, {len(world.races)} races.")
    state.log("Beasts, dead, soldiers, blades: read a foe before it reads you.")
    if war_cities:
        seen_wars = set()
        for f in world.factions:
            for foe in f.at_war:
                seen_wars.add(tuple(sorted((faction_name(world, f.id), faction_name(world, foe)))))
        if seen_wars:
            a, b = sorted(seen_wars)[0]
            state.log(f"War burns: {a} vs {b}. Borderlands crawl with blades.")
    state.log("O city, D dungeon, # ruin, * shrine, = road. E talks, J journal.")
    for q in world.quests:
        state.log(f"Known rumor: {q.title}")
    if world.dormant_quests:
        state.log(f"{len(world.dormant_quests)} unheard rumors linger in towns. Talk (E) to hear them.")
    return state


def _tally(world, key: str, n: int = 1) -> None:
    try:
        world.stats[key] = int(world.stats.get(key, 0)) + n
    except Exception:
        pass


def gain_xp(state: GameState, amount: int) -> None:
    p = state.player
    p.xp += amount
    while p.xp >= p.xp_needed:
        p.xp -= p.xp_needed
        _tally(state.world, "levels")
        p.level += 1
        p.max_hp += 6 + p.attr("CON") // 2
        p.atk += 2
        p.unspent += 1
        p.max_mana += 2
        p.mana = p.max_mana
        p.hp = min(p.max_hp, p.hp + p.max_hp // 2)
        state.log(f"+ LEVEL {p.level}! HP {p.max_hp}, ATK {p.atk}, +1 attribute point (see CHARACTERS).")
        if p.level % 5 == 0:
            p.perk_drafts += 1
            state.log(f"+ A perk draft awaits (level {p.level})! Press P in CHARACTERS.")
        play("level")


def apply_class_package(p: Player, cls: dict, terms: list[str],
                        rng: random.Random,
                        climate: dict | None = None) -> list[str]:
    """Dress a new hero in their calling: attributes, skills, gear, spells."""
    from .items import gen_item
    lines = []
    name = cls.get("name", "Commoner")
    p.class_name = name
    for k, v in (cls.get("mods") or {}).items():
        if k in p.attrs:
            p.attrs[k] = int(p.attrs.get(k, 4)) + int(v)
    for k, v in (cls.get("skills") or {}).items():
        if k in p.skills:
            p.skills[k] = int(p.skills.get(k, 0)) + int(v)
    for kind in (cls.get("gear") or [])[:2]:
        base_kind, _, want_style = kind.partition(":")
        if base_kind == "bow":
            from .items import gen_bow
            item = gen_bow(terms, rng, tier=1, climate=climate)
        else:
            item = gen_item(base_kind, terms, rng, tier=1, climate=climate)
            if want_style and (item.get("slot") or "") == "weapon" and not item.get("ranged"):
                prefix = {"swift": "Swift ", "heavy": "Great ", "spear": "Long ",
                          "sword": ""}.get(want_style, "")
                item["style"] = want_style or item.get("style", "sword")
                if prefix and not item["name"].startswith(prefix):
                    item["name"] = f"{prefix}{item['name']}"
        p.equipment[item["slot"]] = item
        lines.append(item["name"])
    for sid in (cls.get("spells") or []):
        if sid not in p.spells:
            p.spells.append(sid)
    p.max_mana = 8 + p.attr("WIS") * 4
    p.mana = p.max_mana
    return lines


def apply_race_package(p: Player, race) -> str:
    """Blood tells: attribute leans, a seeded skill, and a mana body to match."""
    mods = getattr(race, "mods", None) or {}
    for k, v in mods.items():
        if k in p.attrs:
            p.attrs[k] = int(p.attrs.get(k, 4)) + int(v)
    skill = getattr(race, "skill", "")
    if skill and skill in p.skills:
        p.skills[skill] = int(p.skills.get(skill, 0)) + 10
    p.max_mana = 8 + p.attr("WIS") * 4
    p.mana = p.max_mana
    return getattr(race, "blurb", "")


def add_skill(state: GameState, key: str, n: int) -> None:
    """Use-to-improve: progress a skill, announcing level-ups (max 10)."""
    p = state.player
    before = p.skill_level(key)
    p.skills[key] = int(p.skills.get(key, 0)) + n
    after = p.skill_level(key)
    if after > before:
        state.log(f"+ Skill up: {key.capitalize()} {after}!")


def xp_gain(p: Player, amount: int) -> int:
    from .items import eff_attr
    mult = 1 + eff_attr(p, "WIS") * 0.03 + eff_skill(p, "lore") * 0.02
    try:
        if (p.buffs or {}).get("rested", 0) > 0:
            mult += 0.15  # slept in your own bed: everything teaches faster
    except Exception:
        pass
    return max(1, round(amount * mult))


def melee_damage(p: Player, rng: random.Random,
                 state: GameState | None = None) -> tuple[int, bool, str]:
    from .items import eff_atk, eff_attr
    from .perks import perk_rank, perk_mag
    weapon = (p.equipment or {}).get("weapon") or {}
    dtype = weapon.get("element", "") or "physical"
    dmg = eff_atk(p) + eff_attr(p, "STR") // 3 + eff_skill(p, "blades") // 2 + rng.randint(-2, 3)
    r = perk_rank(p, "keeneye")
    bonus = perk_mag(state, "keeneye") * r / 100 if (r and state is not None) else 0
    buffs = p.buffs if hasattr(p, "buffs") else p.get("buffs", {})
    if (buffs or {}).get("berserk", 0) > 0:
        dmg += 6
    if (buffs or {}).get("focus", 0) > 0:
        crit = True
        if hasattr(p, "buffs"):
            p.buffs.pop("focus", None)
        else:
            p.get("buffs", {}).pop("focus", None)
    else:
        crit = rng.random() < 0.05 + eff_attr(p, "LUK") * 0.01 + bonus
    if crit:
        dmg *= 2
    return max(1, dmg), crit, dtype


def los_clear(grid: list[str], walk: set, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Bresenham sight: every tile between the endpoints must be walkable.
    Endpoints are exempt (archers lean out of scrub, targets duck behind none)."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    x, y = x0, y0
    if dx >= dy:
        err = dx // 2
        while x != x1:
            x += sx
            err -= dy
            if err < 0:
                y += sy
                err += dx
            if (x, y) != (x1, y1) and grid[y][x] not in walk:
                return False
    else:
        err = dy // 2
        while y != y1:
            y += sy
            err -= dx
            if err < 0:
                x += sx
                err += dy
            if (x, y) != (x1, y1) and grid[y][x] not in walk:
                return False
    return True


def has_los(state: GameState, x0: int, y0: int, x1: int, y1: int) -> bool:
    grid, WW, HH = _play_grid(state)
    if not (0 <= x0 < WW and 0 <= y0 < HH and 0 <= x1 < WW and 0 <= y1 < HH):
        return False
    return los_clear(grid, _play_walk(state), x0, y0, x1, y1)


def ranged_damage(p: Player, rng: random.Random,
                  state: GameState | None = None) -> tuple[int, bool, str]:
    """Bow volley: ~90% of melee weight; LUK steadies the hand, not STR."""
    from .items import eff_atk, eff_attr, wielded_bow
    from .perks import perk_rank, perk_mag
    bow = wielded_bow(p) or {}
    dtype = bow.get("element", "") or "physical"
    dmg = round(eff_atk(p) * 0.9) + eff_skill(p, "blades") // 2 + rng.randint(-2, 2)
    r = perk_rank(p, "keeneye")
    bonus = perk_mag(state, "keeneye") * r / 100 if (r and state is not None) else 0
    buffs = p.buffs if hasattr(p, "buffs") else p.get("buffs", {})
    if (buffs or {}).get("berserk", 0) > 0:
        dmg += 6
    if (buffs or {}).get("focus", 0) > 0:
        crit = True
        if hasattr(p, "buffs"):
            p.buffs.pop("focus", None)
        else:
            p.get("buffs", {}).pop("focus", None)
    else:
        crit = rng.random() < 0.05 + eff_attr(p, "LUK") * 0.01 + bonus
    if crit:
        dmg *= 2
    return max(1, dmg), crit, dtype


def _nearest_volley_target(state: GameState) -> Enemy | None:
    """Nearest living foe inside the bow window with a clear lane."""
    from .items import BOW_MIN, BOW_MAX
    p = state.player
    best, best_d = None, None
    for e in state.enemies:
        if not _hostile(e):
            continue
        d = abs(e.x - p.x) + abs(e.y - p.y)
        if BOW_MIN <= d <= BOW_MAX and has_los(state, p.x, p.y, e.x, e.y):
            if best_d is None or d < best_d:
                best, best_d = e, d
    return best


def combat_shoot(state: GameState, rng: random.Random | None = None) -> None:
    """R key: loose an arrow. Out of grapple it strikes 2-4 tiles down a
    clear lane (and the wilds answer); sharing a tile it is an awkward
    half-draw followed by the usual reply."""
    from .items import BOW_MIN, BOW_MAX, wielded_bow
    rng = rng or random.Random()
    p = state.player
    if p.hp <= 0:
        return
    if wielded_bow(p) is None:
        state.log("No bow drawn (wield one from INVENTORY). Ranged steel shoots 2-4.")
        return
    if p.ammo <= 0:
        state.log("Quiver empty! Loot quivers, buy them, or burn a quiver (U) from the pack.")
        return
    p.last_strike = state.turns
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if e is not None and e.alive and abs(e.x - p.x) + abs(e.y - p.y) <= 1:
        p.ammo -= 1
        dmg, crit, dtype = ranged_damage(p, rng, state)
        raw = max(1, dmg // 2)
        add_skill(state, "blades", 1)
        state.log(f"Too close to draw fully on {e.name}!")
        if _hit_foe(state, e, raw, dtype, rng, crit, verb="Your arrow nicks"):
            _status_tick(state, rng)
            return
        _foe_counter(state, e, rng)
        _status_tick(state, rng)
        return
    tgt = _nearest_volley_target(state)
    if tgt is None:
        state.log(f"No foe drawn within {BOW_MIN}-{BOW_MAX} tiles down a clear lane.")
        return
    p.ammo -= 1
    dmg, crit, dtype = ranged_damage(p, rng, state)
    add_skill(state, "blades", 2)
    killed = _hit_foe(state, tgt, dmg, dtype, rng, crit, verb="Your arrow catches")
    advance(state, 5)
    if not killed:
        # the bowstring is loud: a far foe marks where you stand
        if abs(tgt.x - p.x) + abs(tgt.y - p.y) > aggro_radius(state):
            grid, WW, HH = _play_grid(state)
            walk = _play_walk(state)
            dx = (p.x > tgt.x) - (p.x < tgt.x)
            dy = (p.y > tgt.y) - (p.y < tgt.y)
            nx, ny = tgt.x + dx, tgt.y + dy
            if (dx or dy) and 0 <= nx < WW and 0 <= ny < HH \
                    and grid[ny][nx] in walk \
                    and not any(f.alive and f.x == nx and f.y == ny for f in state.enemies):
                tgt.x, tgt.y = nx, ny
    _enemy_turn(state, rng)
    _status_tick(state, rng)


# Flesh remembers: weaknesses (+50%) and resistances (half).
KIND_AFFINITY = {
    "beast": (["ember"], []),
    "spider": (["frost"], []),
    "undead": (["ember"], ["frost"]),
    "wraith": (["storm"], ["physical"]),
    "golem": (["storm"], ["physical"]),
    "drake": (["frost"], ["ember"]),
    "mage": ([], []),
    "specter": ([], []),
    "soldier": ([], []),
    "bandit": ([], []),
}
OPPOSITE = {"ember": "frost", "frost": "ember", "storm": "umbral", "umbral": "storm"}
# Typed fangs: drakes breathe, wraiths unmake.
FOE_DTYPE = {"drake": "ember", "wraith": "umbral"}


def foe_affinity(e: Enemy) -> tuple[list, list]:
    weak, resist = KIND_AFFINITY.get(e.kind, ([], []))
    weak, resist = list(weak), list(resist)
    if e.attune:
        if e.attune not in resist:
            resist.append(e.attune)
        opp = OPPOSITE.get(e.attune, "")
        if opp and opp not in weak:
            weak.append(opp)
    return weak, resist


def apply_affinity(dmg: int, dtype: str, e: Enemy) -> tuple[int, str]:
    weak, resist = foe_affinity(e)
    if dtype in weak:
        return max(1, round(dmg * 1.5)), "weak"
    if dtype in resist:
        return max(1, dmg // 2), "resisted"
    return dmg, ""


def heal_cost(p: Player) -> int:
    from .items import eff_attr
    return max(1, 5 - eff_attr(p, "CHA") // 3 - eff_skill(p, "speech") // 2)


def flee_chance(p: Player, state: GameState | None = None) -> float:
    from .items import eff_attr
    from .perks import perk_rank, perk_mag
    base = min(0.9, 0.6 + eff_attr(p, "SPD") * 0.02)
    r = perk_rank(p, "fleetfoot")
    if r:
        mag = perk_mag(state, "fleetfoot") if state is not None else 8
        base = min(0.95, base + mag * r / 100)
    buffs = p.buffs if hasattr(p, "buffs") else p.get("buffs", {})
    if (buffs or {}).get("swift", 0) > 0:
        base = min(0.95, base + 0.15)
    if (buffs or {}).get("tangle", 0) > 0:
        base = max(0.05, base - 0.2)  # snared ankles run slow
    return base


def aggro_radius(state: GameState) -> int:
    from .items import eff_attr
    r = 6 - eff_attr(state.player, "SPD") // 4 - eff_skill(state.player, "sneak") // 3
    phase = clock_phase(state.world.clock)
    if phase == "night":
        r -= 2
    elif phase in ("dawn", "dusk"):
        r -= 1
    return max(3, r)


def clock_phase(minutes: int) -> str:
    h = (minutes // 60) % 24
    if 5 <= h < 8:
        return "dawn"
    if 8 <= h < 18:
        return "day"
    if 18 <= h < 21:
        return "dusk"
    return "night"


def clock_str(minutes: int) -> str:
    day = minutes // 1440 + 1
    h, m = (minutes // 60) % 24, minutes % 60
    return f"Day {day}, {h:02d}:{m:02d} ({clock_phase(minutes)})"


def advance(state: GameState, minutes: int) -> None:
    before = clock_phase(state.world.clock)
    state.world.clock += minutes
    after = clock_phase(state.world.clock)
    if after != before and state.last_phase_announced != after:
        state.last_phase_announced = after
        whispers = {"dawn": "Dawn breaks over the realm.",
                    "day": "The sun climbs high.",
                    "dusk": "Dusk settles. Shadows lengthen.",
                    "night": "Night falls. Blades move unseen (foes notice you later)."}
        state.log(whispers[after])
    # urgent hours pass: overdue work simply vanishes from the log
    today = state.world.clock // 1440
    for q in list(state.world.quests):
        if q.deadline_day and today > q.deadline_day and q.act == 0:
            state.world.quests.remove(q)
            state.log(f"The hour passed: {q.title}. Gone.")
    _brew_war(state)


def _complete_quest(state: GameState, quest) -> None:
    p = state.player
    if quest in state.world.quests:
        state.world.quests.remove(quest)
    elif quest in state.world.dormant_quests:
        state.world.dormant_quests.remove(quest)
    if quest.id not in state.world.completed_quests:
        state.world.completed_quests.append(quest.id)
    p.quests_done += 1
    from .items import eff_attr as _ea
    bonus = eff_skill(p, "speech") + _ea(p, "CHA") // 2
    try:
        if (p.buffs or {}).get("inspire", 0) > 0:
            bonus += 5  # the song precedes you: tales pay better
    except Exception:
        pass
    p.gold += quest.reward_gold + bonus
    _tally(state.world, "quests")
    xp = xp_gain(p, quest.reward_xp)
    state.log(f"+ Quest done: {quest.title}! +{quest.reward_gold + bonus}g +{xp}xp.")
    play("quest")
    add_skill(state, "speech", 3)
    add_skill(state, "lore", 2)
    gain_xp(state, xp)
    from .items import quest_reward_item
    prize = quest_reward_item(quest.kind, name_pool(state.world),
                              random.Random(state.world.seed + len(state.world.completed_quests) * 131),
                              p.level, climate=state.world.climate)
    if prize is not None:
        give_item(state, prize, "Reward")
    from .plot import advance_plot
    advance_plot(state, quest.id)
    _chain_followup(state, quest)
    _saga_advance(state, quest)
    if not state.world.quests and not state.world.dormant_quests:
        _fresh_rumors(state)


def _saga_advance(state: GameState, quest) -> None:
    """Book sagas turn the page: completing I/II releases the vaulted next part."""
    from .quests import Quest as _Q
    w = state.world
    saga = getattr(quest, "saga", "") or ""
    if not saga:
        return
    vault = getattr(w, "book_sagas", None)
    if not isinstance(vault, dict) or saga not in vault:
        return
    rest = vault.get(saga) or []
    if not rest:
        return
    nxt = rest.pop(0)
    try:
        q = _Q.from_dict(nxt)
    except Exception:
        return
    if q.id in {x.id for x in w.quests} or q.id in (w.completed_quests or []):
        return
    w.dormant_quests.append(q)
    if not rest:
        try:
            del vault[saga]
        except Exception:
            pass
    state.log(f"The saga turns... (a new rumor stirs near {q.giver}).")


def _chain_followup(state: GameState, quest) -> None:
    """Every third completed side tale births a linked one (same folk, new trouble)."""
    from .quests import Quest
    w = state.world
    if quest.act != 0 or len(w.completed_quests) % 3 != 0:
        return
    home = {c.name: c.city for c in w.characters}
    base_city = home.get(quest.giver, "") or (w.cities[0].name if w.cities else "")
    others = [c.name for c in w.cities if c.name != base_city]
    bandits = [c.name for c in w.characters if c.role == "bandit"] or ["the Red Hood"]
    n = len(w.completed_quests)
    new = None
    if quest.kind == "bounty" and others:
        new = Quest(id=f"{quest.id}-ii-{n}", kind="escort", title=f"Guide {quest.giver} Home",
                    giver=quest.giver, target_city=base_city or others[0],
                    companion=quest.giver,
                    flavor=f"Shaken, {quest.giver} wants company on the road home.",
                    reward_gold=14, reward_xp=30)
    elif quest.kind == "explore":
        scholar = next((c.name for c in w.characters
                        if c.role != "bandit" and c.city == base_city), quest.giver)
        tgt = next((c for c in others if c != home.get(scholar, "")), base_city)
        new = Quest(id=f"{quest.id}-ii-{n}", kind="deliver",
                    title=f"Word of {quest.target_site} for {tgt}",
                    giver=scholar, target_city=tgt,
                    flavor=f"{scholar} must tell {tgt} what sleeps in {quest.target_site}.",
                    reward_gold=12, reward_xp=30)
    elif quest.kind == "deliver" and others:
        tgt = next((c for c in others if c != base_city), others[0])
        new = Quest(id=f"{quest.id}-ii-{n}", kind="tribute",
                    title=f"Tribute of 40g for {tgt}", giver=quest.giver,
                    target_city=tgt, amount=40,
                    flavor=f"Emboldened, {quest.giver} levies tribute for {tgt}.",
                    reward_gold=8, reward_xp=30)
    elif quest.kind == "escort":
        new = Quest(id=f"{quest.id}-ii-{n}", kind="bounty",
                    title=f"Bounty: {bandits[n % len(bandits)]}",
                    giver=quest.giver, target_enemy=bandits[n % len(bandits)],
                    flavor=f"The ambushers on the road are named. {quest.giver} wants blood.",
                    reward_gold=18, reward_xp=40)
    elif quest.kind == "hunt":
        foes = [f.name for f in w.factions] or ["raiders"]
        new = Quest(id=f"{quest.id}-ii-{n}", kind="hunt",
                    title=f"Cull 3 {foes[n % len(foes)]} raiders",
                    giver=quest.giver, target_enemy=foes[n % len(foes)], amount=3,
                    flavor="They keep coming. Thin them again.",
                    reward_gold=16, reward_xp=40)
    elif quest.kind == "tribute" and others:
        tgt = next((c for c in others if c != base_city), others[0])
        new = Quest(id=f"{quest.id}-ii-{n}", kind="deliver",
                    title=f"Receipts for {tgt}", giver=quest.giver, target_city=tgt,
                    flavor=f"The tribute is paid; {tgt} must hear of it.",
                    reward_gold=12, reward_xp=30)
    if new is not None and new.id not in {q.id for q in w.quests} \
            and new.id not in w.completed_quests:
        w.dormant_quests.append(new)
        state.log(f"Word spreads from this deed... (a new rumor stirs near {base_city or 'town'}).")


def _maybe_urgent(state: GameState, q) -> None:
    """One in four bounties/hunts/escorts is time-bound (4 days, set on hearing)."""
    if q.kind not in ("bounty", "hunt", "escort") or q.deadline_day:
        return
    if sum(ord(c) for c in q.id) % 4 == 0:
        q.deadline_day = state.world.clock // 1440 + 4


# ---------------- companions (escort NPCs fight) ----------------
# Bodies on the road: every active escort grows one follower that trails the @,
# strikes adjacent foes, and can be beaten down (never slain: the down rise when
# the road is safe). Hurt persists on the quest (comp_hp: 0 = hale, -1 = down).

def _escort_quests(state: GameState) -> list:
    return [q for q in state.world.quests if q.kind == "escort" and q.companion]


def comp_max_hp(state: GameState) -> int:
    return 30 + state.player.level * 5


def comp_atk(state: GameState) -> int:
    return 4 + state.player.level // 2


def comp_status(state: GameState, q) -> tuple[str, int]:
    """(standing, hp): hale | wounded | down. Legacy/zero hurt means hale."""
    if q.comp_hp == -1:
        return "down", 0
    if q.comp_hp and q.comp_hp > 0:
        return "wounded", min(int(q.comp_hp), comp_max_hp(state))
    return "hale", comp_max_hp(state)


def companion_line(state: GameState, q) -> str:
    standing, hp = comp_status(state, q)
    if standing == "down":
        return f"o {q.companion} is down! (rises when the road is safe)"
    if standing == "wounded":
        return (f"o {q.companion} fights beside you ({hp}/{comp_max_hp(state)}hp)"
                f" -> {q.target_city[:24]}")
    return f"o {q.companion} follows you -> {q.target_city[:24]}"


def _sync_companions(state: GameState) -> None:
    """Prune the finished, birth the new, reel in the far, raise the down."""
    live = {q.id for q in _escort_quests(state)}
    for qid in list(state.companions):
        if qid not in live:
            del state.companions[qid]
    p = state.player
    for q in _escort_quests(state):
        c = state.companions.setdefault(q.id, {"x": p.x, "y": p.y})
        if abs(c["x"] - p.x) + abs(c["y"] - p.y) > 8:
            c["x"], c["y"] = p.x, p.y
        if q.comp_hp == -1 and not any(
                e.alive and abs(e.x - p.x) + abs(e.y - p.y) <= 6 for e in state.enemies):
            q.comp_hp = comp_max_hp(state) // 2
            state.log(f"+ {q.companion} staggers back up!")


def _companion_follow(state: GameState) -> None:
    """One trailing step per stride, overworld only (they wait at delves)."""
    if state.interior is not None:
        return
    _sync_companions(state)
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    p = state.player
    blocked = {(e.x, e.y) for e in state.enemies if e.alive}
    for q in _escort_quests(state):
        if comp_status(state, q)[0] == "down":
            continue
        c = state.companions[q.id]
        if abs(c["x"] - p.x) + abs(c["y"] - p.y) <= 1:
            continue
        dx = (p.x > c["x"]) - (p.x < c["x"])
        dy = (p.y > c["y"]) - (p.y < c["y"])
        prefs = [(dx, 0), (0, dy)] if abs(p.x - c["x"]) >= abs(p.y - c["y"]) else [(0, dy), (dx, 0)]
        for sx, sy in prefs:
            if not sx and not sy:
                continue
            nx, ny = c["x"] + sx, c["y"] + sy
            if (0 <= nx < WW and 0 <= ny < HH and grid[ny][nx] in walk
                    and (nx, ny) not in blocked):
                c["x"], c["y"] = nx, ny
                break


def _companion_turn(state: GameState, rng: random.Random) -> None:
    """After foes close: companions strike adjacent blades, and loose blades
    nip back at them. Overworld only; grappled foes are the hero's own."""
    if state.interior is not None:
        return
    for q in _escort_quests(state):
        if comp_status(state, q)[0] == "down":
            continue
        c = state.companions[q.id]
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - c["x"]) + abs(e.y - c["y"]) <= 1]
        if not foes:
            continue
        tgt = min(foes, key=lambda e: e.hp)
        raw = max(1, comp_atk(state) + rng.randint(-1, 2))
        _hit_foe(state, tgt, raw, "physical", rng, verb=f"{q.companion} strikes")
    for q in _escort_quests(state):
        standing, hp = comp_status(state, q)
        if standing == "down":
            continue
        c = state.companions[q.id]
        for e in state.enemies:
            if (_hostile(e) and e is not state.in_combat_with
                    and abs(e.x - c["x"]) + abs(e.y - c["y"]) <= 1
                    and abs(e.x - state.player.x) + abs(e.y - state.player.y) > 0):
                nick = max(1, e.atk // 2 + rng.randint(-1, 1))
                if _class_template(state) == "paladin":
                    nick = max(1, nick - 1)  # the aura stands between
                left = hp - nick
                if left <= 0:
                    q.comp_hp = -1
                    state.log(f"! {e.name} beats {q.companion} down! (Safe road revives.)")
                    break
                q.comp_hp = left
                hp = left
                state.log(f"! {e.name} nicks {q.companion} ({max(0, left)} left).")


def _beast_howl(state: GameState, e: Enemy, rng: random.Random) -> None:
    """Blood calls blood: a struck beast howls and the pack answers (cap 5 near)."""
    near = sum(1 for f in state.enemies if f.alive
               and abs(f.x - e.x) + abs(f.y - e.y) <= 6)
    if near >= 5:
        return
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    opts = [(e.x + dx, e.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= e.x + dx < WW and 0 <= e.y + dy < HH
            and grid[e.y + dy][e.x + dx] in walk
            and not any(f.alive and f.x == e.x + dx and f.y == e.y + dy
                        for f in state.enemies)]
    if not opts:
        return
    x, y = rng.choice(opts)
    pup = spawn_foe(state.world, x, y, rng, [],
                    level_scale=max(0, (state.player.level - 1) // 2), force="beast")
    if pup is None:
        return
    state.enemies.append(pup)
    state.log(f"! {e.name} howls — the pack answers! ({pup.name} bounds in.)")


def _boss_enrage(state: GameState, e: Enemy) -> None:
    """A third health gone: harder blows, hungrier heavies, charm snapped."""
    e.enraged = True
    e.atk = max(e.atk + 2, round(e.atk * 1.5))
    e.charmed = 0
    state.log(f"! {e.name} ENRAGES! Blows hit harder and heavies come hungry.")
    state.ping(e.x, e.y, "ENRAGED", (255, 60, 60))
    state.flash(e.x, e.y)


def _foe_draught(state: GameState, e: Enemy) -> bool:
    """Humanoids carry one draught and quaff it under half health (costs the turn)."""
    if not e.draught or not e.alive:
        return False
    if e.max_hp <= 0 or e.hp * 2 >= e.max_hp:
        return False
    e.draught = False
    e.hp = min(e.max_hp, e.hp + 15)
    state.log(f"! {e.name} quaffs a draught ({max(0, e.hp)} left).")
    return True


def _boss_warcry(state: GameState, e: Enemy, rng: random.Random) -> None:
    """Two-thirds gone: the boss roars and guards rush in (once, cap 8 standing)."""
    if sum(1 for f in state.enemies if f.alive) >= 8:
        return
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    opts = [(e.x + dx, e.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= e.x + dx < WW and 0 <= e.y + dy < HH
            and grid[e.y + dy][e.x + dx] in walk
            and not any(f.alive and f.x == e.x + dx and f.y == e.y + dy
                        for f in state.enemies)]
    if not opts:
        return
    e.cried = True
    for x, y in opts[:2]:
        guard = spawn_foe(state.world, x, y, rng, [],
                          level_scale=max(0, (state.player.level - 1) // 2),
                          force="soldier")
        if guard is not None:
            state.enemies.append(guard)
    state.log(f"! {e.name} roars — guards rush in!")


def _discover(state: GameState, city_name: str) -> int:
    """Hear unheard rumors from locals: dormant quests whose giver lives here
    move into the active log."""
    home = {c.name: c.city for c in state.world.characters}
    found = 0
    for q in list(state.world.dormant_quests):
        if home.get(q.giver) == city_name:
            state.world.dormant_quests.remove(q)
            state.world.quests.append(q)
            _maybe_urgent(state, q)
            state.log(f"Rumor heard: {q.title} (J for journal).")
            found += 1
    return found


def _find_quest(state: GameState, kind: str, target: str):
    for q in state.world.quests:
        if q.kind == kind and (q.target_city or q.target_enemy or q.target_site) == target:
            return q
    for q in state.world.dormant_quests:
        if q.kind == kind and (q.target_city or q.target_enemy or q.target_site) == target:
            return q
    return None


def quest_target_pos(state: GameState, quest) -> tuple[int, int] | None:
    """Where the compass points for one quest (enemy positions are live)."""
    w = state.world
    city = next((c for c in w.cities if c.name == quest.target_city), None)
    if quest.kind in ("deliver", "escort", "tribute") and city is not None:
        return city.x, city.y
    site = next((s for s in w.sites if s.name == (quest.target_site or "")), None)
    if quest.kind in ("explore", "relic", "finale") and site is not None:
        return site.x, site.y
    if quest.kind == "pilgrimage":
        shrines = [s for s in w.sites if s.kind == "shrine"]
        if shrines:
            best = min(shrines, key=lambda s: abs(s.x - state.player.x) + abs(s.y - state.player.y))
            return best.x, best.y
        return None
    if quest.kind == "treasure" and quest.target_x >= 0:
        return quest.target_x, quest.target_y
    if quest.kind in ("bounty", "hunt"):
        foes = [e for e in state.enemies if e.alive and
                (quest.target_enemy in e.name or quest.kind == "hunt")]
        if quest.kind == "hunt" and not foes:
            foes = [e for e in state.enemies if e.alive]
        if foes:
            best = min(foes, key=lambda e: abs(e.x - state.player.x) + abs(e.y - state.player.y))
            return best.x, best.y
        if site is not None:
            return site.x, site.y
        return None
    return None


def caravan_ride(state: GameState, dest_name: str, rng: random.Random | None = None) -> bool:
    """F key in a visited city: pay gold, ride the roads, risk the road."""
    rng = rng or random.Random()
    w = state.world
    if state.interior is not None or state.in_combat_with:
        return False
    p = state.player
    home = next((c for c in w.cities if c.x == p.x and c.y == p.y), None)
    dest = next((c for c in w.cities if c.name == dest_name), None)
    if home is None or dest is None or dest.name == home.name:
        return False
    if dest.name not in (w.visited or []):
        state.log(f"No road-song for {dest.name} yet — walk there first.")
        return False
    dist = abs(dest.x - home.x) + abs(dest.y - home.y)
    fare = max(5, dist // 5)
    if p.oath and home.faction == p.oath:
        fare = max(3, fare // 2)
        state.log(f"Sworn rates: the caravan asks {fare}g to {dest.name}.")
    if (p.buffs or {}).get("inspire", 0) > 0:
        fare = max(3, fare * 3 // 4)
        state.log(f"They heard your songs: the caravan asks {fare}g to {dest.name}.")
    if p.gold < fare:
        state.log(f"The caravan wants {fare}g to {dest.name}.")
        return False
    p.gold -= fare
    advance(state, max(30, dist * 2))
    p.x, p.y = dest.x, dest.y
    state.log(f"The caravan rolls into {dest.name} (-{fare}g).")
    for q in _escort_quests(state):
        state.companions[q.id] = {"x": p.x, "y": p.y}
    if rng.random() < 0.15:
        bandits = [c for c in w.characters if c.role == "bandit"]
        if bandits:
            b = rng.choice(bandits)
            state.enemies.append(Enemy(name=b.name, x=dest.x, y=dest.y, hp=b.hp, atk=b.atk))
            state.in_combat_with = state.enemies[-1]
            state.log(f"! Ambush on the road! {b.name} was waiting.")
    return True


def _fresh_rumors(state: GameState) -> None:
    """Endless but never repeating: new batch excluding everything done."""
    from .quests import build_quests
    import random as _r
    w = state.world
    rng = _r.Random(w.seed + len(w.completed_quests) * 7919)
    batch = build_quests(w.characters, w.cities, w.sites, w.lore_terms,
                         [], rng, exclude=set(w.completed_quests), count=10,
                         factions=w.factions,
                         city_faction={c.name: c.faction for c in w.cities},
                         grid=w.grid)
    if batch:
        w.dormant_quests.extend(batch)
        state.log("+ New rumors drift on the wind. Ask in towns to hear them.")
    else:
        state.log("+ The realm is at peace. Every tale told.")


def _play_grid(state: GameState) -> tuple[list[str], int, int]:
    """Current map: the dungeon underfoot, or the overworld."""
    if state.interior is not None:
        g = state.interior["grid"]
        return g, len(g[0]), len(g)
    return state.world.grid, state.world.width, state.world.height


def _play_walk(state: GameState) -> set:
    from .dungeon import WALKABLE_IN, WALKABLE_TOWN
    if state.interior is not None:
        if state.interior.get("kind") == "city":
            return WALKABLE_TOWN
        return WALKABLE_IN
    from .worldgen import WALKABLE
    return WALKABLE


def site_memory(world, site_name: str) -> dict:
    return world.site_states.setdefault(
        site_name, {"boss_dead": False, "chests": [], "tablets": []})


def move_player(state: GameState, dx: int, dy: int, rng: random.Random | None = None) -> None:
    if state.in_combat_with:
        state.log("You are in combat! (A)ttack, (R) shoot, or (F)lee.")
        return
    if getattr(state.world, "director_active", None):
        state.log("The road demands an answer (open the event: Y).")
        return
    rng = rng or random.Random()
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    inside = state.interior is not None
    nx = max(0, min(WW - 1, state.player.x + dx))
    ny = max(0, min(HH - 1, state.player.y + dy))
    tile = grid[ny][nx]
    if tile not in walk:
        state.log("Blocked.")
        return
    state.player.x, state.player.y = nx, ny
    advance(state, 10)
    state.turns += 1
    state.player.mana = min(state.player.max_mana, state.player.mana + 1)
    # buffs tick; the feast knits as you walk
    for b in list(state.player.buffs):
        state.player.buffs[b] -= 1
        if state.player.buffs[b] <= 0:
            del state.player.buffs[b]
            state.log(f"The {b} fades.")
    if state.player.buffs.get("feast", 0) > 0:
        from .items import eff_max_hp as _emh
        state.player.hp = min(_emh(state.player), state.player.hp + 2)
    if state.player.poison > 0:
        _status_tick(state, rng)
        if state.player.hp <= 0:
            return
    _companion_follow(state)
    if inside:
        from .dungeon import CHEST
        if tile == CHEST:
            _open_chest(state, nx, ny, rng)
        # enemy encounter
        for e in state.enemies:
            if e.alive and e.x == nx and e.y == ny:
                _ghost = (state.player.buffs or {}).get("ghost", 0) > 0
                if getattr(e, "ally", False):
                    state.log("Your spectral falls in beside you.")
                    break
                if (e.faction and e.faction == state.player.oath) or _ghost:
                    state.log(f"{e.name} nods you through." if not _ghost
                              else "Unseen, you drift past.")
                    break
                state.in_combat_with = e
                state.log(f"! Ambushed by {e.name}! (A)ttack, (R) shoot, or (F)lee.")
                return
        if state.interior.get("kind") == "city":
            _npc_turn(state, rng)
        else:
            _enemy_turn(state, rng)
        return
    # city arrival
    for city in state.world.cities:
        if city.x == nx and city.y == ny:
            if city.name not in state.world.visited:
                state.world.visited.append(city.name)
            try:
                state.world.tension = max(0.0, float(getattr(state.world, "tension", 0.0) or 0.0) - 30.0)
            except Exception:
                pass
            state.log(f"Entered {city.name}. (H)eal {heal_cost(state.player)}g/10hp. E to ask rumors. Z to rest.")
            found = _find_quest(state, "escort", city.name)
            if found:
                _complete_quest(state, found)
                break
    # wild site discovery
    for s in state.world.sites:
        if s.x == nx and s.y == ny:
            state.log(f"Discovered {s.name} ({s.kind}). Press E to enter.")
            if s.lore:
                state.log(f"Old tale: {s.lore}")
            add_skill(state, "lore", 3)
            add_skill(state, "survival", 1)
            found = _find_quest(state, "explore", s.name)
            if found:
                _complete_quest(state, found)
                break
    # enemy encounter
    for e in state.enemies:
        if e.alive and e.x == nx and e.y == ny:
            _ghost = (state.player.buffs or {}).get("ghost", 0) > 0
            if getattr(e, "ally", False):
                state.log("Your spectral falls in beside you.")
                break
            if (e.faction and e.faction == state.player.oath) or _ghost:
                state.log(f"{e.name} nods you through." if not _ghost
                          else "Unseen, you drift past.")
                break
            state.in_combat_with = e
            state.log(f"! Ambushed by {e.name}! (A)ttack, (R) shoot, or (F)lee.")
            return
    _check_relic(state)
    # buried caches: stand on the X
    for q in list(state.world.quests):
        if q.kind == "treasure" and q.target_x == nx and q.target_y == ny:
            _complete_quest(state, q)
            break
    # sown steel bites heroes too (camps lay for you, not for them)
    if not inside:
        _spring_trap_hero(state, rng)
    # escorting painted folk: the road sometimes objects
    if any(q.kind == "escort" for q in state.world.quests) and rng.random() < 0.06:
        bandits = [c for c in state.world.characters if c.role == "bandit"]
        if bandits:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ax, ay = nx + dx, ny + dy
                if (0 <= ax < state.world.width and 0 <= ay < state.world.height
                        and grid[ay][ax] in walk
                        and not any(e.alive and e.x == ax and e.y == ay for e in state.enemies)):
                    b = rng.choice(bandits)
                    state.enemies.append(Enemy(name=b.name, x=ax, y=ay, hp=b.hp, atk=b.atk))
                    comp = next(q.companion for q in state.world.quests if q.kind == "escort")
                    state.log(f"! Blades in the dark — for {comp}! {b.name} bars the way.")
                    break
    # event director: tension-paced road deck (+ chained follow-ups)
    try:
        from .director import tick_travel as _director_tick
        _director_tick(state, rng)
    except Exception:
        pass
    _enemy_turn(state, rng)
    if state.in_combat_with:
        return
    if any(e.alive and abs(e.x - nx) + abs(e.y - ny) == 1 for e in state.enemies):
        add_skill(state, "sneak", 1)  # breathed the same air and lived
    _ecology_tick(state, rng)
    _maybe_expand(state, rng)


AGGRO_RADIUS = 6


def _enemy_turn(state: GameState, rng: random.Random) -> None:
    """Foes are no longer statues: they wander, and close ranks when they
    scent you. Same speed as you, so running in a straight line escapes."""
    p = state.player
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    taken = {(e.x, e.y) for e in state.enemies if e.alive}
    for e in list(state.enemies):
        if not e.alive:
            continue
        if e.burn > 0:
            e.burn -= 1
            e.hp -= 2
            if not e.alive:
                state.log(f"{e.name} burns down!")
                _slay(state, e, rng)
                continue
            taken.discard((e.x, e.y))
        else:
            taken.discard((e.x, e.y))
        if e.blind > 0:
            e.blind -= 1  # glitter in the eyes: no volleys this turn
        if getattr(e, "cowed", False):
            taken.add((e.x, e.y))  # broken: it will not fight
            continue
        if getattr(e, "routed", 0) > 0:
            e.routed -= 1
            dx = (e.x > p.x) - (e.x < p.x)
            dy = (e.y > p.y) - (e.y < p.y)
            fled = False
            for sx, sy in ((dx, 0), (0, dy)):
                if not sx and not sy:
                    continue
                nx, ny = e.x + sx, e.y + sy
                if (0 <= nx < WW and 0 <= ny < HH
                        and grid[ny][nx] in walk and (nx, ny) not in taken):
                    e.x, e.y = nx, ny
                    fled = True
                    break
            taken.add((e.x, e.y))
            if e.routed <= 0 or not fled:
                e.hp = 0
                gain_xp(state, xp_gain(p, 10))
                state.log(f"{e.name} flees into the dark.")
            continue
        if getattr(e, "frenzied", 0) > 0:
            e.frenzied -= 1
            pack = [o for o in state.enemies if _hostile(o) and o is not e
                    and abs(o.x - e.x) + abs(o.y - e.y) <= 1]
            taken.add((e.x, e.y))
            if pack:
                tgt = rng.choice(pack)
                tgt.hp -= max(1, e.atk)
                state.log(f"Frenzied {e.name} mauls {tgt.name}!")
                if not tgt.alive:
                    _slay(state, tgt, rng)
            continue
        if getattr(e, "ally", False):
            e.ally_ttl -= 1
            taken.add((e.x, e.y))
            if e.ally_ttl <= 0:
                e.hp = 0
                state.log(f"{e.name} dissolves into mist. Well served.")
                continue
            prey = [o for o in state.enemies if _hostile(o)]
            if prey:
                tgt = min(prey, key=lambda o: abs(o.x - e.x) + abs(o.y - e.y))
                if abs(tgt.x - e.x) + abs(tgt.y - e.y) <= 1:
                    tgt.hp -= max(1, e.atk + rng.randint(-1, 2))
                    state.log(f"{e.name} savages {tgt.name}!")
                    if not tgt.alive:
                        _slay(state, tgt, rng)
                else:
                    dx = (tgt.x > e.x) - (tgt.x < e.x)
                    dy = (tgt.y > e.y) - (tgt.y < e.y)
                    for sx, sy in (((dx, 0), (0, dy)) if dx or dy else ()):
                        nx, ny = e.x + sx, e.y + sy
                        if (0 <= nx < WW and 0 <= ny < HH
                                and grid[ny][nx] in walk and (nx, ny) not in taken
                                and not (nx == p.x and ny == p.y)):
                            e.x, e.y = nx, ny
                            taken.add((nx, ny))
                            break
            continue
        if getattr(e, "slowed", 0) > 0:
            e.slowed -= 1  # yrden frost: every other step stolen
        if e.kind == "undead" and state.turns % 2 == 1:
            taken.add((e.x, e.y))  # the dead shamble every other step
            continue
        if getattr(e, "slowed", 0) > 0 and state.turns % 2 == 1:
            taken.add((e.x, e.y))
            continue
        if e.kind == "golem" and state.turns % 3 != 0:
            taken.add((e.x, e.y))  # stone is patient
            continue
        if _foe_draught(state, e):
            taken.add((e.x, e.y))
            continue
        radius = aggro_radius(state) + (2 if e.kind in ("beast", "spider") else 0)
        if e.kind == "wraith" and clock_phase(state.world.clock) != "night":
            radius = 0  # wraiths only hunger after dark
        if e.charmed > state.turns:
            radius = 0  # charmed blades see no enemy in you
        if e.kind in ("beast", "spider"):
            from .perks import perk_rank
            if perk_rank(p, "beastfriend") and state.turns - p.last_strike > 10:
                radius = 0  # old scent sleeps till provoked
        if e.faction and e.faction == p.oath:
            radius = 0  # sworn blades know your colors
        elif e.faction and e.faction in oath_foes(state):
            radius += 2  # rivals watch for your colors
        dist = abs(e.x - p.x) + abs(e.y - p.y)
        step = None
        breath = ""
        if e.charmed <= state.turns and 2 <= dist <= 3 \
                and has_los(state, e.x, e.y, p.x, p.y):
            if e.kind == "drake":
                breath = "ember"
            elif e.kind == "wraith" and clock_phase(state.world.clock) == "night":
                breath = "umbral"
        if breath:
            # drakes breathe, wraiths wail: typed volleys the wards remember
            if e.blind > 0:
                state.log(f"{e.name}'s breath gutters out, glitter-eyed.")
            elif rng.random() < 0.8:
                edmg = max(1, e.atk - 1 + rng.randint(-2, 2))
                _hurt_player(state, e, edmg, breath, rng,
                             "breathes ember on you" if breath == "ember"
                             else "wails into you")
            else:
                state.log(f"{e.name}'s breath gutters out.")
            taken.add((e.x, e.y))
            continue
        if e.kind == "mage" and e.charmed <= state.turns \
                and (not e.faction or e.faction != p.oath):
            # chanters hold range, ward themselves, and mend their pack
            hurt = [o for o in state.enemies if o.alive and o is not e
                    and abs(o.x - e.x) + abs(o.y - e.y) <= 2
                    and o.hp < (o.max_hp or o.hp)]
            if hurt and not e.aided and rng.random() < 0.4:
                tgt = min(hurt, key=lambda o: o.hp)
                tgt.hp = min(tgt.max_hp or tgt.hp + 12, tgt.hp + 12)
                e.aided = True
                state.log(f"{e.name} chants, and {tgt.name} knits (+12hp)!")
                taken.add((e.x, e.y))
                continue
            if e.shield <= 0 and e.hp < (e.max_hp or e.hp) and rng.random() < 0.3:
                e.shield = 10
                state.log(f"{e.name} raises a shimmering ward!")
                taken.add((e.x, e.y))
                continue
            if 2 <= dist <= 4 and has_los(state, e.x, e.y, p.x, p.y):
                if e.blind > 0:
                    state.log(f"{e.name}'s hex gutters out, glitter-eyed.")
                elif rng.random() < 0.7:
                    edmg = max(1, e.atk - 1 + rng.randint(-2, 2))
                    _hurt_player(state, e, edmg, "storm", rng, "hurls lightning at you")
                else:
                    state.log(f"{e.name}'s hex hisses wide.")
                taken.add((e.x, e.y))
                continue
        if (e.ranged and e.charmed <= state.turns and dist <= 4
                and (not e.faction or e.faction != p.oath)
                and has_los(state, e.x, e.y, p.x, p.y)):
            from .items import BOW_MIN as _BMIN
            if dist < _BMIN:
                # too close to draw: back off to string range
                dx = (e.x > p.x) - (e.x < p.x)
                dy = (e.y > p.y) - (e.y < p.y)
                fled = False
                for sx, sy in ((dx, 0), (0, dy)):
                    if not sx and not sy:
                        continue
                    nx, ny = e.x + sx, e.y + sy
                    if (0 <= nx < WW and 0 <= ny < HH
                            and grid[ny][nx] in walk and (nx, ny) not in taken):
                        e.x, e.y = nx, ny
                        fled = True
                        break
                taken.add((e.x, e.y))
                if fled:
                    if e.x == p.x and e.y == p.y:
                        state.in_combat_with = e
                        state.log(f"! {e.name} runs you down! (A)ttack, (R) shoot, or (F)lee.")
                    continue
            # loose: 80% to land, guard and wards answer as ever
            if e.blind > 0:
                state.log(f"{e.name}'s arrow hisses wide, glitter-eyed.")
            elif rng.random() < 0.8:
                edmg = max(1, e.atk - 1 + rng.randint(-2, 2))
                _hurt_player(state, e, edmg, "physical", rng, "shoots you")
            else:
                state.log(f"{e.name}'s arrow hisses wide.")
            taken.add((e.x, e.y))
            continue
        if 0 < dist <= radius:
            dx = (p.x > e.x) - (p.x < e.x)
            dy = (p.y > e.y) - (p.y < e.y)
            prefs = [(dx, 0), (0, dy)] if abs(e.x - p.x) >= abs(e.y - p.y) else [(0, dy), (dx, 0)]
            for sx, sy in prefs:
                if not sx and not sy:
                    continue
                nx, ny = e.x + sx, e.y + sy
                if (0 <= nx < WW and 0 <= ny < HH
                        and grid[ny][nx] in walk and (nx, ny) not in taken):
                    step = (sx, sy)
                    break
        elif rng.random() < 0.3:
            opts = [(sx, sy) for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (0 <= e.x + sx < WW and 0 <= e.y + sy < HH
                        and grid[e.y + sy][e.x + sx] in walk
                        and (e.x + sx, e.y + sy) not in taken)]
            if opts:
                step = rng.choice(opts)
        if step:
            e.x += step[0]
            e.y += step[1]
            if e.kind == "spider" and dist <= radius and rng.random() < 0.35:
                # skittering second lunge
                dx = (p.x > e.x) - (p.x < e.x)
                dy = (p.y > e.y) - (p.y < e.y)
                nx, ny = e.x + dx, e.y + dy
                if (dx or dy) and 0 <= nx < WW and 0 <= ny < HH \
                        and grid[ny][nx] in walk and (nx, ny) not in taken \
                        and not (nx == p.x and ny == p.y):
                    e.x, e.y = nx, ny
        taken.add((e.x, e.y))
        if _hostile(e):
            _spring_trap_foe(state, e, rng)
            if not e.alive:
                continue
        if e.x == p.x and e.y == p.y:
            if e.faction and e.faction == p.oath:
                continue  # sworn ground shared peacefully
            if (p.buffs or {}).get("ghost", 0) > 0:
                continue  # unseen, unbothered
            state.in_combat_with = e
            state.log(f"! {e.name} runs you down! (A)ttack, (R) shoot, or (F)lee.")
            _companion_turn(state, rng)
            return
    _companion_turn(state, rng)


EXPAND_MARGIN = 8


def foe_cap(state: GameState) -> int:
    """How many wilds the wilds hold: founding density plus one per hero level."""
    w = state.world
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
    scale = max(0.5, (w.width * w.height) / (150 * 85))
    return min(60, max(7, round((len(bandits) + 4) * scale) + state.player.level))


def _ecology_tick(state: GameState, rng: random.Random) -> None:
    """Living wilds, every stride: strays beyond 40 leagues move on (quest
    blades, bosses, and the charmed are never touched), and while the count
    sits under the cap, the dark thickens — newcomers prowl in at 10-16
    leagues, clear of hearths, scaled to the hero."""
    if state.interior is not None or state.in_combat_with:
        return
    w, p = state.world, state.player
    grid = w.grid
    named = {q.target_enemy for q in list(w.quests) + list(w.dormant_quests)
             if q.target_enemy}
    kept = []
    for e in state.enemies:
        if (e.alive and abs(e.x - p.x) + abs(e.y - p.y) > 40 and not e.boss
                and e.charmed <= state.turns and e.name not in named):
            continue  # moved on
        kept.append(e)
    state.enemies = kept
    if state.in_combat_with is not None:
        return
    alive = [e for e in state.enemies if e.alive]
    if len(alive) >= foe_cap(state) or rng.random() > 0.12:
        return
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
    laired = {q.target_enemy for q in list(w.quests) + list(w.dormant_quests)
              if q.kind == "bounty" and q.target_site}
    roamers = [b for b in bandits if b.name not in laired] or bandits
    from .worldgen import WALKABLE
    for _ in range(40):
        x = max(0, min(w.width - 1, p.x + rng.randint(-16, 16)))
        y = max(0, min(w.height - 1, p.y + rng.randint(-16, 16)))
        d = abs(x - p.x) + abs(y - p.y)
        if not (10 <= d <= 16) or grid[y][x] not in WALKABLE:
            continue
        if any(abs(c.x - x) + abs(c.y - y) <= 3 for c in w.cities):
            continue  # hearths stay safe
        if any(e.alive and e.x == x and e.y == y for e in state.enemies):
            continue
        foe = spawn_foe(w, x, y, rng, roamers, level_scale=trail_scale(p.level))
        if foe is not None:
            state.enemies.append(foe)
        break


def _maybe_expand(state: GameState, rng: random.Random) -> None:
    """Infinite frontier: growing the world when the player nears an edge."""
    from .worldgen import grow, settle_frontier, BUILDABLE
    w, p = state.world, state.player
    if p.x < EXPAND_MARGIN:
        _expand_side(state, "left", rng)
    elif p.x >= w.width - EXPAND_MARGIN:
        _expand_side(state, "right", rng)
    if p.y < EXPAND_MARGIN:
        _expand_side(state, "top", rng)
    elif p.y >= w.height - EXPAND_MARGIN:
        _expand_side(state, "bottom", rng)


def _expand_side(state: GameState, side: str, rng: random.Random) -> None:
    from .worldgen import grow, settle_frontier, BUILDABLE
    w = state.world
    dx, dy = grow(w, side)
    # shift every tracked position if land was prepended
    if dx or dy:
        state.player.x += dx
        state.player.y += dy
        for member in [state.player] + [m for m in state.roster if m is not state.player]:
            mk = getattr(member, "mark", None)
            if isinstance(mk, list) and len(mk) == 2:
                try:
                    mk[0] += dx
                    mk[1] += dy
                except Exception:
                    pass
        for e in state.enemies:
            e.x += dx
            e.y += dy
        for c in state.companions.values():
            c["x"] += dx
            c["y"] += dy
        for member in state.roster:
            if member is not state.player:
                member.x += dx
                member.y += dy
    summary = settle_frontier(w, rng, anchor=(state.player.x, state.player.y))
    # frontier bands need teeth: seed a few foes out there (laired bosses stay home)
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
    laired = {q.target_enemy for q in list(w.quests) + list(w.dormant_quests)
              if q.kind == "bounty" and q.target_site}
    roamers = [b for b in bandits if b.name not in laired] or bandits
    grid = w.grid
    placed = 0
    lvl = state.player.level
    for _ in range(120):
        if placed >= 3:
            break
        x, y = rng.randrange(w.width), rng.randrange(w.height)
        if grid[y][x] in BUILDABLE and abs(x - state.player.x) + abs(y - state.player.y) > 10:
            foe = spawn_foe(w, x, y, rng, roamers, level_scale=lvl)
            if foe is None:
                break
            state.enemies.append(foe)
            placed += 1
    region = summary["region"]
    bits = []
    if summary["cities"]:
        bits.append(f"{len(summary['cities'])} town(s)")
    if summary["sites"]:
        wild = [s for s in summary["sites"] if s.kind in ("dungeon", "ruin", "shrine")]
        stead = [s for s in summary["sites"] if s.kind in ("tower", "camp", "farm")]
        if wild:
            bits.append(f"{len(wild)} wild site(s)")
        if stead:
            bits.append(f"{len(stead)} steading(s)")
    if summary["quests"]:
        bits.append(f"{len(summary['quests'])} rumors")
    state.log(f"+ The frontier opens: {region.name} ({', '.join(bits) or 'open wilds'}).")
    # frontier camps post their own guards
    for camp in [s for s in summary["sites"] if s.kind == "camp"]:
        for _ in range(60):
            x = max(0, min(w.width - 1, camp.x + rng.randint(-2, 2)))
            y = max(0, min(w.height - 1, camp.y + rng.randint(-2, 2)))
            if (w.grid[y][x] in BUILDABLE
                    and abs(x - state.player.x) + abs(y - state.player.y) > 10
                    and not any(e.x == x and e.y == y for e in state.enemies)):
                b = rng.choice(roamers)
                state.enemies.append(Enemy(name=b.name, x=x, y=y, hp=b.hp, atk=b.atk))
                break


def interact(state: GameState, rng: random.Random | None = None) -> None:
    """Talk / enter / learn: context action underfoot."""
    from .dungeon import STAIRS, DOWN
    rng = rng or random.Random()
    if state.in_combat_with:
        state.log("No talking mid-fight!")
        return
    px, py = state.player.x, state.player.y
    if state.interior is not None:
        if state.interior.get("kind") == "city":
            from .dungeon import GATE
            grid, _, _ = _play_grid(state)
            if grid[py][px] == GATE:
                ascend(state)
                return
            if _talk(state):
                return
            state.log("Cobbles and smoke. Gates (G) lead out; folk love gossip (E).")
            return
        grid, _, _ = _play_grid(state)
        if grid[py][px] == STAIRS:
            depth = int(state.interior.get("depth", 1))
            level = int(state.interior.get("level", 0))
            if depth > 1 and level > 0:
                descend_level(state, -1, rng)
            else:
                ascend(state)
            return
        if grid[py][px] == DOWN:
            depth = int(state.interior.get("depth", 1))
            level = int(state.interior.get("level", 0))
            if level < depth - 1:
                descend_level(state, 1, rng)
            else:
                state.log("The dark goes no deeper.")
            return
        if _read_tablet(state, rng):
            return
        state.log("Dust and echoes. Stairs (<) lead out, (>) lead down.")
        return
    # standing on a city tile: walk the gates
    for city in state.world.cities:
        if city.x == px and city.y == py:
            descend(state, city, rng)
            return
    # standing on a wild site: delve, learn, survey, loot, or sup
    for s in state.world.sites:
        if s.x == px and s.y == py:
            if s.kind == "shrine":
                learn_at_shrine(state)
                return
            if s.kind == "tower":
                _survey(state, s)
                return
            if s.kind == "camp":
                _loot_camp(state, s, rng)
                return
            if s.kind == "farm":
                _share_meal(state, s)
                return
            descend(state, s, rng)
            return
    for city in state.world.cities:
        if abs(city.x - px) + abs(city.y - py) <= 1:
            locals_ = [c for c in state.world.characters if c.city == city.name][:3]
            names = ", ".join(f"{c.name} ({c.role})" for c in locals_) or "quiet streets"
            state.log(f"{city.name}: {names}.")
            advance(state, 15)
            add_skill(state, "speech", 1)
            if city.faction:
                line = f" territory of {faction_name(state.world, city.faction)}."
                foes = next((f.at_war for f in state.world.factions if f.id == city.faction), [])
                if foes:
                    line += f" At war with {', '.join(faction_name(state.world, x) for x in foes)}."
                state.log(line)
            if city.founded:
                state.log(f"Founded {city.founded} by {city.founder}.")
            if city.flavor:
                state.log(f"Lore: {city.flavor[:120]}")
            # the town remembers: a historical tidbit about this place
            from .history import events_at
            past = events_at(state.world, city.name)
            if past and rng.random() < 0.5:
                e = rng.choice(past)
                state.log(f"In {e['year']}: {e['text'][:120]}")
            # memory ledger: folk quote back your road deeds
            try:
                from .director import memory_line as _mem2, foreshadow_line as _fore2
                mem2 = _mem2(state.world, rng)
                if mem2 and rng.random() < 0.35:
                    state.log(f"A local nods: \"{mem2[:140]}\"")
                else:
                    fore2 = _fore2(state.world, rng)
                    if fore2 and rng.random() < 0.3:
                        state.log(f"A local warns: \"{fore2[:140]}\"")
            except Exception:
                pass
            # hear local rumors first, then turn in work for this city
            _discover(state, city.name)
            _turn_in(state, city.name)
            return
    # adjacent enemy talk = taunt
    for e in state.enemies:
        if e.alive and abs(e.x - px) + abs(e.y - py) == 1:
            state.log(f"{e.name} snarls: 'Your {state.world.lore_terms[0] if state.world.lore_terms else 'gold'} is mine!'")
            return
    state.log("No one nearby.")


def heal(state: GameState) -> None:
    px, py = state.player.x, state.player.y
    in_town = state.interior is not None and state.interior.get("kind") == "city"
    on_city = in_town or any(c.x == px and c.y == py for c in state.world.cities)
    if not on_city:
        state.log("Heal only inside a city (O). Camp (Z) in the wilds.")
        return
    cost = heal_cost(state.player)
    if state.player.oath:
        home = None
        if in_town:
            home = next((c for c in state.world.cities
                         if c.name == state.interior["site"]), None)
        else:
            home = next((c for c in state.world.cities if c.x == px and c.y == py), None)
        if home is not None and home.faction == state.player.oath:
            cost = max(1, cost // 2)
            state.log(f"Sworn rates in {home.name}: healing costs {cost}g.")
    if state.player.gold < cost:
        state.log(f"Not enough gold (need {cost}).")
        return
    from .items import eff_max_hp
    if state.player.hp >= eff_max_hp(state.player):
        state.log("Already at full health.")
        return
    state.player.gold -= cost
    mend = 10 + 3 * eff_skill(state.player, "medicine")
    state.player.hp = min(eff_max_hp(state.player), state.player.hp + mend)
    state.player.poison = 0
    state.player.bleed = 0
    advance(state, 30)
    play("heal")
    state.log(f"Healed to {state.player.hp}/{eff_max_hp(state.player)}. Gold: {state.player.gold}")


def rest(state: GameState, rng: random.Random | None = None) -> None:
    """Z: inn rest in a city (3g, sleep till dawn) or wild camp (free, +8h,
    ambush risk lowered by Survival)."""
    rng = rng or random.Random()
    from .items import eff_max_hp
    p = state.player
    in_town = state.interior is not None and state.interior.get("kind") == "city"
    in_city = in_town or any(c.x == p.x and c.y == p.y for c in state.world.cities)
    try:
        _hc = home_of(state.world).get("city", "")
        _athome = bool(_hc) and (
            (state.interior.get("site") == _hc if in_town else
             any(c.name == _hc and c.x == p.x and c.y == p.y for c in state.world.cities)))
    except Exception:
        _athome = False
    if p.hp >= eff_max_hp(p) and in_city:
        if _athome and p.buffs.get("rested", 0) <= 0:
            if p.gold < 3:
                state.log("The innkeep wants 3g for a bed.")
                return
            p.gold -= 3
            advance(state, 120)
            p.buffs["rested"] = 120
            state.log("+ Slept in your own bed: rested (+15% learning, 120 steps).")
        else:
            state.log("Already rested and hale.")
        return
    if in_city:
        if p.gold < 3:
            state.log("The innkeep wants 3g for a bed.")
            return
        p.gold -= 3
        m = state.world.clock % 1440
        adv = (360 - m) if m < 360 else (1440 - m + 360)
        advance(state, adv)
        p.hp = eff_max_hp(p)
        p.mana = p.max_mana
        p.poison = 0
        p.bleed = 0
        try:
            state.world.tension = 0.0
        except Exception:
            pass
        if _athome:
            p.buffs["rested"] = 120
            state.log("+ Slept in your own bed: rested (+15% learning, 120 steps).")
        add_skill(state, "survival", 1)
        play("heal")
        state.log(f"+ Rested at the inn till dawn. HP full. Gold: {p.gold}.")
        return
    # wild camp
    advance(state, 480)
    p.hp = eff_max_hp(p)
    p.mana = p.max_mana
    p.poison = 0
    p.bleed = 0
    add_skill(state, "survival", 2)
    risk = max(0.05, 0.25 - eff_skill(p, "survival") * 0.02)
    if rng.random() < risk:
        grid, WW, HH = _play_grid(state)
        walk = _play_walk(state)
        lvl = max(0, (p.level - 1) // 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)):
            nx, ny = p.x + dx, p.y + dy
            if (0 <= nx < WW and 0 <= ny < HH
                    and grid[ny][nx] in walk
                    and not any(e.alive and e.x == nx and e.y == ny for e in state.enemies)):
                bandits = [c for c in state.world.characters if c.role == "bandit"]
                b = rng.choice(bandits) if bandits else None
                if b is None:
                    break
                foe = Enemy(name=b.name, x=nx, y=ny,
                            hp=max(1, b.hp + lvl * 3), atk=max(1, b.atk + lvl // 2))
                state.enemies.append(foe)
                if dx == 0 and dy == 0:
                    state.in_combat_with = foe
                    state.log(f"! {b.name} was already waiting at your camp! Fight!")
                else:
                    state.log(f"! Your campfire drew {b.name}! (E) nearby.")
                break
        else:
            state.log("+ Camped the night undisturbed. HP full.")
    else:
        state.log("+ Camped the night undisturbed. HP full.")


def _hit_foe(state: GameState, e: Enemy, raw: int, dtype: str,
             rng: random.Random, crit: bool = False, verb: str = "You hit") -> bool:
    """Shared strike resolution. Returns True if the foe died."""
    from .perks import perk_rank, perk_mag
    r = perk_rank(state.player, "executioner")
    if r and e.max_hp > 0 and e.hp <= e.max_hp * 0.35:
        raw = raw + perk_mag(state, "executioner") * r
    # flanking: a foe holding off your companion leaves its back open
    try:
        comp_tiles = {(c["x"], c["y"]) for c in (state.companions or {}).values()}
        if any(abs(cx - e.x) + abs(cy - e.y) <= 1 for cx, cy in comp_tiles):
            raw = round(raw * 1.5)
            verb = f"{verb} (flanking)"
    except Exception:
        pass
    dealt, note = apply_affinity(raw, dtype, e)
    if getattr(e, "shield", 0) > 0 and dealt > 0:
        absorbed = min(e.shield, dealt)
        e.shield -= absorbed
        dealt -= absorbed
        state.log(f"The ward around {e.name} drinks {absorbed}.")
        if dealt <= 0:
            state.ping(e.x, e.y, "warded", (140, 190, 220))
            return False
    e.hp -= dealt
    tag = " WEAK!" if note == "weak" else (" resisted." if note == "resisted" else "")
    state.log(f"{verb} {e.name} for {dealt}{' CRIT' if crit else ''}{tag} ({max(0, e.hp)} left).")
    state.ping(e.x, e.y, str(dealt), (255, 215, 0) if crit else (255, 255, 255))
    state.flash(e.x, e.y)
    play("hit")
    if dtype == "ember" and rng.random() < 0.35:
        e.burn = 3 + perk_rank(state.player, "emberwake") * perk_mag(state, "emberwake")
    buffs = state.player.buffs if hasattr(state.player, "buffs") else {}
    if dtype == "physical" and verb.split(" ")[0] in ("You", "Your") \
            and verb != "Your thorns catch" and (buffs or {}).get("firebelch", 0) > 0 \
            and rng.random() < 0.5:
        e.burn = 3
        state.log(f"Your breath sets {e.name} burning!")
    if not e.alive:
        _slay(state, e, rng)
        if state.in_combat_with is e:
            state.in_combat_with = None
        return True
    if e.max_hp < e.hp + dealt:
        e.max_hp = e.hp + dealt  # first blood establishes the measure (legacy-safe)
    if e.kind == "beast" and rng.random() < 0.35:
        _beast_howl(state, e, rng)
    _morale_check(state, e, rng)
    if e.boss and not e.enraged and e.hp <= e.max_hp * 0.35:
        _boss_enrage(state, e)
    if e.boss and not e.cried and e.hp <= e.max_hp * 0.66:
        _boss_warcry(state, e, rng)
    return False


def _morale_check(state: GameState, e: Enemy, rng: random.Random) -> None:
    """Bloodied thinking foes break: blades/soldiers/chanters surrender
    (tribute + stand down), beasts/spiders rout. Bosses and the mindless
    (dead, wraiths, golems, drakes) never do."""
    if e.boss or not e.alive or e.cowed or e.routed > 0:
        return
    if e.kind in ("undead", "wraith", "golem", "drake", "specter"):
        return
    try:
        frac = e.hp / max(1, e.max_hp or e.hp)
    except Exception:
        return
    if frac > 0.3:
        return
    if e.kind in ("bandit", "soldier", "mage"):
        chance = 0.2 if e.kind == "soldier" else 0.35
        if rng.random() < chance:
            e.cowed = True
            e.windup = 0
            tribute = rng.randint(5, 12)
            state.player.gold += tribute
            state.log(f"! {e.name} throws down its steel and begs mercy (+{tribute}g tribute). It will not fight.")
    else:  # beast, spider
        if rng.random() < 0.4:
            e.routed = 4
            e.windup = 0
            state.log(f"! {e.name} breaks and runs!")


def _wielded_style(p) -> str:
    try:
        return str(((p.equipment or {}).get("weapon") or {}).get("style", "sword"))
    except Exception:
        return "sword"


def _adjacent_foe(state: GameState, rng: random.Random | None = None) -> Enemy | None:
    """Nearest living foe sharing the hero's tile or one step away (two with
    a spear). Tile-sharers re-grapple; neighbours can be struck without
    stepping in. Berserk heroes swing wild: a random neighbour instead."""
    p = state.player
    reach = 2 if _wielded_style(p) == "spear" else 1
    near = [e for e in state.enemies if _hostile(e)
            and abs(e.x - p.x) + abs(e.y - p.y) <= reach]
    if not near:
        return None
    sharers = [e for e in near if e.x == p.x and e.y == p.y]
    if sharers:
        state.in_combat_with = sharers[0]
        return sharers[0]
    buffs = p.buffs if hasattr(p, "buffs") else {}
    if (buffs or {}).get("berserk", 0) > 0 and len(near) > 1 and rng is not None:
        return rng.choice(near)
    return min(near, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))


def combat_attack(state: GameState, rng: random.Random | None = None) -> None:
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if not e:
        return
    rng = rng or random.Random()
    _assassin_shadow(state, e)
    dmg, crit, dtype = melee_damage(state.player, rng, state)
    add_skill(state, "blades", 2)
    state.player.last_strike = state.turns
    if _hit_foe(state, e, dmg, dtype, rng, crit):
        _status_tick(state, rng)
        return
    _foe_counter(state, e, rng)
    _status_tick(state, rng)


def _assassin_shadow(state: GameState, e: Enemy) -> None:
    """Assassins murder the slowed: a snared foe never sees it coming."""
    try:
        if state.player.class_name == "Assassin" and getattr(e, "slowed", 0) > 0 \
                and not (state.player.buffs or {}).get("focus"):
            state.player.buffs["focus"] = 30
            state.log("From the shadows — it never saw you.")
    except Exception:
        pass


def combat_heavy(state: GameState, rng: random.Random | None = None) -> None:
    """Heavy: ~1.7x damage at 75% accuracy, but the swing leaves you winded
    (+50% on the next reply). Great weapons cleave every adjacent foe. Miss
    = free counter."""
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if not e:
        return
    rng = rng or random.Random()
    from .perks import perk_rank, perk_mag
    style = _wielded_style(state.player)
    if not perk_rank(state.player, "windrunner"):
        state.player.winded = True
    acc = 0.75 + perk_rank(state.player, "steady") * perk_mag(state, "steady") / 100
    if style == "swift":
        acc -= 0.1
    if rng.random() > acc:
        state.log(f"Your heavy swing misses {e.name}!")
        state.player.last_strike = state.turns
        add_skill(state, "blades", 1)
        _foe_counter(state, e, rng)
        _status_tick(state, rng)
        return
    _assassin_shadow(state, e)
    dmg, crit, dtype = melee_damage(state.player, rng, state)
    mult = 2.0 if style == "heavy" else 1.7
    raw = max(1, round(dmg * mult))
    add_skill(state, "blades", 3)
    state.player.last_strike = state.turns
    if _hit_foe(state, e, raw, dtype, rng, crit, verb="You CRUSH"):
        state.player.winded = False  # none left standing to exploit it
        _status_tick(state, rng)
        return
    if style == "heavy":
        for o in [x for x in state.enemies if x.alive and x is not e
                  and abs(x.x - state.player.x) + abs(x.y - state.player.y) <= 1]:
            _hit_foe(state, o, max(1, raw // 2), dtype, rng, crit, verb="The arc catches")
        state.log("Your great weapon arcs through them all!")
    _foe_counter(state, e, rng)
    _status_tick(state, rng)


def combat_quick(state: GameState, rng: random.Random | None = None) -> None:
    """Quick: ~0.6x damage (0.8x with a swift blade, 0.5x with a great one),
    foe counter hits softer; 60% to spoil a windup."""
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if not e:
        return
    rng = rng or random.Random()
    _assassin_shadow(state, e)
    dmg, crit, dtype = melee_damage(state.player, rng, state)
    style = _wielded_style(state.player)
    mult = 0.8 if style == "swift" else (0.5 if style == "heavy" else 0.6)
    raw = max(1, round(dmg * mult))
    add_skill(state, "blades", 1)
    state.player.last_strike = state.turns
    if e.windup and rng.random() < 0.6:
        e.windup = 0
        state.log(f"Quick cut spoils {e.name}'s heavy!")
    if _hit_foe(state, e, raw, dtype, rng, crit, verb="You nick"):
        _status_tick(state, rng)
        return
    _foe_counter(state, e, rng, soft=True)
    _status_tick(state, rng)


def combat_defend(state: GameState, rng: random.Random | None = None) -> None:
    """Defend: no strike, but the next counter is quartered (heavies too)."""
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if not e:
        return
    rng = rng or random.Random()
    state.player.guarding = True
    state.log(f"You raise your guard against {e.name}.")
    add_skill(state, "survival", 1)
    _foe_counter(state, e, rng)
    _status_tick(state, rng)


def use_consumable(state: GameState, index: int,
                   rng: random.Random | None = None) -> bool:
    """Drink/throw/burn a pack consumable by inventory index. In combat the
    foe usually answers (smoke escapes instead). Returns True if used."""
    rng = rng or random.Random()
    p = state.player
    if not (0 <= index < len(p.inventory)):
        return False
    item = p.inventory[index]
    if (item.get("kind") or "") != "consumable":
        return False
    sub = item.get("sub", "")
    e = state.in_combat_with
    if sub == "potion":
        from .items import eff_max_hp
        if p.hp >= eff_max_hp(p) and p.poison <= 0:
            state.log("Already hale — save the draught.")
            return False
        del p.inventory[index]
        healed = 25 + eff_skill(p, "medicine")
        p.hp = min(eff_max_hp(p), p.hp + healed)
        p.bleed = 0
        play("heal")
        state.log(f"You drink {item['name']} (+{healed}hp, bleeding staunched).")
        if e and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    if sub == "bomb":
        del p.inventory[index]
        p.last_strike = state.turns
        if e is None or not e.alive:
            # field test: scorch adjacent vermin
            foes = [f for f in state.enemies if f.alive
                    and abs(f.x - p.x) + abs(f.y - p.y) <= 2]
            if not foes:
                state.log(f"You hurl {item['name']} into the empty wilds. Wasteful.")
                return True
            for f in foes:
                f.hp -= 12
                if rng.random() < 0.5:
                    f.burn = 3
                if not f.alive:
                    _slay(state, f, rng)
            state.log(f"{item['name']} bursts among {len(foes)} foe(s)!")
            return True
        _hit_foe(state, e, 25, "ember", rng, verb="The bomb catches")
        splash = [f for f in state.enemies if f.alive and f is not e
                  and abs(f.x - e.x) + abs(f.y - e.y) <= 2]
        for f in splash:
            f.hp -= 12
            if rng.random() < 0.5:
                f.burn = 3
            if not f.alive:
                _slay(state, f, rng)
        if splash:
            state.log(f"The blast scorches {len(splash)} nearby foe(s).")
        if e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        else:
            _status_tick(state, rng)
        return True
    if sub == "smoke":
        del p.inventory[index]
        if e is None:
            state.log(f"{item['name']} blooms grey. No one to flee.")
            return True
        state.log(f"{item['name']} blooms grey — you vanish!")
        add_skill(state, "sneak", 2)
        state.in_combat_with = None
        state.player.winded = False
        e.windup = 0
        return True
    if sub == "quiver":
        del p.inventory[index]
        from .perks import perk_rank, perk_mag
        extra = perk_rank(p, "fletcher") * perk_mag(state, "fletcher")
        p.ammo += 8 + extra
        state.log(f"You fletch {item['name']} (+{8 + extra} arrows, {p.ammo} total).")
        if e and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    if sub == "tonic":
        del p.inventory[index]
        p.shield += 15
        play("heal")
        state.log(f"You drink {item['name']} (+15 ward, {p.shield} total).")
        if e and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    if sub in ("swift", "iron", "focus", "secondwind", "berserk", "ghost",
               "greed", "firebelch"):
        turns = {"swift": 30, "iron": 20, "focus": 30, "secondwind": 60,
                 "berserk": 15, "ghost": 10, "greed": 60, "firebelch": 15}[sub]
        del p.inventory[index]
        p.buffs[sub] = turns
        play("heal")
        state.log(f"You take {item['name']} ({sub} {turns} steps).")
        if e and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    if sub == "love":
        del p.inventory[index]
        if e is not None and e.alive and not e.boss:
            tgt = e
        else:
            near = [f for f in state.enemies if f.alive and not f.boss
                    and abs(f.x - p.x) + abs(f.y - p.y) <= 4]
            tgt = min(near, key=lambda f: abs(f.x - p.x) + abs(f.y - p.y)) if near else None
        if tgt is None:
            state.log(f"You dash {item['name']} into the empty wilds. Wasteful.")
            return True
        tgt.charmed = state.turns + 30
        tgt.windup = 0
        state.log(f"{tgt.name} falls hopelessly in love with you (30 steps).")
        if state.in_combat_with is tgt:
            state.in_combat_with = None
        elif e is not None and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    if sub == "glitter":
        del p.inventory[index]
        targets = [f for f in state.enemies if f.alive
                   and abs(f.x - p.x) + abs(f.y - p.y) <= 4]
        if not targets:
            state.log(f"You burst {item['name']} into the empty wilds. Wasteful.")
            return True
        for f in targets:
            f.blind = 20
        state.log(f"{item['name']} blinds {len(targets)} foe(s) — no volleys 20 steps!")
        if e is not None and e.alive:
            _foe_counter(state, e, rng)
            _status_tick(state, rng)
        return True
    return False


# ---------------- alchemy: gather, salvage, brew ----------------
# Forests give herbs (G), the slain give stranger stock, and the brew kettle
# (K) turns stock into field goods. No new currencies: mats ride the pack.

RECIPES = [
    {"id": "draught", "name": "Field Draught", "need": {"herb": 3}, "makes": "potion"},
    {"id": "firebomb", "name": "Blackpowder Bomb", "need": {"herb": 2, "venom": 1},
     "makes": "bomb"},
    {"id": "smoke", "name": "Grave Smoke", "need": {"herb": 2, "dust": 1}, "makes": "smoke"},
    {"id": "quiver", "name": "Bone Quiver", "need": {"fang": 2}, "makes": "quiver"},
    {"id": "tonic", "name": "Stoneward Tonic", "need": {"dust": 2, "scale": 1},
     "makes": "tonic"},
    {"id": "swift", "name": "Swiftfoot Tonic", "need": {"herb": 2, "fang": 2},
     "makes": "swift"},
    {"id": "iron", "name": "Ironhide Brew", "need": {"herb": 2, "scale": 1},
     "makes": "iron"},
    {"id": "focus", "name": "Focusing Tea", "need": {"herb": 1, "fang": 1, "venom": 1},
     "makes": "focus"},
    {"id": "secondwind", "name": "Second Wind", "need": {"dust": 3, "scale": 1},
     "makes": "secondwind"},
    {"id": "love", "name": "Love Philtre", "need": {"herb": 1, "venom": 2},
     "makes": "love"},
    {"id": "glitter", "name": "Glitterbomb", "need": {"fang": 2, "dust": 1},
     "makes": "glitter"},
    {"id": "berserk", "name": "Berserk Mushroom", "need": {"fang": 1, "venom": 2},
     "makes": "berserk"},
    {"id": "ghost", "name": "Ghost Draught", "need": {"dust": 3}, "makes": "ghost"},
    {"id": "greed", "name": "Greed Philter", "need": {"herb": 1, "fang": 1, "scale": 1},
     "makes": "greed"},
    {"id": "firebelch", "name": "Dragonbreath", "need": {"venom": 1, "dust": 2},
     "makes": "firebelch"},
    {"id": "snare", "name": "Snare Trap", "need": {"fang": 1, "herb": 2},
     "makes": "snare"},
    {"id": "dart", "name": "Dart Trap", "need": {"fang": 1, "venom": 1},
     "makes": "dart"},
    {"id": "embertrap", "name": "Ember Cache", "need": {"dust": 1, "scale": 1},
     "makes": "ember"},
    {"id": "oil", "name": "Oil Slick", "need": {"herb": 1, "venom": 1},
     "makes": "oil"},
]

SALVAGE = {
    "beast": ("fang", 0.7), "spider": ("venom", 0.6), "undead": ("dust", 0.6),
    "wraith": ("dust", 0.6), "drake": ("scale", 1.0), "golem": ("scale", 0.5),
}


def gather(state: GameState, rng: random.Random | None = None) -> None:
    """G key on a forest tile: strip wildherbs (+1, sometimes +1). Costs time."""
    from .items import gen_material
    rng = rng or random.Random()
    p = state.player
    if state.in_combat_with:
        state.log("No gathering mid-fight!")
        return
    if state.interior is not None:
        state.log("Nothing grows here. Seek forests (T) under open sky.")
        return
    grid, WW, HH = _play_grid(state)
    if not (0 <= p.x < WW and 0 <= p.y < HH) or grid[p.y][p.x] != "T":
        state.log("No herbs here — seek the forests (T).")
        return
    n = 1 + (1 if rng.random() < 0.25 else 0)
    for _ in range(n):
        give_item(state, gen_material("herb", name_pool(state.world), rng), "Gathered")
    advance(state, 30)
    add_skill(state, "survival", 1)
    _enemy_turn(state, rng)


def brew(state: GameState, recipe_id: str, rng: random.Random | None = None) -> bool:
    """Kettle work: trade stock for field goods (and rogue traps)."""
    from .items import gen_consumable, gen_trap, mat_count, take_mats, TRAP_DEFS
    rng = rng or random.Random()
    recipe = next((r for r in RECIPES if r["id"] == recipe_id), None)
    if recipe is None:
        return False
    short = [f"{need} {sub}" for sub, need in recipe["need"].items()
             if mat_count(state.player, sub) < need]
    if short:
        state.log(f"Short for {recipe['name']}: need {', '.join(short)}.")
        return False
    for sub, need in recipe["need"].items():
        take_mats(state.player, sub, need)
    if recipe["makes"] in TRAP_DEFS:
        give_item(state, gen_trap(recipe["makes"], name_pool(state.world), rng),
                  "Trapped")
    else:
        give_item(state, gen_consumable(recipe["makes"], name_pool(state.world), rng),
                  "Brewed")
    advance(state, 15)
    add_skill(state, "survival", 1)
    return True


def _trap_key(state: GameState) -> str:
    """Where a laid trap sleeps: overworld tile, or site+floor+tile below."""
    p = state.player
    if state.interior is not None and state.interior.get("kind") != "city":
        return f"{state.interior.get('site', '?')}:{state.interior.get('level', 0)}:{p.x}:{p.y}"
    return f"ow:{p.x}:{p.y}"


def lay_trap(state: GameState, inv_index: int) -> bool:
    """X on a trap good: sow it underfoot (foes tread, you don't)."""
    inv = state.player.inventory
    if not (0 <= inv_index < len(inv)):
        return False
    item = inv[inv_index]
    if (item.get("kind") or "") != "trap":
        return False
    traps = getattr(state.world, "traps", None)
    if not isinstance(traps, dict):
        state.world.traps = traps = {}
    if len(traps) >= 12:
        state.log("The ground is sown enough (12 traps live). Lift one by treading? No — they keep.")
        return False
    key = _trap_key(state)
    if key in traps:
        state.log("Already sown here. Spread them out.")
        return False
    traps[key] = {"sub": item.get("sub", "snare"), "by": state.player.class_name}
    del inv[inv_index]
    state.log(f"Sown: {item['name']} underfoot. Lure them over it.")
    return True


def _spring_trap_foe(state: GameState, e: Enemy, rng: random.Random) -> None:
    """A foe treads sown ground: snare/dart/ember/oil, then gone."""
    traps = getattr(state.world, "traps", None)
    if not isinstance(traps, dict):
        return
    fx, fy = e.x, e.y
    if state.interior is not None and state.interior.get("kind") != "city":
        key = f"{state.interior.get('site', '?')}:{state.interior.get('level', 0)}:{fx}:{fy}"
    else:
        key = f"ow:{fx}:{fy}"
    trap = traps.pop(key, None)
    if trap is None or trap.get("foe") is True:
        if trap is not None:
            traps[key] = trap  # heroes' steel, not theirs: leave it
        return
    sub = trap.get("sub", "snare")
    thief = str(getattr(state.player, "class_name", "")) == "Thief"
    if sub == "snare":
        e.slowed = max(e.slowed, 6)
        state.log(f"Snare takes {e.name}! Slowed 6 steps.")
    elif sub == "dart":
        dmg = 12 + (1 if thief else 0)
        _hit_foe(state, e, dmg, "physical", rng, verb="Darts take")
    elif sub == "ember":
        dmg = 8 + (1 if thief else 0)
        _hit_foe(state, e, dmg, "ember", rng, verb="The cache erupts on")
        if e.alive:
            e.burn = 3
    else:  # oil
        e.slowed = max(e.slowed, 8)
        if e.burn > 0:
            _hit_foe(state, e, 10, "ember", rng, verb="The oil catches on")
        else:
            state.log(f"{e.name} slips in oil! Steps stolen.")


def _spring_trap_hero(state: GameState, rng: random.Random) -> None:
    """Camp-laid steel bites the hero stepping in (never your own work)."""
    traps = getattr(state.world, "traps", None)
    if not isinstance(traps, dict):
        return
    key = _trap_key(state)
    trap = traps.get(key)
    if trap is None or trap.get("foe") is not True:
        return
    del traps[key]
    p = state.player
    sub = trap.get("sub", "dart")
    if sub == "snare":
        p.buffs["tangle"] = 8
        state.log("A snare takes your ankle! (-flee 8 steps.)")
    elif sub == "ember":
        p.hp = max(1, p.hp - 6)
        state.log("An ember cache pops underfoot! (-6hp.)")
    elif sub == "oil":
        p.buffs["tangle"] = 8
        state.log("Oil! You skate and sprawl. (-flee 8 steps.)")
    else:
        p.hp = max(1, p.hp - 8)
        state.log("Darts hiss from the dark! (-8hp.)")


def _salvage(state: GameState, e: Enemy, rng: random.Random) -> None:
    """The slain keep stranger stock: fangs, venom, dust, scales."""
    from .items import gen_material
    if e.kind not in SALVAGE:
        return
    sub, chance = SALVAGE[e.kind]
    if rng.random() > chance:
        return
    n = 1 + (1 if e.kind == "beast" and rng.random() < 0.3 else 0)
    for _ in range(n):
        give_item(state, gen_material(sub, name_pool(state.world), rng), "Salvaged")


def region_at(world, x: int, y: int) -> str:
    for r in world.regions:
        if r.x0 <= x < r.x1 and r.y0 <= y < r.y1:
            return r.name
    return ""


def _descend_town(state: GameState, city, rng: random.Random, quiet: bool) -> bool:
    """Walk the gates: deterministic streets, the city's own locals plus
    working townsfolk (merchant/healer/scout/elder/guard) so every visit
    has a reason. Safe."""
    from .dungeon import gen_town, interior_seed
    w = state.world
    seed = interior_seed(w.seed, city.x, city.y)
    tier = ["hamlet", "town", "town", "city"][seed % 4]
    gen = gen_town(seed, tier)
    min_npcs = {"hamlet": 6, "town": 10, "city": 14}[tier]
    want = max(min_npcs, gen["max_npcs"])
    locals_ = [c for c in w.characters if c.city == city.name][:want]
    npcs = []
    for i, c in enumerate(locals_):
        if i < len(gen["npc_spots"]):
            x, y = gen["npc_spots"][i]
            npcs.append({"name": c.name, "role": c.role, "x": x, "y": y})
    # fillers: working townsfolk with purpose (no quest gossip of their own)
    roles = ["merchant", "healer", "scout", "elder", "guard"]
    races = [r.name for r in w.races] or ["Human"]
    fi = 0
    while len(npcs) < min(want, len(gen["npc_spots"])) and fi < 40:
        r = random.Random((seed + fi * 131) & 0xFFFFFFFF)
        role = roles[fi % len(roles)]
        race = r.choice(races)
        name = f"{race} {role.capitalize()}{fi // len(roles) + 1}"
        if any(n["name"] == name for n in npcs) or \
                any(c.name == name for c in w.characters):
            fi += 1
            continue
        x, y = gen["npc_spots"][len(npcs)]
        npcs.append({"name": name, "role": role, "x": x, "y": y, "filler": True})
        fi += 1
    state.interior = {"site": city.name, "kind": "city",
                      "grid": gen["grid"], "gates": gen["gates"],
                      "npcs": npcs, "shop_buildings": gen["shops"],
                      "inn": gen["inn"]}
    w.active_interior = {"site": city.name, "kind": "city",
                         "return_x": state.player.x, "return_y": state.player.y,
                         "ow_enemies": [e.__dict__ for e in state.enemies]}
    state.enemies = []
    state.in_combat_with = None
    state.player.x, state.player.y = gen["w"] // 2, gen["h"] - 2
    if not quiet:
        state.log(f"You pass the gates of {city.name}. E greets folk; gates (G) lead out.")
    return True


def _npc_turn(state: GameState, rng: random.Random) -> None:
    """Townsfolk drift; they want nothing from you (until spoken to)."""
    from .dungeon import WALKABLE_TOWN
    if not state.interior or state.interior.get("kind") != "city":
        return
    grid = state.interior["grid"]
    taken = {(n["x"], n["y"]) for n in state.interior["npcs"]}
    taken.add((state.player.x, state.player.y))
    for n in state.interior["npcs"]:
        if rng.random() > 0.3:
            continue
        taken.discard((n["x"], n["y"]))
        opts = [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if grid[n["y"] + dy][n["x"] + dx] in WALKABLE_TOWN
                and (n["x"] + dx, n["y"] + dy) not in taken]
        if opts:
            dx, dy = rng.choice(opts)
            n["x"] += dx
            n["y"] += dy
        taken.add((n["x"], n["y"]))


def _discover_giver(state: GameState, npc_name: str) -> int:
    found = 0
    for q in list(state.world.dormant_quests):
        if q.giver == npc_name:
            state.world.dormant_quests.remove(q)
            state.world.quests.append(q)
            _maybe_urgent(state, q)
            state.log(f"Rumor heard: {q.title} (J for journal).")
            found += 1
    return found


def _turn_in(state: GameState, city_name: str) -> None:
    found = _find_quest(state, "deliver", city_name)
    if found:
        _complete_quest(state, found)
    found = _find_quest(state, "escort", city_name)
    if found:
        _complete_quest(state, found)
    found = _find_quest(state, "tribute", city_name)
    if found:
        if state.player.gold >= found.amount:
            state.player.gold -= found.amount
            _complete_quest(state, found)
        else:
            state.log(f"Tribute unpaid: they demand {found.amount}g (you hold {state.player.gold}g).")


def _talk(state: GameState) -> bool:
    """E next to a townsfolk: gossip, rumors from THEM, and turn-ins."""
    if not state.interior or state.interior.get("kind") != "city":
        return False
    px, py = state.player.x, state.player.y
    for n in state.interior["npcs"]:
        if abs(n["x"] - px) + abs(n["y"] - py) <= 1:
            import random as _r
            from .quests import BARKS
            who = next((c for c in state.world.characters if c.name == n["name"]), None)
            # memory ledger: folk quote back what you did on the road
            try:
                from .director import memory_line as _mem, foreshadow_line as _fore
                mem = _mem(state.world, _r.Random(hash(n["name"]) & 0xFFFFFFFF))
                if mem and (hash(n["name"] + str(state.world.clock // 1440)) % 4 == 0):
                    state.log(f"{n['name']} ({n['role']}): \"{mem[:140]}\"")
                    advance(state, 15)
                    add_skill(state, "speech", 1)
                    _discover_giver(state, n["name"])
                    _turn_in(state, state.interior["site"])
                    return True
                fore = _fore(state.world, _r.Random((hash(n["name"]) >> 1) & 0xFFFFFFFF))
                if fore and (hash(n["name"]) % 3 == 0):
                    state.log(f"{n['name']} ({n['role']}): \"{fore[:140]}\"")
                    advance(state, 15)
                    add_skill(state, "speech", 1)
                    _discover_giver(state, n["name"])
                    _turn_in(state, state.interior["site"])
                    return True
            except Exception:
                pass
            if _role_service(state, n):
                return True
            if who and who.dialogue:
                says = f'"{who.dialogue[:100]}"'
            else:
                bark = BARKS[sum(map(ord, n["name"])) % len(BARKS)]
                says = f'"{bark.format(place=state.interior["site"])}"'
            state.log(f"{n['name']} ({n['role']}): {says}")
            advance(state, 15)
            add_skill(state, "speech", 1)
            _discover_giver(state, n["name"])
            _turn_in(state, state.interior["site"])
            return True
    return False


def _role_service(state: GameState, n: dict) -> bool:
    """Working townsfolk do work: merchants report stock, healers mend (1/day),
    scouts mark the nearest wild site, elders teach history, guards brief wars."""
    role = str(n.get("role", ""))
    if role not in ("merchant", "healer", "scout", "elder", "guard"):
        return False
    city = state.interior.get("site", "") if state.interior else ""
    if role == "merchant":
        try:
            rows = shop_rows(state, 0)
            ndoors = max(1, len(state.interior.get("shop_buildings", [])))
            from . import trade as _trade
            want, mult = _trade.top_demand(state.world, city)
            crave = f" {city} craves {want} (x{mult})." if want and mult >= 1.4 else ""
            if rows:
                from .items import item_line
                shown = "; ".join(f"{it.get('name', '?')} {it.get('value', 0)}g"
                                  for _, it in rows[:2])
                state.log(f"{n['name']} (merchant): \"{ndoors} doors (S); finest now: {shown[:120]}. B buys beside a door.{crave}\"")
            else:
                state.log(f"{n['name']} (merchant): \"{ndoors} doors (S) — shelves bare, try the next town.{crave}\"")
        except Exception:
            state.log(f"{n['name']} (merchant): \"Doors marked S. B buys beside one.\"")
    elif role == "healer":
        from .items import eff_max_hp
        mem = site_memory(state.world, city)
        today = int(state.world.clock // 1440)
        key = f"heal_{n['name']}"
        if mem.get(key) == today:
            state.log(f"{n['name']} (healer): \"Rest till tomorrow; my herbs need moonlight.\"")
        elif state.player.hp >= eff_max_hp(state.player):
            state.log(f"{n['name']} (healer): \"Hale already. The inn (Z) keeps you so.\"")
        else:
            state.player.hp = min(eff_max_hp(state.player), state.player.hp + 10)
            mem[key] = today
            from .sfx import play as _play
            try:
                _play("heal")
            except Exception:
                pass
            state.log(f"{n['name']} (healer) binds your wounds (+10hp). Once a day, no coin.")
    elif role == "scout":
        best, bd = None, 10 ** 9
        for s in state.world.sites:
            d = abs(s.x - state.player.x) + abs(s.y - state.player.y)
            if d < bd:
                best, bd = s, d
        if best is not None:
            dx, dy = best.x - state.player.x, best.y - state.player.y
            horiz = "east" if dx > 0 else "west" if dx < 0 else ""
            vert = "south" if dy > 0 else "north" if dy < 0 else ""
            state.log(f"{n['name']} (scout): \"{best.name} ({best.kind}) lies {bd} leagues {vert}{horiz}. I marked your eyes.\"")
            add_skill(state, "survival", 1)
        else:
            state.log(f"{n['name']} (scout): \"No wilds worth naming from here.\"")
    elif role == "elder":
        from .history import events_at
        past = events_at(state.world, city)
        if past:
            import random as _r
            e = _r.Random(hash(city) & 0xFFFFFFFF).choice(past)
            state.log(f"{n['name']} (elder): \"In {e['year']}: {e['text'][:130]}\"")
            add_skill(state, "lore", 2)
        else:
            state.log(f"{n['name']} (elder): \"This town is young; its songs are still being written.\"")
    elif role == "guard":
        from .worldgen import faction_name
        city_o = next((c for c in state.world.cities if c.name == city), None)
        if city_o is not None and city_o.faction:
            foes = next((f.at_war for f in state.world.factions if f.id == city_o.faction), [])
            war = f" At war with {', '.join(faction_name(state.world, x) for x in foes)}." if foes else " At peace, for now."
            mine = " Show your colors (O) and walk proud." if not state.player.oath else ""
            state.log(f"{n['name']} (guard): \"{faction_name(state.world, city_o.faction)} holds here.{war}{mine}\"")
        else:
            state.log(f"{n['name']} (guard): \"Free town. Blades pass, trouble follows — shout if steel comes out.\"")
    advance(state, 15)
    add_skill(state, "speech", 1)
    _discover_giver(state, n["name"])
    _turn_in(state, city)
    return True


def descend(state: GameState, place, rng: random.Random | None = None,
            quiet: bool = False) -> bool:
    """Enter a dungeon/ruin (foes, loot, boss) or a town (locals, shops, inn).

    Layouts are seed-derived and cost no save space; only flags persist.
    Overworld bands wait outside (snapshot in world.active_interior).
    """
    from .dungeon import gen_interior, gen_town, interior_seed, depth_for_seed
    rng = rng or random.Random()
    w = state.world
    if state.interior is not None:
        return False
    if hasattr(place, "faction"):
        return _descend_town(state, place, rng, quiet)
    from .dungeon import FLOOR
    site = place
    seed = interior_seed(w.seed, site.x, site.y)
    depth = depth_for_seed(seed)
    gen = gen_interior(seed, site.name, site.kind, level=0, depth=depth,
                       theme=getattr(site, "theme", ""))
    mem = site_memory(w, site.name)
    grid = [list(r) for r in gen["grid"]]
    # re-hide used tablets; opened chests become plain floor (legacy ids too)
    for tb in gen["tablets"]:
        leg = tb["id"].replace(f"#{gen['level']}#", "#")
        if tb["id"] in mem["tablets"] or leg in mem["tablets"]:
            grid[tb["y"]][tb["x"]] = FLOOR
    for ch in gen["chests"]:
        leg = ch["id"].replace(f"#{gen['level']}#", "#")
        if ch["id"] in mem["chests"] or leg in mem["chests"]:
            grid[ch["y"]][ch["x"]] = FLOOR
    state.interior = {"site": site.name, "kind": site.kind,
                      "grid": ["".join(r) for r in grid],
                      "stairs": gen["stairs"], "stairs_down": gen.get("stairs_down"),
                      "rooms": gen["rooms"],
                      "chests": gen["chests"], "tablets": gen["tablets"],
                      "boss_room": gen["boss_room"],
                      "seed": seed, "level": 0, "depth": depth,
                      "theme": getattr(site, "theme", "")}
    w.active_interior = {"site": site.name, "kind": site.kind,
                         "return_x": state.player.x, "return_y": state.player.y,
                         "ow_enemies": [e.__dict__ for e in state.enemies]}
    # fresh blood below (dungeons refill; bosses do not). The deep scales up.
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
    sx, sy = gen["stairs"]
    foes: list[Enemy] = []
    floor = [(x, y) for y in range(gen["h"]) for x in range(gen["w"])
             if grid[y][x] == FLOOR and abs(x - sx) + abs(y - sy) > 4]
    rng.shuffle(floor)
    laired_here = {q.target_enemy for q in list(w.quests) + list(w.dormant_quests)
                   if q.kind == "bounty" and q.target_site == site.name}
    roamers = [b for b in bandits if b.name not in laired_here] or bandits
    for i in range(min(max(3, len(gen["rooms"]) // 2), 8, len(floor))):
        x, y = floor[i]
        foe = spawn_foe_delve(w, x, y, rng, roamers, state.player.level)
        if foe is not None:
            foes.append(foe)
    if depth <= 1:
        boss = _spawn_boss(state, site, rng)
        if boss is not None:
            foes.append(boss)
    state.enemies = foes
    state.in_combat_with = None
    state.player.x, state.player.y = sx, sy
    if not quiet:
        if depth > 1:
            state.log(f"Descending into {site.name} ({site.kind}, {depth} floors). E on (>) climbs down, (<) climbs out.")
        else:
            state.log(f"Descending into {site.name} ({site.kind}). Find the stairs (<) to leave.")
        if site.lore:
            state.log(f"Old tale: {site.lore}")
        boss = next((e for e in foes if e.boss), None)
        if boss is not None:
            from .history import boss_legend
            state.log(f"Below waits {boss.name}, {boss_legend(state.world, rng)}.")
    return True


def descend_level(state: GameState, delta: int, rng: random.Random | None = None) -> bool:
    """Climb between delve floors (seed-derived layouts, zero save space)."""
    from .dungeon import gen_interior, FLOOR
    rng = rng or random.Random()
    if not state.interior or state.interior.get("kind") == "city":
        return False
    w = state.world
    site_name = state.interior.get("site", "")
    site = next((s for s in w.sites if s.name == site_name), None)
    seed = int(state.interior.get("seed", w.seed))
    depth = int(state.interior.get("depth", 1))
    level = int(state.interior.get("level", 0)) + delta
    if level < 0 or level >= depth:
        return False
    gen = gen_interior(seed, site_name, state.interior.get("kind", "dungeon"),
                       level=level, depth=depth,
                       theme=state.interior.get("theme", ""))
    mem = site_memory(w, site_name)
    grid = [list(r) for r in gen["grid"]]
    for tb in gen["tablets"]:
        leg = tb["id"].replace(f"#{level}#", "#")
        if tb["id"] in mem["tablets"] or leg in mem["tablets"]:
            grid[tb["y"]][tb["x"]] = FLOOR
    for ch in gen["chests"]:
        leg = ch["id"].replace(f"#{level}#", "#")
        if ch["id"] in mem["chests"] or leg in mem["chests"]:
            grid[ch["y"]][ch["x"]] = FLOOR
    state.interior.update({
        "grid": ["".join(r) for r in grid],
        "stairs": gen["stairs"], "stairs_down": gen.get("stairs_down"),
        "rooms": gen["rooms"], "chests": gen["chests"],
        "tablets": gen["tablets"], "boss_room": gen["boss_room"],
        "level": level})
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
    if delta > 0:
        sx, sy = gen["stairs"]
    else:
        sx, sy = gen.get("stairs_down") or gen["stairs"]
    floor = [(x, y) for y in range(gen["h"]) for x in range(gen["w"])
             if grid[y][x] == FLOOR and abs(x - sx) + abs(y - sy) > 4]
    rng.shuffle(floor)
    foes: list[Enemy] = []
    for i in range(min(max(3, len(gen["rooms"]) // 2), 8, len(floor))):
        x, y = floor[i]
        foe = spawn_foe_delve(w, x, y, rng, bandits, state.player.level + level * 2)
        if foe is not None:
            if level > 0:
                foe.hp = max(1, foe.hp + level * 6)
                foe.atk = max(1, foe.atk + level)
            foes.append(foe)
    if site is not None and level == depth - 1:
        boss = _spawn_boss(state, site, rng)
        if boss is not None:
            boss.hp = max(1, boss.hp + level * 10)
            boss.atk = max(1, boss.atk + level)
            foes.append(boss)
            from .history import boss_legend
            state.log(f"Below waits {boss.name}, {boss_legend(state.world, rng)}.")
    state.enemies = foes
    state.in_combat_with = None
    state.player.x, state.player.y = sx, sy
    state.log(f"Floor {level + 1} of {depth}: {site_name}.")
    return True


def spawn_foe_delve(world, x: int, y: int, rng: random.Random,
                    pool: list, level: int) -> Enemy | None:
    """Delve fodder: mostly blades, sometimes dead things; scaled by delve depth of hero."""
    r = rng.random()
    if r < 0.15:
        foe = spawn_foe(world, x, y, rng, pool, force="mage")
    elif r < 0.35:
        foe = spawn_foe(world, x, y, rng, pool, force="undead")
    else:
        foe = spawn_foe(world, x, y, rng, pool, force="bandit")
    if foe is None:
        return None
    foe.hp = max(1, foe.hp + level * 4)
    foe.atk = max(1, foe.atk + (level + 1) // 2)
    return foe


def _spawn_boss(state: GameState, site, rng: random.Random) -> Enemy | None:
    """The lair's master waits on the last floor only: the plot Tyrant at
    the finale seat, else a linked bounty target, else a lore-named horror."""
    mem = site_memory(state.world, site.name)
    if mem["boss_dead"]:
        return None
    if state.interior is not None and int(state.interior.get("depth", 1)) > 1 \
            and int(state.interior.get("level", 0)) < int(state.interior.get("depth", 1)) - 1:
        return None
    bx, by = state.interior["boss_room"]
    level = state.player.level
    plot = getattr(state.world, "plot", None) or {}
    if (not plot.get("done") and plot.get("finale_site") == site.name
            and plot.get("villain")):
        return Enemy(name=plot["villain"], x=bx, y=by,
                     hp=150 + level * 14 + rng.randint(0, 20),
                     atk=17 + level + rng.randint(0, 3),
                     boss=True, kind="bandit", trait="Dread")
    linked = next((q for q in list(state.world.quests) + list(state.world.dormant_quests)
                   if q.kind == "bounty" and q.target_site == site.name
                   and q.id not in state.world.completed_quests
                   and q.target_enemy), None)
    if linked is not None:
        name = linked.target_enemy
    else:
        term = (state.world.lore_terms[0].capitalize()
                if state.world.lore_terms else "Grim")
        name = f"{term} {rng.choice(['Horror', 'Warden', 'Tyrant'])}"
    hp = 60 + level * 12 + rng.randint(0, 20)
    atk = 10 + level + rng.randint(0, 3)
    trait = ""
    if rng.random() < 0.4:
        trait = rng.choice(["Savage", "Towering", "Cursed"])
        name = f"{trait} {name}"
        if trait == "Savage":
            atk += 3
        elif trait == "Towering":
            hp += 25
    return Enemy(name=name, x=bx, y=by, hp=hp, atk=atk, boss=True, trait=trait)


def ascend(state: GameState) -> bool:
    """Climb out: overworld bands resume where they left off."""
    snap = state.world.active_interior
    if state.interior is None or not snap:
        return False
    state.player.x, state.player.y = snap["return_x"], snap["return_y"]
    try:
        state.enemies = [Enemy(**e) for e in snap.get("ow_enemies", [])]
    except Exception:
        pass
    state.interior = None
    state.world.active_interior = None
    state.in_combat_with = None
    for q in _escort_quests(state):
        state.companions[q.id] = {"x": state.player.x, "y": state.player.y}
    state.log("You climb back to the overworld.")
    return True


def _check_relic(state: GameState) -> None:
    """Relic beats complete the moment the heirloom is worn or packed."""
    relics = [q for q in state.world.quests if q.kind == "relic"]
    if not relics:
        return
    gear = {i.get("name", "") for i in state.player.inventory}
    gear |= {v.get("name", "") for v in (state.player.equipment or {}).values() if v}
    for q in relics:
        for art in state.world.artifacts:
            if art.get("name") and art["name"] in gear and q.title.endswith(art["name"]):
                _complete_quest(state, q)
                break


def _open_chest(state: GameState, x: int, y: int, rng: random.Random) -> None:
    from .dungeon import FLOOR
    from .items import gen_item
    mem = site_memory(state.world, state.interior["site"])
    chest = next((c for c in state.interior["chests"]
                  if c["x"] == x and c["y"] == y), None)
    if chest is None or chest["id"] in mem["chests"]:
        return
    mem["chests"].append(chest["id"])
    grid = [list(r) for r in state.interior["grid"]]
    grid[y][x] = FLOOR
    state.interior["grid"] = ["".join(r) for r in grid]
    from .perks import perk_rank
    lord = bool(perk_rank(state.player, "ruinlord")) and \
        state.interior.get("kind") in ("dungeon", "ruin")
    # heirlooms sleep in their appointed delves first
    for art in state.world.artifacts:
        if art.get("dungeon") == state.interior["site"] and not art.get("claimed"):
            art["claimed"] = True
            heirloom = gen_item(rng.choice(["weapon", "armor", "ring"]),
                                name_pool(state.world), rng, tier=3)
            heirloom["name"] = art["name"]
            heirloom["id"] = "heirloom-" + art["name"].lower().replace(" ", "-")
            heirloom["value"] += 50
            give_item(state, heirloom, "The hoard yields")
            state.log(f"Legends spoke true: {art['name']}!")
            break
    else:
        item = gen_item(rng.choice(["weapon", "armor", "ring", "amulet"]),
                        name_pool(state.world), rng,
                        tier=min(6, 2 + rng.randint(0, 1) + danger_bonus(state)
                                 + (1 if lord else 0)))
        give_item(state, item, "Chest holds")
    gold = rng.randint(10, 30) * (2 if lord else 1)
    state.player.gold += gold
    state.log(f"+ {gold}g in the dust beside it.")
    _check_relic(state)


def _read_tablet(state: GameState, rng: random.Random) -> bool:
    from .dungeon import FLOOR, TABLET
    px, py = state.player.x, state.player.y
    grid, WW, HH = _play_grid(state)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = px + dx, py + dy
        if not (0 <= nx < WW and 0 <= ny < HH) or grid[ny][nx] != TABLET:
            continue
        mem = site_memory(state.world, state.interior["site"])
        tab = next((t for t in state.interior["tablets"]
                    if t["x"] == nx and t["y"] == ny), None)
        if tab is None or tab["id"] in mem["tablets"]:
            continue
        mem["tablets"].append(tab["id"])
        g = [list(r) for r in state.interior["grid"]]
        g[ny][nx] = FLOOR
        state.interior["grid"] = ["".join(r) for r in g]
        add_skill(state, "lore", 5)
        state.log("The stones teach you (+5 Lore).")
        if state.world.dormant_quests and rng.random() < 0.5:
            q = rng.choice(state.world.dormant_quests)
            state.world.dormant_quests.remove(q)
            state.world.quests.append(q)
            state.log(f"The stones whisper: {q.title}.")
        return True
    state.log("No legible stonework here.")
    return False


def learn_at_shrine(state: GameState) -> bool:
    """E on a shrine site: master one unknown spell of the realm. Each shrine
    teaches once ever — seek new stones for new words."""
    from .magic import spellbook
    px, py = state.player.x, state.player.y
    site = next((s for s in state.world.sites if s.x == px and s.y == py and s.kind == "shrine"), None)
    if site is None:
        return False
    mem = site_memory(state.world, site.name)
    if mem.get("taught"):
        state.log("This shrine has taught all it can. New stones, new words.")
        return True
    known = set(state.player.spells)
    unknown = [s for s in spellbook(state.world.lore_terms) if s["id"] not in known]
    if not unknown:
        state.log("The shrine hums. You know all it has to teach.")
        return True
    import random as _r
    spell = _r.Random(state.world.seed + len(known)).choice(unknown)
    state.player.spells.append(spell["id"])
    mem["taught"] = True
    advance(state, 60)
    play("quest")
    state.log(f"+ The shrine teaches you {spell['name']}! (C to cast.)")
    for q in list(state.world.quests):
        if q.kind == "pilgrimage":
            q.progress += 1
            if q.progress >= max(1, q.amount):
                _complete_quest(state, q)
            else:
                state.log(f"Pilgrimage: {q.progress}/{q.amount} shrines.")
    return True


def fuse_rows(state: GameState) -> list[dict]:
    """Shrine-fusion options: known fusable base x element (fee + known flag)."""
    from .magic import FUSABLE, ELEMENTS, FUSE_FEE, fused_def
    terms = name_pool(state.world)
    known = set(state.player.spells or [])
    rows = []
    for base in FUSABLE:
        if base not in known:
            continue
        for el in ELEMENTS:
            fid = f"{base}-{el}"
            sub, n = FUSE_FEE[el]
            from .items import mat_count
            rows.append({"base": base, "element": el, "id": fid,
                         "def": fused_def(terms, base, el),
                         "fee": f"{n} {sub}", "have": mat_count(state.player, sub) >= n,
                         "known": fid in known})
    return rows


def fuse_spell(state: GameState, base: str, element: str) -> bool:
    """Fuse at a shrine: known base x element for a material fee."""
    from .magic import FUSABLE, ELEMENTS, FUSE_FEE
    from .items import take_mats
    px, py = state.player.x, state.player.y
    if not any(s.x == px and s.y == py and s.kind == "shrine" for s in state.world.sites):
        state.log("Shrine fusion needs a shrine (*) underfoot.")
        return False
    if base not in FUSABLE or element not in ELEMENTS:
        return False
    if base not in (state.player.spells or []):
        state.log("You must know the base spell first (shrines teach).")
        return False
    fid = f"{base}-{element}"
    if fid in (state.player.spells or []):
        state.log("That fusion already burns in your book.")
        return False
    sub, n = FUSE_FEE[element]
    if not take_mats(state.player, sub, n):
        state.log(f"The shrine asks {n} {sub} (slain foes + wilds carry them).")
        return False
    state.player.spells.append(fid)
    advance(state, 60)
    play("quest")
    for q in list(state.world.quests):
        if q.kind == "pilgrimage":
            q.progress += 1
            if q.progress >= max(1, q.amount):
                _complete_quest(state, q)
            else:
                state.log(f"Pilgrimage: {q.progress}/{q.amount} shrines.")
    state.log(f"+ Fused {fid}! (C to cast.)")
    return True


HOME_PRICE = 200


def home_of(world) -> dict:
    h = getattr(world, "home", None)
    if not isinstance(h, dict):
        h = {}
    h.setdefault("city", "")
    h.setdefault("stash", [])
    h.setdefault("rise", False)
    world.home = h
    return h


def buy_home(state: GameState, city_name: str) -> bool:
    """Buy the city room: gear stash, rested sleep, settable rise point."""
    w = state.world
    if not any(c.name == city_name for c in w.cities):
        return False
    h = home_of(w)
    if h.get("city") == city_name:
        state.log("This is already home.")
        return False
    if state.player.gold < HOME_PRICE:
        state.log(f"A room here costs {HOME_PRICE}g (you hold {state.player.gold}g).")
        return False
    state.player.gold -= HOME_PRICE
    h["city"] = city_name
    play("coin")
    state.log(f"+ Home: a room in {city_name}. Stash gear (M), sleep (Z) for rested, rise here if set.")
    return True


def stash_put(state: GameState, inv_index: int) -> bool:
    h = home_of(state.world)
    if not h.get("city"):
        state.log("No home yet — buy a room in a city first.")
        return False
    inv = state.player.inventory
    if not (0 <= inv_index < len(inv)):
        return False
    h["stash"].append(inv.pop(inv_index))
    state.log(f"Stashed. ({len(h['stash'])} in the room.)")
    return True


def stash_take(state: GameState, stash_index: int) -> bool:
    h = home_of(state.world)
    if not h.get("city"):
        return False
    if not (0 <= stash_index < len(h["stash"])):
        return False
    if len(state.player.inventory) >= pack_cap(state.player):
        state.log(f"Pack is full ({pack_cap(state.player)}).")
        return False
    item = h["stash"].pop(stash_index)
    slot = item.get("slot", "")
    if slot and not state.player.equipment.get(slot):
        state.player.equipment[slot] = item
        state.log("Taken + equipped.")
    else:
        state.player.inventory.append(item)
        state.log("Taken.")
    return True


def set_rise(state: GameState, on: bool) -> bool:
    h = home_of(state.world)
    if not h.get("city"):
        state.log("No home yet.")
        return False
    h["rise"] = bool(on)
    state.log(f"You will rise {'at home in ' + h['city'] if on else 'where you fall'} henceforth.")
    return True


def _class_template(state: GameState) -> str:
    """Template id of the hero's calling ("" when unstoried)."""
    try:
        for c in (state.world.classes or []):
            if c.get("name") == state.player.class_name:
                return str(c.get("template", ""))
    except Exception:
        pass
    return ""


ARTS = {
    "warrior": ("Battle-cry", 80, "Bloodied thinking foes break and beg."),
    "mage": ("Overchannel", 40, "8hp buys a full well of mana."),
    "ranger": ("Double volley", 50, "One arrow, up to three foes down the lane."),
    "rogue": ("Vanish", 60, "Slip the grapple; next strike crits."),
    "cleric": ("Consecrate", 80, "The dead burn and flee."),
    "bard": ("Inspire", 100, "60 steps of richer tales (+5g a quest)."),
    "sorcerer": ("Wild surge", 50, "Loose raw sky at the nearest foe."),
    "paladin": ("Lay hands", 400, "Knit whole and clean (~400 steps)."),
}


def art_status(state: GameState) -> tuple[str, str, bool, int]:
    """(name, desc, ready, steps_left) for the hero's calling art."""
    p = state.player
    tpl = ""
    for c in (state.world.classes or []):
        if c.get("name") == p.class_name:
            tpl = c.get("template", "")
            break
    if tpl not in ARTS:
        return ("No art", "This calling walks unstoried.", False, 0)
    name, _cd, desc = ARTS[tpl]
    left = int((p.arts_cd or {}).get(tpl, 0)) - state.turns
    return (name, desc, left <= 0, max(0, left))


def use_art(state: GameState, rng: random.Random | None = None) -> bool:
    """P on the wilds: work your calling's one true trick."""
    from .items import eff_skill
    rng = rng or random.Random()
    p = state.player
    tpl = ""
    for c in (state.world.classes or []):
        if c.get("name") == p.class_name:
            tpl = c.get("template", "")
            break
    if tpl not in ARTS:
        state.log("Your calling keeps no arts. (Commoners dream louder.)")
        return False
    name, cd, _desc = ARTS[tpl]
    if int((p.arts_cd or {}).get(tpl, 0)) > state.turns:
        state.log(f"{name} is still catching its breath.")
        return False
    ok = False
    if tpl == "warrior":
        broke = 0
        for e in list(state.enemies):
            if not _hostile(e) or e.boss or abs(e.x - p.x) + abs(e.y - p.y) > 2:
                continue
            if e.kind in ("undead", "wraith", "golem", "drake"):
                continue
            frac = e.hp / max(1, e.max_hp or e.hp)
            if frac > 0.5:
                continue
            if e.kind in ("bandit", "soldier", "mage"):
                e.cowed, e.windup, broke = True, 0, broke + 1
            else:
                e.routed, e.windup, broke = 4, 0, broke + 1
        state.log(f"You bellow! {broke} foe(s) break." if broke else "You bellow! Nothing breaks — yet.")
        ok = True
    elif tpl == "mage":
        if p.hp <= 12:
            state.log("Too weak to channel.")
            return False
        p.hp -= 8
        p.mana = p.max_mana
        state.log("Pain into power: mana full (-8hp).")
        ok = True
    elif tpl == "ranger":
        from .items import wielded_bow
        if wielded_bow(p) is None or p.ammo < 1:
            state.log("Double volley needs a drawn bow and an arrow.")
            return False
        from .items import BOW_MIN, BOW_MAX
        lane = [e for e in state.enemies if _hostile(e)
                and BOW_MIN <= abs(e.x - p.x) + abs(e.y - p.y) <= BOW_MAX
                and has_los(state, p.x, p.y, e.x, e.y)]
        if not lane:
            state.log("No lane worth the arrow.")
            return False
        p.ammo -= 1
        dmg, _crit, dtype = ranged_damage(p, rng, state)
        for tgt in sorted(lane, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))[:3]:
            _hit_foe(state, tgt, dmg, dtype, rng, verb="Your volley catches")
        ok = True
    elif tpl == "rogue":
        near = any(_hostile(e) and abs(e.x - p.x) + abs(e.y - p.y) <= 2 for e in state.enemies)
        if not near and state.in_combat_with is None:
            state.log("No one to vanish from.")
            return False
        state.in_combat_with = None
        p.buffs["focus"] = 30
        add_skill(state, "sneak", 2)
        state.log("Gone. The next strike crits (30 steps).")
        ok = True
    elif tpl == "cleric":
        foes = [e for e in state.enemies if _hostile(e) and not e.boss
                and e.kind in ("undead", "wraith")
                and abs(e.x - p.x) + abs(e.y - p.y) <= 4]
        if not foes:
            state.log("No dead in reach to consecrate.")
            return False
        for tgt in foes:
            _hit_foe(state, tgt, 15, "ember", rng, verb="Light takes")
            if tgt.alive:
                tgt.routed = 4
        ok = True
    elif tpl == "bard":
        p.buffs["inspire"] = 120
        state.log("You sing! Tales pay +5g for 120 steps.")
        ok = True
    elif tpl == "sorcerer":
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= 7]
        if not foes:
            state.log("No foe in reach to surge at.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        el = rng.choice(["ember", "frost", "storm", "umbral"])
        p.last_strike = state.turns
        _hit_foe(state, tgt, 6 + p.attr("WIS") * 2 + eff_skill(p, "lore"),
                 el, rng, verb=f"Wild {el} takes")
        ok = True
    elif tpl == "paladin":
        from .items import eff_max_hp
        p.hp = min(eff_max_hp(p), p.hp + 30)
        p.poison, p.bleed = 0, 0
        state.log("Warm light knits you (+30hp, cleansed).")
        ok = True
    if ok:
        p.arts_cd[tpl] = state.turns + cd
        advance(state, 10)
    return ok


def _survey(state: GameState, site) -> None:
    """E on a watchtower: name every wild site within 25 leagues."""
    px, py = state.player.x, state.player.y
    near = sorted((s for s in state.world.sites if s.name != site.name
                   and abs(s.x - px) + abs(s.y - py) <= 25),
                  key=lambda s: abs(s.x - px) + abs(s.y - py))[:4]
    add_skill(state, "lore", 2)
    if not near:
        state.log(f"From {site.name}: nothing but wilds to the horizon.")
        return
    state.log(f"From {site.name} you spy:")
    for s in near:
        dx, dy = s.x - px, s.y - py
        horiz = "east" if dx > 0 else "west" if dx < 0 else ""
        vert = "south" if dy > 0 else "north" if dy < 0 else ""
        state.log(f"  {s.name} ({s.kind}), {abs(dx) + abs(dy)} leagues {vert}{horiz}.")


def _loot_camp(state: GameState, site, rng: random.Random) -> None:
    """E on a bandit camp: cleared blades only; the cache pays once."""
    from .items import gen_item
    mem = site_memory(state.world, site.name)
    guards = [e for e in state.enemies if e.alive
              and abs(e.x - site.x) + abs(e.y - site.y) <= 4]
    if guards:
        state.log(f"Clear the blades first ({len(guards)} guard(s) prowl)!")
        return
    if mem.get("cache"):
        state.log("Picked clean. Cold ashes.")
        return
    mem["cache"] = True
    gold = rng.randint(20, 50)
    state.player.gold += gold
    item = gen_item(rng.choice(["weapon", "armor"]), name_pool(state.world), rng, tier=2,
                    climate=state.world.climate)
    give_item(state, item, "The cache holds")
    state.log(f"+ {gold}g in the war-chest.")


def _share_meal(state: GameState, site) -> None:
    """E on a farm: one hot meal per day heals 15."""
    from .items import eff_max_hp
    mem = site_memory(state.world, site.name)
    today = state.world.clock // 1440
    if mem.get("meal_day") == today:
        state.log("The pot is empty till tomorrow.")
        return
    mem["meal_day"] = today
    state.player.hp = min(eff_max_hp(state.player), state.player.hp + 15)
    state.player.buffs["feast"] = 120
    advance(state, 30)
    state.log(f"+ {site.name} shares a hot meal (+15hp, feast regenerates).")


def _cast_bloodprice(state: GameState, rng: random.Random) -> bool:
    """The wild perk's answer: half your blood for ruin (mag x rank damage)."""
    from .perks import perk_rank, perk_mag
    p = state.player
    if p.hp <= 10:
        state.log("Too weak to pay the price.")
        return False
    foes = [e for e in state.enemies if _hostile(e)
            and abs(e.x - p.x) + abs(e.y - p.y) <= 4]
    if state.in_combat_with is not None and state.in_combat_with.alive:
        foes = [state.in_combat_with]
    if not foes:
        state.log("No foe near enough to price.")
        return False
    tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
    price = max(1, p.hp // 2)
    p.hp -= price
    p.last_strike = state.turns
    dmg = perk_mag(state, "bloodprice") * perk_rank(p, "bloodprice")
    state.log(f"Blood for ruin! You pay {price}hp.")
    if _hit_foe(state, tgt, dmg, "umbral", rng, verb="The price takes"):
        _status_tick(state, rng)
        return True
    if state.in_combat_with is tgt:
        _foe_counter(state, tgt, rng)
    _status_tick(state, rng)
    return True


def cast_spell(state: GameState, spell_id: str, rng: random.Random | None = None) -> bool:
    """Cast from the book. In combat the foe answers if it lives."""
    from .magic import spell_def
    from .perks import perk_rank, perk_mag
    rng = rng or random.Random()
    p = state.player
    if spell_id == "bloodprice" and "bloodprice" in (p.spells or []) \
            and perk_rank(p, "bloodprice"):
        return _cast_bloodprice(state, rng)
    spell = spell_def(name_pool(state.world), spell_id)
    if spell is None or spell_id not in p.spells:
        return False
    base = spell.get("base", spell_id)
    fused_el = spell.get("element", "")
    cost = max(1, spell["cost"] - eff_skill(p, "arcana") // 3)
    if p.mana < cost:
        state.log(f"Not enough mana for {spell['name']} ({cost}).")
        return False
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    add_skill(state, "arcana", 1)
    if base in ("bolt", "spark", "smite"):
        reach = {"bolt": 7, "spark": 7, "smite": 5}[base]
        base_n = {"bolt": 6, "spark": 3, "smite": 12}[base]
        wmult = {"bolt": 2, "spark": 1, "smite": 3}[base]
        dtype = fused_el or {"bolt": "ember", "spark": "storm", "smite": "umbral"}[base]
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= reach]
        if not foes:
            state.log("No foe in reach of the spell.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        p.mana -= cost
        p.last_strike = state.turns
        dmg = base_n + p.attr("WIS") * wmult + eff_skill(p, "lore")
        dealt, note = apply_affinity(dmg, dtype, tgt)
        tgt.hp -= dealt
        add_skill(state, "lore", 1)
        tag = " WEAK!" if note == "weak" else (" resisted." if note == "resisted" else "")
        state.log(f"{spell['name']} strikes {tgt.name} for {dealt}!{tag}")
        if dtype == "ember" and rng.random() < 0.35:
            tgt.burn = 3
        if not tgt.alive:
            state.in_combat_with = None if state.in_combat_with is tgt else state.in_combat_with
            _slay(state, tgt, rng)
        elif state.in_combat_with is tgt or (tgt.x == p.x and tgt.y == p.y):
            _foe_counter(state, tgt, rng)
    elif base == "mend":
        from .items import eff_max_hp
        if p.hp >= eff_max_hp(p) and p.poison <= 0:
            state.log("You are already whole.")
            return False
        p.mana -= cost
        from .perks import perk_rank, perk_mag
        mend_r = perk_rank(p, "mendpower")
        bonus = 4 if fused_el else 0  # fused mending knits deeper
        p.hp = min(eff_max_hp(p), p.hp + 12 + p.attr("WIS") * 2 + bonus
                   + (perk_mag(state, "mendpower") * mend_r if mend_r else 0))
        if p.poison > 0:
            p.poison = 0
            state.log(f"{spell['name']} knits you whole ({p.hp}hp) and burns the venom out.")
        else:
            state.log(f"{spell['name']} knits you whole ({p.hp}hp).")
        if state.in_combat_with:
            _foe_counter(state, state.in_combat_with, rng)
    elif base == "ward":
        p.mana -= cost
        p.shield = 10 + p.attr("WIS") * 2 + (6 if fused_el else 0)
        state.log(f"{spell['name']} settles over you ({p.shield} ward).")
        if state.in_combat_with:
            _foe_counter(state, state.in_combat_with, rng)
    elif base == "igni":
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= 2]
        if not foes:
            state.log("No foe close enough to burn.")
            return False
        p.mana -= cost
        p.last_strike = state.turns
        for tgt in foes:
            dmg = 5 + p.attr("WIS") * 2 + eff_skill(p, "lore")
            _hit_foe(state, tgt, dmg, "ember", rng, verb=f"{spell['name']} engulfs")
            tgt.burn = 3
        if state.in_combat_with is not None and state.in_combat_with.alive:
            _foe_counter(state, state.in_combat_with, rng)
    elif base == "aard":
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= 4]
        if not foes:
            state.log("Nothing in reach to push.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        p.mana -= cost
        p.last_strike = state.turns
        dmg = 3 + p.attr("WIS")
        _hit_foe(state, tgt, dmg, "physical", rng, verb=f"{spell['name']} hurls")
        if tgt.alive:
            tgt.windup = 0
            dx = (tgt.x > p.x) - (tgt.x < p.x)
            dy = (tgt.y > p.y) - (tgt.y < p.y)
            for _ in range(2):
                nx, ny = tgt.x + dx, tgt.y + dy
                if (dx or dy) and 0 <= nx < WW and 0 <= ny < HH \
                        and grid[ny][nx] in walk \
                        and not any(o.alive and o.x == nx and o.y == ny for o in state.enemies):
                    tgt.x, tgt.y = nx, ny
                else:
                    break
            state.log(f"{tgt.name} staggers back!")
            if state.in_combat_with is tgt and abs(tgt.x - p.x) + abs(tgt.y - p.y) <= 1:
                _foe_counter(state, tgt, rng)
            elif state.in_combat_with is tgt:
                state.in_combat_with = None
    elif base == "yrden":
        foes = [e for e in state.enemies if _hostile(e) and not e.boss
                and abs(e.x - p.x) + abs(e.y - p.y) <= 4]
        if not foes:
            state.log("Nothing in reach to snare.")
            return False
        p.mana -= cost
        for tgt in foes:
            tgt.slowed = max(tgt.slowed, 10)
        state.log(f"{spell['name']} chains {len(foes)} foe(s) — slowed 10 steps!")
        if state.in_combat_with:
            _foe_counter(state, state.in_combat_with, rng)
    elif base == "fury":
        foes = [e for e in state.enemies if _hostile(e) and not e.boss
                and abs(e.x - p.x) + abs(e.y - p.y) <= 5]
        if not foes:
            state.log("No weak mind in reach to madden.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        p.mana -= cost
        tgt.frenzied = 8
        tgt.windup = 0
        state.log(f"{tgt.name}'s eyes go red — it turns on its pack!")
        if state.in_combat_with is tgt:
            state.in_combat_with = None
    elif base == "frostbite":
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= 5]
        if not foes:
            state.log("No foe in reach to freeze.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        p.mana -= cost
        p.last_strike = state.turns
        dmg = 4 + p.attr("WIS") * 2 + eff_skill(p, "lore")
        _hit_foe(state, tgt, dmg, "frost", rng, verb=f"{spell['name']} bites")
        if tgt.alive:
            tgt.slowed = max(tgt.slowed, 6)
            state.log(f"{tgt.name} slows, rimed with frost!")
            if state.in_combat_with is tgt or (tgt.x == p.x and tgt.y == p.y):
                _foe_counter(state, tgt, rng)
    elif base == "summon":
        if any(e.alive and e.ally for e in state.enemies):
            state.log("Your spectral already walks. One at a time.")
            return False
        grid, WW, HH = _play_grid(state)
        walk = _play_walk(state)
        opts = [(p.x + dx, p.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= p.x + dx < WW and 0 <= p.y + dy < HH
                and grid[p.y + dy][p.x + dx] in walk
                and not any(o.alive and o.x == p.x + dx and o.y == p.y + dy
                            for o in state.enemies)]
        if not opts:
            state.log("No room beside you for the spectral to step through.")
            return False
        p.mana -= cost
        x, y = opts[0]
        terms = name_pool(state.world)
        term = (terms[0].capitalize() if terms else "Ash")
        pup = Enemy(name=f"Spectral {term} Wolf", x=x, y=y,
                    hp=25 + p.attr("WIS") * 3, atk=5 + p.attr("WIS") // 2,
                    kind="specter", ally=True, ally_ttl=25)
        pup.max_hp = pup.hp
        state.enemies.append(pup)
        state.log(f"+ {pup.name} pads from the mist (25 steps)! It fights for you.")
    elif base == "turn":
        foes = [e for e in state.enemies if _hostile(e) and not e.boss
                and e.kind in ("undead", "wraith")
                and abs(e.x - p.x) + abs(e.y - p.y) <= 3]
        if not foes:
            state.log("No dead in reach to turn.")
            return False
        p.mana -= cost
        for tgt in foes:
            tgt.routed = 4
            tgt.windup = 0
            state.log(f"{tgt.name} recoils from the dawncry and flees!")
    elif base == "blizzard":
        foes = [e for e in state.enemies if _hostile(e)
                and abs(e.x - p.x) + abs(e.y - p.y) <= 4]
        if not foes:
            state.log("No foe in reach of the storm.")
            return False
        p.mana -= cost
        p.last_strike = state.turns
        for tgt in foes:
            dmg = 8 + p.attr("WIS") * 3 + eff_skill(p, "lore")
            _hit_foe(state, tgt, dmg, "frost", rng, verb=f"{spell['name']} buries")
            if tgt.alive:
                tgt.slowed = max(tgt.slowed, 6)
        if state.in_combat_with is not None and state.in_combat_with.alive:
            _foe_counter(state, state.in_combat_with, rng)
    elif base == "invis":
        p.mana -= cost
        p.buffs["ghost"] = 12
        add_skill(state, "sneak", 2)
        foe = state.in_combat_with
        if foe is not None and abs(foe.x - p.x) + abs(foe.y - p.y) > 1:
            state.in_combat_with = None
        state.log(f"{spell['name']} settles over you — unseen 12 steps.")
    elif base == "mark":
        if state.interior is not None:
            state.log("Mark only under the open sky (not below).")
            return False
        if not p.mark:
            p.mana -= cost
            p.mark = [p.x, p.y]
            state.log(f"+ Hearthmark set here ({p.x}, {p.y}). Cast again to return.")
            return True
        mx, my = max(0, min(state.world.width - 1, p.mark[0])), \
            max(0, min(state.world.height - 1, p.mark[1]))
        dist = abs(mx - p.x) + abs(my - p.y)
        p.mana -= cost
        advance(state, max(30, dist * 2))
        p.x, p.y = mx, my
        for q in _escort_quests(state):
            state.companions[q.id] = {"x": p.x, "y": p.y}
        state.in_combat_with = None
        state.log(f"The mark calls you home ({mx}, {my}).")
    elif spell_id == "charm":
        foes = [e for e in state.enemies if _hostile(e) and not e.boss
                and abs(e.x - p.x) + abs(e.y - p.y) <= 5]
        if not foes:
            state.log("No charmable mind in reach.")
            return False
        tgt = min(foes, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
        p.mana -= cost
        tgt.charmed = state.turns + 30 + (10 if _class_template(state) == "bard" else 0)
        tgt.windup = 0
        state.log(f"{tgt.name} blinks, smiles, and forgets you.")
        if state.in_combat_with is tgt:
            state.in_combat_with = None
    elif spell_id == "blink":
        p.mana -= cost
        opts = [(x, y) for y in range(max(0, p.y - 5), min(HH, p.y + 6))
                for x in range(max(0, p.x - 5), min(WW, p.x + 6))
                if grid[y][x] in walk and abs(x - p.x) + abs(y - p.y) > 0]
        if opts:
            p.x, p.y = rng.choice(opts)
            state.log(f"{spell['name']}! You unravel elsewhere.")
        if state.in_combat_with:
            state.in_combat_with = None
            state.log("You blink clear of the fight.")
            state.player.winded = False
    elif spell_id == "sight":
        if state.interior is not None:
            state.log("Stone above stone: the sight cannot pierce the deep.")
            return False
        p.mana -= cost
        sites = sorted(state.world.sites,
                       key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))[:3]
        for s in sites:
            dx, dy = s.x - p.x, s.y - p.y
            horiz = "east" if dx > 0 else "west" if dx < 0 else ""
            vert = "south" if dy > 0 else "north" if dy < 0 else ""
            state.log(f"{spell['name']}: {s.name} ({s.kind}) {abs(dx)+abs(dy)} leagues {vert}{horiz}.")
        if not sites:
            state.log(f"{spell['name']}: nothing but wilds.")
        if state.in_combat_with:
            _foe_counter(state, state.in_combat_with, rng)
    else:
        return False
    advance(state, 5)
    return True


def danger_bonus(state: GameState) -> int:
    """Better steel where the realm is meaner: delves (+1) and ground far
    from every hearth (+1). Caps with the tier math at the call sites."""
    bonus = 0
    if state.interior is not None and state.interior.get("kind") in ("dungeon", "ruin"):
        bonus += 1
    if state.interior is None:
        p = state.player
        if all(abs(c.x - p.x) + abs(c.y - p.y) > 25 for c in state.world.cities):
            bonus += 1
    return bonus


# ---------------- factions: oaths, tides, ages ----------------
# Swear to a power (O), bleed its rivals, and the war itself can end: the
# winner takes the loser's towns, the annals turn a page (age+1), and after
# three days of peace a new war kindles. Endings close ages, never the game.

WAR_END_TIDE = 14


def oath_foes(state: GameState) -> list:
    """Powers the sworn power is at war with (empty when unsworn)."""
    if not state.player.oath:
        return []
    f = next((f for f in state.world.factions if f.id == state.player.oath), None)
    return list(f.at_war) if f is not None else []


def faction_rows(state: GameState) -> list[dict]:
    """Oath panel rows: every power with cities, foes, standing, oath mark."""
    from .worldgen import faction_name
    out = []
    for f in state.world.factions:
        out.append({"id": f.id, "name": faction_name(state.world, f.id),
                    "cities": len(f.cities),
                    "foes": [faction_name(state.world, x) for x in f.at_war],
                    "standing": int(state.player.standing.get(f.id, 0)),
                    "oath": state.player.oath == f.id})
    return out


def swear_oath(state: GameState, fid: str) -> bool:
    from .worldgen import faction_name
    w = state.world
    if not any(f.id == fid for f in w.factions) or state.player.oath == fid:
        return False
    if state.player.oath:
        state.player.standing[state.player.oath] = \
            min(int(state.player.standing.get(state.player.oath, 0)), 0) - 5
        state.log(f"You break faith with {faction_name(w, state.player.oath)}.")
    state.player.oath = fid
    play("quest")
    state.log(f"You kneel and swear to {faction_name(w, fid)}. Its blades will know you. "
              f"Healing and caravans come cheaper in its towns.")
    return True


def forswear_oath(state: GameState) -> bool:
    from .worldgen import faction_name
    if not state.player.oath:
        return False
    old = state.player.oath
    state.player.oath = ""
    state.player.standing[old] = min(int(state.player.standing.get(old, 0)), 0) - 5
    state.log(f"You lay down the colors of {faction_name(state.world, old)} (standing "
              f"{state.player.standing[old]}). No power will trust you soon.")
    return True


def _credit_war_kill(state: GameState, e: Enemy) -> None:
    """A sworn-color death moves the tide: rivals love you, the victim bills you."""
    from .worldgen import faction_name
    fid = e.faction
    if not fid:
        return
    w = state.world
    from .perks import perk_rank, perk_mag
    prof = perk_rank(state.player, "warprofiteer")
    w.war_tide[fid] = int(w.war_tide.get(fid, 0)) + 1 + \
        (perk_mag(state, "warprofiteer") * prof if prof else 0)
    me = next((f for f in w.factions if f.id == fid), None)
    for r in (me.at_war if me is not None else []):
        state.player.standing[r] = int(state.player.standing.get(r, 0)) + 2
    state.player.standing[fid] = int(state.player.standing.get(fid, 0)) - 3
    if fid == state.player.oath:
        state.player.standing[fid] -= 5
        state.log(f"Oathbreaker! {faction_name(w, fid)} marks your treason "
                  f"({state.player.standing[fid]}).")
    elif me is not None and any(r == state.player.oath for r in me.at_war):
        state.log(f"For {faction_name(w, state.player.oath)}! "
                  f"({faction_name(w, fid)} tide: {w.war_tide[fid]}.)")
    _check_war_end(state, fid)


def _check_war_end(state: GameState, fid: str) -> None:
    w = state.world
    me = next((f for f in w.factions if f.id == fid), None)
    if me is None:
        return
    for rid in list(me.at_war):
        foe = next((f for f in w.factions if f.id == rid), None)
        if foe is None:
            continue
        a, b = int(w.war_tide.get(fid, 0)), int(w.war_tide.get(rid, 0))
        if a + b < WAR_END_TIDE:
            continue
        if a > b:
            _end_war(state, winner=foe, loser=me)
        elif b > a:
            _end_war(state, winner=me, loser=foe)
        else:
            _end_war(state, *(_tiebreak(state, me, foe)))
        return


def _tiebreak(state: GameState, a, b) -> tuple:
    """Even blood: more towns win; truly even, the seed decides."""
    if len(a.cities) != len(b.cities):
        return (a, b) if len(a.cities) > len(b.cities) else (b, a)
    rng = random.Random(state.world.seed + state.world.age * 101)
    return (a, b) if rng.random() < 0.5 else (b, a)


def _end_war(state: GameState, winner, loser) -> None:
    """An age ends: towns kneel, the annals turn, peace pays, play goes on."""
    from .worldgen import faction_name
    w = state.world
    taken = [c.name for c in w.cities if c.faction == loser.id]
    for c in w.cities:
        if c.faction == loser.id:
            c.faction = winner.id
    winner.cities = sorted(set(winner.cities) | set(taken))
    loser.cities = []
    winner.at_war = [x for x in winner.at_war if x != loser.id]
    loser.at_war = [x for x in loser.at_war if x != winner.id]
    w.war_tide[winner.id] = 0
    w.war_tide[loser.id] = 0
    last_year = max([e.get("year", 0) for e in w.history] + [800])
    w.history.append({"year": last_year + 1, "kind": "age",
                      "text": f"Age {w.age} ends: {winner.name} breaks {loser.name}; "
                              f"{len(taken)} towns kneel.",
                      "place": taken[0] if taken else ""})
    w.history.sort(key=lambda e: (e.get("year", 0), e.get("kind", "")))
    w.age += 1
    w.peace_until = w.clock + 3 * 1440
    # a new age rebuilds the director deck (no repeats within an age)
    try:
        from .director import reset_for_age as _reset_age
        mem = list(getattr(w, "director_memory", []) or [])
        act = getattr(w, "director_active", None)
        _reset_age(w)
        w.director_memory = mem
        w.director_active = act
    except Exception:
        pass
    w.ending = (f"AGE {w.age - 1} ENDS — {winner.name} triumphs! {loser.name} kneels, "
                f"{len(taken)} towns change colors. +150g. (Enter)")
    state.player.gold += 150
    state.player.buffs["triumph"] = 60
    state.player.standing[winner.id] = int(state.player.standing.get(winner.id, 0)) + 5
    _tally(state.world, "ages")
    play("quest")
    state.log(f"! {w.ending}")


def _brew_war(state: GameState) -> None:
    """After three days of peace, old grudges kindle a new war. Endlessly."""
    from .worldgen import faction_name
    w = state.world
    if any(f.at_war for f in w.factions) or len(w.factions) < 2:
        return
    if w.clock < w.peace_until:
        return
    cands = [f for f in w.factions if f.cities]
    if len(cands) < 2:
        return
    rng = random.Random(w.seed * 7 + w.age)
    a, b = rng.sample(cands, 2)
    a.at_war.append(b.id)
    b.at_war.append(a.id)
    state.log(f"! War kindles anew: {faction_name(w, a.id)} vs {faction_name(w, b.id)}. "
              f"Choose a side (O).")


def _slay(state: GameState, e: Enemy, rng: random.Random) -> None:
    """Shared kill resolution for blade and bolt (loot, bounties, bosses)."""
    from .items import loot_drop, eff_attr, gen_item
    p = state.player
    loot = rng.randint(5, 15) + eff_attr(p, "LUK") // 2
    if e.kind == "soldier":
        loot += 10
    if e.kind == "golem":
        loot += 15
    if e.kind == "drake":
        loot += 30
    if e.trait == "Cursed":
        loot += 20
    if e.boss:
        loot += rng.randint(30, 60)
        mem = site_memory(state.world, state.interior["site"] if state.interior else "")
        mem["boss_dead"] = True
    p.gold += loot
    xp = xp_gain(p, (120 if e.boss else 20 + e.atk * 3))
    tag = "BOSS SLAIN" if e.boss else f"{e.name} falls"
    state.log(f"+ {tag}! +{loot}g +{xp}xp.")
    play("slay")
    gain_xp(state, xp)
    if e.boss:
        p.buffs["triumph"] = 60
        state.log("+ Triumph surges through you (+3 ATK, 60 steps).")
    if e.kind == "beast":
        add_skill(state, "survival", 1)
    elif e.kind in ("undead", "wraith"):
        add_skill(state, "lore", 1)
    elif e.kind == "spider":
        add_skill(state, "survival", 1)
    elif e.kind == "drake":
        add_skill(state, "lore", 2)
    tier = min(6, 1 + e.atk // 4 + (1 if e.trait == "Cursed" else 0)
               + (1 if e.kind == "drake" else 0) + danger_bonus(state))
    from .perks import perk_rank, perk_mag
    scav = perk_rank(p, "scavenger")
    luck = eff_attr(p, "LUK") + (5 if (p.buffs or {}).get("greed", 0) > 0 else 0)
    drop = loot_drop(name_pool(state.world), rng, e.atk, luck,
                     tier=tier, bonus=eff_skill(p, "salvage") * 0.01
                     + (perk_mag(state, "scavenger") * scav / 100 if scav else 0),
                     climate=state.world.climate,
                     min_rarity="keen" if e.boss else "common")
    if drop is not None:
        add_skill(state, "salvage", 2)
        give_item(state, drop, "Looted")
    from .items import consumable_drop
    use = consumable_drop(name_pool(state.world), rng)
    if use is not None:
        give_item(state, use, "Looted")
    _salvage(state, e, rng)
    if e.boss:
        prize = gen_item(rng.choice(["weapon", "armor", "ring"]),
                         name_pool(state.world), rng, tier=4 if e.trait == "Dread" else 3,
                         climate=state.world.climate,
                         min_rarity="runed" if e.trait == "Dread" else "keen")
        give_item(state, prize, "The hoard yields")
    found = _find_quest(state, "bounty", e.name)
    if found:
        _complete_quest(state, found)
    # hunt quests: every kill counts toward active culls (blade, bolt, burn)
    for q in list(state.world.quests):
        if q.kind == "hunt":
            q.progress += 1
            if q.progress >= max(1, q.amount):
                _complete_quest(state, q)
            else:
                state.log(f"Hunt: {q.progress}/{q.amount} {q.target_enemy} raiders.")
    for q in list(state.world.quests):
        if q.kind == "finale" and q.target_enemy == e.name:
            _complete_quest(state, q)
            break
    state.world.kill_count += 1
    _tally(state.world, "kills")
    try:
        state.world.recent_blood = min(100.0, float(getattr(state.world, "recent_blood", 0) or 0.0) + 15.0)
    except Exception:
        pass
    _maybe_rise_captain(state, rng)
    _credit_war_kill(state, e)


def _maybe_rise_captain(state: GameState, rng: random.Random) -> None:
    """Blood calls blood: every 8th kill, a new captain rises and is posted."""
    from .quests import Quest
    w = state.world
    if w.kill_count % 8 != 0:
        return
    bandits = [c for c in w.characters if c.role == "bandit"] or w.characters[:2]
    if not bandits:
        return
    base = rng.choice(bandits).name
    name = f"{base} the {rng.choice(['Cruel', 'Black', 'Red', 'Scarred', 'One-Eye'])}"
    if any(e.alive and e.name == name for e in state.enemies):
        return
    level = state.player.level
    hp, atk = 45 + level * 7, 9 + level
    trait = rng.choice(["Savage", "Towering", "Cursed"])
    if trait == "Savage":
        atk += 3
    elif trait == "Towering":
        hp += 25
    grid, WW, HH = _play_grid(state)
    walk = _play_walk(state)
    for _ in range(80):
        x = max(0, min(WW - 1, state.player.x + rng.randint(-12, 12)))
        y = max(0, min(HH - 1, state.player.y + rng.randint(-12, 12)))
        if grid[y][x] in walk and abs(x - state.player.x) + abs(y - state.player.y) > 5:
            state.enemies.append(Enemy(name=name, x=x, y=y, hp=hp, atk=atk, trait=trait))
            break
    else:
        return
    qid = f"bounty-{name.lower().replace(' ', '-')}-{w.kill_count}"
    if qid not in {q.id for q in w.quests} and qid not in w.completed_quests:
        w.quests.append(Quest(
            id=qid, kind="bounty", title=f"Bounty: {name}",
            giver="The Wilds", target_enemy=name,
            flavor=f"{name} rose from the blood you spilled. End them.",
            reward_gold=25, reward_xp=60))
    state.log(f"! A new captain rises: {trait} {name}! Bounty posted.")


HEAVY_WINDUP_CHANCE = {
    "bandit": 0.15, "beast": 0.15, "spider": 0.15, "undead": 0.12,
    "soldier": 0.20, "golem": 0.25, "wraith": 0.20, "drake": 0.30,
}

POISON_ON_HIT = {
    "spider": 0.30, "undead": 0.15, "beast": 0.10, "wraith": 0.10,
    "bandit": 0.05, "soldier": 0.05, "golem": 0.0, "drake": 0.0,
}


BLEED_ON_HIT = {
    "beast": 0.10, "spider": 0.10, "bandit": 0.05, "soldier": 0.05,
}


def _status_tick(state: GameState, rng: random.Random | None = None) -> None:
    """Venom's tithe, open veins, and deep wells tick down together."""
    from .perks import perk_rank, perk_mag
    p = state.player
    if p.hp <= 0:
        return
    r = perk_rank(p, "manafont")
    if r:
        p.mana = min(p.max_mana, p.mana + r)
    if p.poison > 0:
        p.poison -= 1
        p.hp -= 2
        state.ping(p.x, p.y, "2", (80, 220, 80))
        if p.poison <= 0:
            state.log("The venom runs its course.")
        else:
            state.log(f"! Venom burns you (2hp, {p.poison} left). Mend cures it.")
    if p.bleed > 0 and p.hp > 0:
        p.bleed -= 1
        p.hp -= 1
        state.ping(p.x, p.y, "1", (220, 60, 60))
        if p.bleed <= 0:
            state.log("The bleeding staunches itself.")
        else:
            state.log(f"! You bleed (1hp, {p.bleed} left). Draughts staunch it.")
    if p.hp <= 0 and not _second_wind(state):
        play("death")
        state.log("x Your afflictions fell you. Press R on the map to rise.")


def _maybe_poison(state: GameState, e: Enemy, rng: random.Random) -> None:
    p = state.player
    if p.hp <= 0:
        return
    if p.poison <= 0:
        chance = POISON_ON_HIT.get(e.kind, 0.0)
        if e.trait == "Cursed":
            chance += 0.10
        if chance > 0 and rng.random() < chance:
            p.poison = 6
            state.log(f"! {e.name}'s filth festers — POISONED (6). Mend cures it.")
    if p.hp > 0 and p.bleed <= 0:
        chance = BLEED_ON_HIT.get(e.kind, 0.0)
        if e.trait == "Savage":
            chance += 0.30
        if chance > 0 and rng.random() < chance:
            p.bleed = 4
            state.log(f"! {e.name} opens a vein — BLEEDING (4). Draughts staunch it.")


def _second_wind(state: GameState) -> bool:
    """Cheat death once: at 0 or less, rise at 1hp and spend the brew."""
    p = state.player
    buffs = p.buffs if hasattr(p, "buffs") else {}
    if p.hp <= 0 and isinstance(buffs, dict) and buffs.get("secondwind", 0) > 0:
        buffs.pop("secondwind", None)
        p.hp = 1
        state.log("! Second wind! You refuse the dark (1hp).")
        state.ping(p.x, p.y, "1", (150, 230, 150))
        return True
    return False


def _hurt_player(state: GameState, e: Enemy, edmg: int, dtype: str,
                 rng: random.Random, blow: str) -> None:
    """One applied reply: wards, winded, guard, poison, death. Shared by all."""
    from .items import eff_resists
    from .perks import perk_rank, perk_mag
    p = state.player
    r = perk_rank(p, "slip")
    if r and rng.random() < perk_mag(state, "slip") * r / 100:
        state.log(f"You slip aside from {e.name} untouched!")
        return
    if dtype in eff_resists(p):
        edmg = max(1, edmg // 2)
        state.log(f"Your {dtype}-ward drinks the blow!")
    if p.winded:
        edmg = max(1, round(edmg * 1.5))
        p.winded = False
        state.log("Winded from the heavy swing — you eat the worst of it!")
    if p.guarding:
        b = perk_rank(p, "bulwark")
        mult = max(0.1, 0.4 - (perk_mag(state, "bulwark") * b / 100 if b else 0))
        edmg = max(1, round(edmg * mult))
        p.guarding = False
        state.log("Your guard turns the blow.")
    buffs = p.buffs if hasattr(p, "buffs") else p.get("buffs", {})
    if (buffs or {}).get("iron", 0) > 0:
        edmg = max(1, edmg - 2)
        state.log("Your ironhide drinks deep of it.")
    if p.shield > 0:
        absorbed = min(p.shield, edmg)
        p.shield -= absorbed
        edmg -= absorbed
        if edmg <= 0:
            state.log(f"Your ward drinks the blow ({p.shield} ward left).")
            return
    p.hp -= edmg
    state.log(f"! {e.name} {blow} for {edmg} ({max(0, p.hp)} left).")
    state.ping(p.x, p.y, str(edmg), (255, 80, 80))
    state.flash(p.x, p.y)
    play("hurt")
    _maybe_poison(state, e, rng)
    t = perk_rank(p, "thorns")
    if t and e.alive and blow in ("hits you", "CRUSHES you"):
        _hit_foe(state, e, perk_mag(state, "thorns") * t, "physical", rng,
                 verb="Your thorns catch")
    if p.hp <= 0 and _second_wind(state):
        return
    if p.hp <= 0:
        play("death")
        state.log("x You fell. Press R on the map to rise at the nearest city.")


def _foe_counter(state: GameState, e: Enemy, rng: random.Random,
                 soft: bool = False) -> None:
    if e is None or not e.alive:
        return
    if _foe_draught(state, e):
        return
    from .items import eff_resists
    p = state.player
    if e.windup:
        e.windup = 0
        edmg = max(1, round(e.atk * 1.8) + rng.randint(-1, 2))
        heavy = True
    else:
        chance = HEAVY_WINDUP_CHANCE.get(e.kind, 0.15)
        if e.boss:
            chance += 0.10
        if e.enraged:
            chance += 0.15
        if rng.random() < chance:
            e.windup = 1
            state.log(f"! {e.name} gathers itself — HEAVY incoming! Defend (D) or spoil it (Quick)!")
            return
        edmg = max(1, e.atk + rng.randint(-2, 2))
        heavy = False
    dtype = FOE_DTYPE.get(e.kind, "physical")
    if dtype in eff_resists(state.player):
        edmg = max(1, edmg // 2)
        state.log(f"Your {dtype}-ward drinks the blow!")
    if soft:
        edmg = max(1, edmg // 2)
    if heavy and p.guarding:
        # a set shield wall all but stops the overhead chop
        p.guarding = False
        state.log("Your guard turns the blow.")
        _hurt_player(state, e, max(1, edmg // 4), dtype, rng, "CRUSHES you")
        return
    blow = "CRUSHES you" if heavy else "hits you"
    _hurt_player(state, e, edmg, dtype, rng, blow)


def respawn(state: GameState) -> bool:
    """Rise at the nearest city with half gold. Returns False if not dead."""
    if state.player.hp > 0:
        return False
    _tally(state.world, "deaths")
    # death drags you out of the deep; the overworld resumes as it was
    if state.interior is not None:
        snap = state.world.active_interior or {}
        try:
            state.enemies = [Enemy(**e) for e in snap.get("ow_enemies", state.enemies)]
        except Exception:
            pass
        state.interior = None
        state.world.active_interior = None
    p = state.player
    home = home_of(state.world)
    rise_city = next((c for c in state.world.cities if c.name == home.get("city", "")), None) \
        if home.get("rise") else None
    best, best_d = None, None
    for c in state.world.cities:
        d = abs(c.x - p.x) + abs(c.y - p.y)
        if best_d is None or d < best_d:
            best, best_d = c, d
    if rise_city is not None:
        best = rise_city
    if best:
        p.x, p.y = best.x, best.y
    from .items import eff_max_hp
    p.hp = eff_max_hp(p)
    p.gold //= 2
    p.poison = 0
    p.guarding = False
    p.bleed = 0
    p.winded = False
    state.in_combat_with = None
    for q in _escort_quests(state):
        q.comp_hp = 0  # mercy of the temple: the fallen walk out beside you
        state.companions[q.id] = {"x": p.x, "y": p.y}
    # scatter living enemies away so you don't instantly re-die
    for e in state.enemies:
        if e.alive and abs(e.x - p.x) + abs(e.y - p.y) < 4:
            e.x = max(0, min(state.world.width - 1, e.x + 6))
    state.log(f"+ You rise in {best.name if best else 'the wilds'}. Gold halved: {p.gold}.")
    return True


def combat_flee(state: GameState, rng: random.Random | None = None) -> None:
    e = state.in_combat_with or _adjacent_foe(state, rng)
    if not e:
        return
    rng = rng or random.Random()
    if rng.random() < flee_chance(state.player, state):
        state.log(f"You fled from {e.name}.")
        e.windup = 0
        state.player.guarding = False
        state.player.winded = False
        add_skill(state, "sneak", 3)
        grid, WW, HH = _play_grid(state)
        walk = _play_walk(state)
        # step back to a random adjacent walkable tile
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = state.player.x + dx, state.player.y + dy
            if 0 <= nx < WW and 0 <= ny < HH:
                if grid[ny][nx] in walk:
                    state.player.x, state.player.y = nx, ny
                    break
        state.in_combat_with = None
    else:
        edmg = max(1, e.atk)
        if state.player.guarding:
            edmg = max(1, round(edmg * 0.4))
            state.player.guarding = False
        state.player.hp -= edmg
        state.log(f"Failed to flee! {e.name} hits for {edmg}.")
        _second_wind(state)


INVENTORY_CAP = 40


def pack_cap(p: Player) -> int:
    """40 scrolls of pack, plus ten per hoarder rank."""
    from .perks import perk_rank
    return INVENTORY_CAP + 10 * perk_rank(p, "hoarder")


def give_item(state: GameState, item: dict, verb: str = "Got") -> bool:
    """Add loot/reward to the pack, auto-equipping into an empty better slot."""
    from .items import item_line
    p = state.player
    slot = item.get("slot", "")
    if len(p.inventory) >= pack_cap(p):
        state.log(f"{verb}: {item['name']} — your pack is full ({pack_cap(p)}). Left behind.")
        return False
    if slot and not p.equipment.get(slot):
        p.equipment[slot] = item
        state.log(f"{verb}: {item_line(item)} — equipped!")
    else:
        p.inventory.append(item)
        state.log(f"{verb}: {item_line(item)}.")
    return True


def _clamp_hp(state: GameState) -> None:
    from .items import eff_max_hp
    p = state.player
    if p.hp > eff_max_hp(p):
        p.hp = eff_max_hp(p)


def equip_item(state: GameState, index: int) -> bool:
    """Equip inventory[index], swapping the old piece back to the pack.
    Consumables are USED instead of worn."""
    p = state.player
    if not (0 <= index < len(p.inventory)):
        return False
    item = p.inventory[index]
    if (item.get("kind") or "") == "consumable":
        return use_consumable(state, index)
    slot = item.get("slot", "")
    if not slot:
        return False
    old = p.equipment.get(slot)
    p.equipment[slot] = item
    del p.inventory[index]
    if old:
        p.inventory.append(old)
        state.log(f"Equipped {item['name']} (stowed {old['name']}).")
    else:
        state.log(f"Equipped {item['name']}.")
    return True


def unequip_item(state: GameState, slot: str) -> bool:
    p = state.player
    item = (p.equipment or {}).get(slot)
    if not item:
        return False
    if len(p.inventory) >= pack_cap(p):
        state.log("Pack is full — cannot unequip.")
        return False
    p.inventory.append(item)
    p.equipment[slot] = None
    _clamp_hp(state)
    state.log(f"Unequipped {item['name']}.")
    return True


def destroy_item(state: GameState, index: int) -> bool:
    p = state.player
    if not (0 <= index < len(p.inventory)):
        return False
    item = p.inventory.pop(index)
    state.log(f"Destroyed {item['name']}.")
    return True


def city_shop(state: GameState) -> list[dict] | None:
    """The merchant stock of the city underfoot (or the town you're inside)."""
    p = state.player
    if state.interior is not None and state.interior.get("kind") == "city":
        return state.world.shops.setdefault(state.interior["site"], [])
    for c in state.world.cities:
        if c.x == p.x and c.y == p.y:
            return state.world.shops.setdefault(c.name, [])
    return None


def shop_rows(state: GameState, building: int | None = None) -> list[tuple[int, dict]]:
    """View into city stock: whole market overworld, or one door's share in town."""
    stock = city_shop(state) or []
    if building is None:
        return list(enumerate(stock))
    n = max(1, len(state.interior.get("shop_buildings", [])) if state.interior else 1)
    return [(ri, it) for ri, it in enumerate(stock) if ri % n == building % n]


def _shop_city(state: GameState) -> str:
    p = state.player
    if state.interior is not None and state.interior.get("kind") == "city":
        return str(state.interior.get("site", ""))
    for c in state.world.cities:
        if c.x == p.x and c.y == p.y:
            return c.name
    return ""


def shop_buy(state: GameState, index: int) -> bool:
    stock = city_shop(state)
    p = state.player
    if stock is None or not (0 <= index < len(stock)):
        return False
    item = stock[index]
    from . import trade as _trade
    price = _trade.buy_price(state.world, _shop_city(state), item)
    if p.gold < price:
        state.log(f"Cannot afford {item['name']} ({price}g).")
        return False
    if len(p.inventory) >= pack_cap(p):
        state.log(f"Pack is full ({pack_cap(p)}).")
        return False
    p.gold -= price
    del stock[index]
    from .items import item_line
    play("coin")
    slot = item.get("slot", "")
    if slot and not p.equipment.get(slot):
        p.equipment[slot] = item
        state.log(f"Bought + equipped {item_line(item)}. Gold: {p.gold}.")
    else:
        p.inventory.append(item)
        state.log(f"Bought {item_line(item)}. Gold: {p.gold}.")
    return True


def shop_sell(state: GameState, index: int) -> bool:
    """Sell a PACK item (equipped gear must come off first). Goods ride the
    city's current demand; gear resells flat at half price."""
    stock = city_shop(state)
    p = state.player
    if stock is None or not (0 <= index < len(p.inventory)):
        return False
    item = p.inventory.pop(index)
    from . import trade as _trade
    price = _trade.sell_price(state.world, _shop_city(state), item)
    p.gold += price
    play("coin")
    stock.append(item)
    state.log(f"Sold {item['name']} for {price}g. Gold: {p.gold}.")
    return True


def reforge_rows(state: GameState) -> list[tuple[str, int | str]]:
    """Smith's bench: worn slots first, then the pack. Locators for shop_reforge."""
    from .items import SLOTS
    rows: list[tuple[str, int | str]] = []
    for slot in SLOTS:
        if (state.player.equipment or {}).get(slot):
            rows.append(("worn", slot))
    for i in range(len(state.player.inventory)):
        rows.append(("pack", i))
    return rows


def shop_reforge(state: GameState, locator: tuple[str, int | str],
                 rng: random.Random | None = None) -> bool:
    """Pay the smith to raise one piece a tier (cap 5). The gold sink."""
    from .items import reforge_cost, reforge_item
    rng = rng or random.Random()
    if city_shop(state) is None:
        return False
    kind, key = locator
    item = None
    if kind == "worn":
        item = (state.player.equipment or {}).get(key)  # type: ignore[arg-type]
    elif kind == "pack" and isinstance(key, int) and 0 <= key < len(state.player.inventory):
        item = state.player.inventory[key]
    if not isinstance(item, dict):
        return False
    if (item.get("kind") or "") == "consumable" or not item.get("slot"):
        state.log(f"{item.get('name', 'That')} takes no hammer.")
        return False
    cost = reforge_cost(item)
    if state.player.gold < cost:
        state.log(f"Reforge needs {cost}g (you hold {state.player.gold}g).")
        return False
    ok, note = reforge_item(item, rng)
    if not ok:
        state.log(f"The smith shakes her head: {note}.")
        return False
    state.player.gold -= cost
    play("coin")
    state.log(f"Reforged {item['name']} for {cost}g ({note}). Gold: {state.player.gold}.")
    return True


# ---------------- pygame frontend ----------------

def run_pygame(state: GameState) -> None:
    try:
        import pygame
    except ImportError as exc:
        raise SystemExit("pygame not installed. Run: pip install -r requirements.txt") from exc

    pygame.init()
    CELL = 22
    VIEW_W, VIEW_H = 31, 21  # tiles visible
    HUD_H = 190
    screen = pygame.display.set_mode((VIEW_W * CELL, VIEW_H * CELL + HUD_H))
    pygame.display.set_caption("Inkbound Realms - ASCII RPG")
    try:
        font = pygame.font.SysFont("consolas,courier new,monospace", 18)
        small = pygame.font.SysFont("consolas,courier new,monospace", 15)
    except Exception:
        font = pygame.font.Font(None, 20)
        small = pygame.font.Font(None, 16)

    COLORS = {
        ".": (120, 160, 120), ",": (70, 130, 180), "~": (40, 90, 200),
        "T": (40, 140, 60), "^": (150, 150, 160), "O": (255, 215, 0),
    }
    BG = (12, 14, 20)
    clock = pygame.time.Clock()
    running = True

    def tile_at(x: int, y: int) -> str:
        return state.world.grid[y][x]

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                import pygame as _pg
                if k == _pg.K_q:
                    running = False
                elif state.in_combat_with:
                    if k == _pg.K_a:
                        combat_attack(state)
                    elif k == _pg.K_f:
                        combat_flee(state)
                else:
                    if k in (_pg.K_UP, _pg.K_w):
                        move_player(state, 0, -1)
                    elif k in (_pg.K_DOWN, _pg.K_s):
                        move_player(state, 0, 1)
                    elif k in (_pg.K_LEFT, _pg.K_a):
                        move_player(state, -1, 0)
                    elif k in (_pg.K_RIGHT, _pg.K_d):
                        move_player(state, 1, 0)
                    elif k == _pg.K_e:
                        interact(state)
                    elif k == _pg.K_h:
                        heal(state)

        screen.fill(BG)
        px, py = state.player.x, state.player.y
        ox = px - VIEW_W // 2
        oy = py - VIEW_H // 2
        for vy in range(VIEW_H):
            for vx in range(VIEW_W):
                wx, wy = ox + vx, oy + vy
                if 0 <= wx < state.world.width and 0 <= wy < state.world.height:
                    t = tile_at(wx, wy)
                    ch, col = t, COLORS.get(t, (200, 200, 200))
                else:
                    ch, col = " ", (0, 0, 0)
                # entities override
                for c in state.world.cities:
                    if c.x == wx and c.y == wy:
                        ch, col = "O", COLORS["O"]
                for e in state.enemies:
                    if e.alive and e.x == wx and e.y == wy:
                        ch, col = "E", (255, 80, 80)
                if wx == px and wy == py:
                    ch, col = "@", (255, 255, 255)
                img = font.render(ch, True, col)
                screen.blit(img, (vx * CELL + 5, vy * CELL + 2))

        # HUD
        base = VIEW_H * CELL
        hud = [
            f"HP {max(0, state.player.hp)}/{state.player.max_hp}  ATK {state.player.atk}  Gold {state.player.gold}  Quests {state.player.quests_done}  Pos ({px},{py})",
        ]
        if state.in_combat_with:
            e = state.in_combat_with
            hud.append(f"COMBAT vs {e.name} (HP {max(0, e.hp)}) -- (A)ttack  (F)lee")
        else:
            hud.append("Move WASD/arrows  E talk/quest  H heal in city  Q quit")
        for msg in state.messages[-5:]:
            hud.append(msg[:95])
        for i, line in enumerate(hud[:8]):
            img = small.render(line, True, (220, 220, 220))
            screen.blit(img, (8, base + 6 + i * 22))
        pygame.display.flip()
        clock.tick(30)

        if state.player.hp <= 0:
            # freeze until quit but keep rendering
            pass
    pygame.quit()
