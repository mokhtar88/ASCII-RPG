"""Procedural world built from extracted book lore."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .extract import Lore, extract_entities
from .names import unique_names, FALLBACK_CITY_STEMS, FALLBACK_NAME_STEMS, SUFFIXES
from .quests import Quest as _Quest, build_quests

# Map tiles
DEEP_WATER = "~"
WATER = ","
RIVER = "r"
SAND = "s"
PLAIN = "."
FOREST = "T"
MOUNTAIN = "^"
CITY_TILE = "O"
DUNGEON_TILE = "D"
RUIN_TILE = "#"
ROAD_TILE = "="
SHRINE_TILE = "*"
TOWER_TILE = "!"
CAMP_TILE = "X"
FARM_TILE = "v"

WALKABLE = {PLAIN, FOREST, SAND, RIVER, CITY_TILE, DUNGEON_TILE,
            RUIN_TILE, ROAD_TILE, SHRINE_TILE, TOWER_TILE, CAMP_TILE, FARM_TILE}
BUILDABLE = {PLAIN, FOREST, SAND}

FALLBACK_RACES = ["Elven", "Dwarven", "Orcish", "Human", "Faefolk", "Drakeborn"]
FALLBACK_DUNGEONS = ["Grimdeep", "Hollowbarrow", "Nightvault", "Ashcrypt", "Thornmaw"]
FALLBACK_STEADS = ["Greyglen", "Oakholt", "Stonefield", "Ravenroost", "Foxden", "Hillbrook"]


@dataclass
class Race:
    name: str
    trait: str
    origin_term: str = ""
    # SRD-harvest bloodline: attribute leans, a seeded skill, a boast.
    mods: dict = field(default_factory=dict)
    skill: str = ""
    blurb: str = ""


# Open-rules bloodlines (SRD 5.1, CC-BY): rotated through each world's peoples.
BLOODLINES = [
    {"mods": {"STR": 1, "CON": 1, "SPD": 1, "CHA": 1, "WIS": 1, "LUK": 1},
     "skill": "speech", "blurb": "Jacks of every trade."},
    {"mods": {"SPD": 2}, "skill": "lore", "blurb": "Keen senses, longer sight."},
    {"mods": {"CON": 2}, "skill": "survival", "blurb": "Stone endures."},
    {"mods": {"LUK": 2}, "skill": "sneak", "blurb": "Small, lucky, gone."},
    {"mods": {"WIS": 2}, "skill": "arcana", "blurb": "Old minds, older tricks."},
    {"mods": {"STR": 2}, "skill": "blades", "blurb": "Built for the fray."},
    {"mods": {"CHA": 2}, "skill": "speech", "blurb": "A face that opens doors."},
    {"mods": {"STR": 1, "CHA": 1}, "skill": "blades", "blurb": "Fire in the blood."},
]


@dataclass
class City:
    name: str
    x: int
    y: int
    origin_name: str = ""
    flavor: str = ""
    founded: int = 0
    founder: str = ""
    faction: str = ""


@dataclass
class Faction:
    id: str
    name: str
    race: str
    cities: list[str] = field(default_factory=list)
    at_war: list[str] = field(default_factory=list)


@dataclass
class Region:
    name: str
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass
class Character:
    name: str
    race: str
    city: str
    role: str
    hp: int
    atk: int
    origin_name: str = ""
    dialogue: str = ""


Quest = _Quest  # re-exported for backwards-compatible imports


@dataclass
class Site:
    name: str
    x: int
    y: int
    kind: str = "dungeon"  # dungeon | ruin | shrine | tower | camp | farm
    origin_name: str = ""
    lore: str = ""  # backstory line (ruins: how they fell)
    theme: str = ""  # dungeon mood: sunken | overgrown | scorched


@dataclass
class World:
    seed: int
    width: int = 150
    height: int = 85
    grid: list[str] = field(default_factory=list)  # rows of chars
    races: list[Race] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    factions: list[Faction] = field(default_factory=list)
    sites: list[Site] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    characters: list[Character] = field(default_factory=list)
    quests: list[Quest] = field(default_factory=list)
    # Rumors not yet heard: revealed by talking (E) in the giver's city.
    dormant_quests: list[Quest] = field(default_factory=list)
    completed_quests: list[str] = field(default_factory=list)
    lore_terms: list[str] = field(default_factory=list)
    # Per-seed elevation calibration, so infinite frontier strips match the
    # original continent. [deep_water_t, water_t, mountain_t]
    elev_thresholds: list[float] = field(default_factory=lambda: [0.30, 0.37, 0.75])
    # Global coords of grid[0][0]. Expanding west/north shifts these negative;
    # noise is sampled in global coords so seams never show.
    gx0: int = 0
    gy0: int = 0
    # Realm clock in minutes (Drop 2: rest, day phases). Shared by the save.
    clock: int = 0
    # Drop 3: merchant stock per city name.
    shops: dict = field(default_factory=dict)
    # Drop 4: playable classes extracted from the books.
    classes: list = field(default_factory=list)
    # Enrichment phase 1: deep history (events), placed artifacts.
    history: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    # Provenance ledger: raw book findings behind the mutated world.
    lore_people: list = field(default_factory=list)
    lore_places: list = field(default_factory=list)
    lore_groups: list = field(default_factory=list)
    # Name-safe nouns for blades, foes, and spells (never verbs).
    relic_words: list = field(default_factory=list)
    # Main tale (story plotter): beats, current page, done flag.
    plot: dict = field(default_factory=dict)
    # Enrichment 2: kills so far (new captains rise every 8).
    kill_count: int = 0
    # Game feel: cities with road-songs (caravan-reachable once walked to).
    visited: list = field(default_factory=list)
    # Elemental climate of the shelf: weights over ember/frost/storm/umbral.
    climate: dict = field(default_factory=dict)
    # Balance telemetry: session-proof counters for tuning.
    stats: dict = field(default_factory=dict)
    # Drop 4: per-site memory (boss slain, chests/tablets used).
    site_states: dict = field(default_factory=dict)
    # Drop 4: dungeon snapshot when the party is underground (else None).
    active_interior: dict | None = None
    # Faction ages: soldier losses per faction, peace clock, current age,
    # and a pending age-ending proclamation ("" = none; play goes on).
    war_tide: dict = field(default_factory=dict)
    peace_until: int = 0
    age: int = 1
    ending: str = ""
    # Book-event mining: verb-frame happenings {kind, names, snippet}.
    book_events: list = field(default_factory=list)
    # Event director: tension meter, road deck (no repeat per age), memory
    # ledger NPCs quote back, pending two-link chains, active modal event.
    tension: float = 0.0
    director_deck: list = field(default_factory=list)
    director_seen: list = field(default_factory=list)
    director_memory: list = field(default_factory=list)
    director_pending: list = field(default_factory=list)
    director_active: dict | None = None
    # Bounty board: per-city postings {city: {day, posts}}, refreshed daily.
    bounty_board: dict = field(default_factory=dict)
    board_day: int = -1
    # Book sagas: vaulted follow-up parts {saga_id: [quest dicts]}; part I
    # starts dormant, II/III release on completing the prior part.
    book_sagas: dict = field(default_factory=dict)
    # Director foreshadow (2-4 day warnings) + recent blood (tier meter).
    director_foreshadow: list = field(default_factory=list)
    recent_blood: float = 0.0
    # Housing: one room per save {city, stash, rise}.
    home: dict = field(default_factory=dict)
    # Rogue work: sown traps keyed ow:x:y or site:level:x:y.
    traps: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seed": self.seed, "width": self.width, "height": self.height,
            "grid": self.grid,
            "races": [asdict(r) for r in self.races],
            "cities": [asdict(c) for c in self.cities],
            "factions": [asdict(f) for f in self.factions],
            "sites": [asdict(s) for s in self.sites],
            "regions": [asdict(r) for r in self.regions],
            "characters": [asdict(c) for c in self.characters],
            "quests": [q.to_dict() for q in self.quests],
            "dormant_quests": [q.to_dict() for q in self.dormant_quests],
            "completed_quests": self.completed_quests,
            "lore_terms": self.lore_terms,
            "elev_thresholds": self.elev_thresholds,
            "gx0": self.gx0,
            "gy0": self.gy0,
            "clock": self.clock,
            "shops": self.shops,
            "classes": self.classes,
            "history": self.history,
            "artifacts": self.artifacts,
            "lore_people": self.lore_people,
            "lore_places": self.lore_places,
            "lore_groups": self.lore_groups,
            "relic_words": self.relic_words,
            "plot": self.plot,
            "kill_count": self.kill_count,
            "visited": self.visited,
            "climate": self.climate,
            "stats": self.stats,
            "site_states": self.site_states,
            "active_interior": self.active_interior,
            "war_tide": self.war_tide,
            "peace_until": self.peace_until,
            "age": self.age,
            "ending": self.ending,
            "book_events": self.book_events,
            "tension": self.tension,
            "director_deck": self.director_deck,
            "director_seen": self.director_seen,
            "director_memory": self.director_memory,
            "director_pending": self.director_pending,
            "director_active": self.director_active,
            "bounty_board": self.bounty_board,
            "board_day": self.board_day,
            "book_sagas": self.book_sagas,
            "director_foreshadow": self.director_foreshadow,
            "recent_blood": self.recent_blood,
            "home": self.home,
            "traps": self.traps,
        }

    @staticmethod
    def from_dict(d: dict) -> "World":
        from .quests import Quest as _Q
        quests = []
        for q in d.get("quests", []):
            try:
                quests.append(_Q.from_dict(q))
            except Exception:
                continue
        dormant = []
        for q in d.get("dormant_quests", []):
            try:
                dormant.append(_Q.from_dict(q))
            except Exception:
                continue
        sites = []
        for s in d.get("sites", []) + d.get("dungeons", []):
            try:
                site = Site(**{k: s.get(k, "") for k in
                               ("name", "x", "y", "kind", "origin_name")})
                site.lore = str(s.get("lore", ""))
                site.theme = str(s.get("theme", ""))
                sites.append(site)
            except Exception:
                continue
        regions = []
        for r in d.get("regions", []):
            try:
                regions.append(Region(name=r.get("name", "Wilds"),
                                      x0=r.get("x0", 0), y0=r.get("y0", 0),
                                      x1=r.get("x1", 0), y1=r.get("y1", 0)))
            except Exception:
                continue
        # legacy tiles: old saves lack new tiles, grid is fine as-is
        return World(
            seed=d["seed"], width=d["width"], height=d["height"], grid=d["grid"],
            races=[Race(**r) for r in d.get("races", [])],
            cities=[City(**{k: c.get(k, 0 if k in ("x", "y", "founded") else "")
                            for k in ("name", "x", "y", "origin_name",
                                      "flavor", "founded", "founder", "faction")})
                    for c in d.get("cities", [])],
            factions=[Faction(id=f.get("id", f.get("name", "")),
                              name=f.get("name", ""), race=f.get("race", ""),
                              cities=f.get("cities", []), at_war=f.get("at_war", []))
                      for f in d.get("factions", [])],
            sites=sites,
            regions=regions,
            characters=[Character(**c) for c in d.get("characters", [])],
            quests=quests,
            dormant_quests=dormant,
            completed_quests=d.get("completed_quests", []),
            lore_terms=d.get("lore_terms", []),
            elev_thresholds=d.get("elev_thresholds", [0.30, 0.37, 0.75]),
            gx0=d.get("gx0", 0),
            gy0=d.get("gy0", 0),
            clock=d.get("clock", 0),
            shops=d.get("shops", {}) if isinstance(d.get("shops"), dict) else {},
            classes=d.get("classes", []) if isinstance(d.get("classes"), list) else [],
            history=d.get("history", []) if isinstance(d.get("history"), list) else [],
            artifacts=d.get("artifacts", []) if isinstance(d.get("artifacts"), list) else [],
            lore_people=d.get("lore_people", []) if isinstance(d.get("lore_people"), list) else [],
            lore_places=d.get("lore_places", []) if isinstance(d.get("lore_places"), list) else [],
            lore_groups=d.get("lore_groups", []) if isinstance(d.get("lore_groups"), list) else [],
            relic_words=d.get("relic_words", []) if isinstance(d.get("relic_words"), list) else [],
            plot=d.get("plot", {}) if isinstance(d.get("plot"), dict) else {},
            kill_count=int(d.get("kill_count", 0)),
            visited=d.get("visited", []) if isinstance(d.get("visited"), list) else [],
            climate=d.get("climate", {}) if isinstance(d.get("climate"), dict) else {},
            stats=d.get("stats", {}) if isinstance(d.get("stats"), dict) else {},
            site_states=d.get("site_states", {}) if isinstance(d.get("site_states"), dict) else {},
            active_interior=d.get("active_interior"),
            war_tide={str(k): int(v) for k, v in d.get("war_tide", {}).items()}
                     if isinstance(d.get("war_tide"), dict) else {},
            peace_until=int(d.get("peace_until", 0)),
            age=int(d.get("age", 1)),
            ending=str(d.get("ending", "")),
            book_events=d.get("book_events", []) if isinstance(d.get("book_events"), list) else [],
            tension=float(d.get("tension", 0.0) or 0.0),
            director_deck=d.get("director_deck", []) if isinstance(d.get("director_deck"), list) else [],
            director_seen=d.get("director_seen", []) if isinstance(d.get("director_seen"), list) else [],
            director_memory=d.get("director_memory", []) if isinstance(d.get("director_memory"), list) else [],
            director_pending=d.get("director_pending", []) if isinstance(d.get("director_pending"), list) else [],
            director_active=d.get("director_active") if isinstance(d.get("director_active"), dict) else None,
            bounty_board=d.get("bounty_board", {}) if isinstance(d.get("bounty_board"), dict) else {},
            board_day=int(d.get("board_day", -1) or -1),
            book_sagas=d.get("book_sagas", {}) if isinstance(d.get("book_sagas"), dict) else {},
            director_foreshadow=d.get("director_foreshadow", []) if isinstance(d.get("director_foreshadow"), list) else [],
            recent_blood=float(d.get("recent_blood", 0) or 0.0),
            home=d.get("home", {}) if isinstance(d.get("home"), dict) else {},
            traps=d.get("traps", {}) if isinstance(d.get("traps"), dict) else {},
        )


def _hash2(ix: int, iy: int, seed: int) -> float:
    """Deterministic 0..1 value noise lattice (pure python, no deps)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) & 0xFFFFFFFF
    h = (h * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return (h & 0xFFFF) / 0xFFFF


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def _value_noise(x: float, y: float, seed: int) -> float:
    import math
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    ux, uy = _smooth(fx), _smooth(fy)
    return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy


def _fbm(x: float, y: float, seed: int, octaves: int) -> float:
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * _value_noise(x * freq, y * freq, seed)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm if norm else 0.5


try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:  # pure-python fallback keeps the game runnable anywhere
    _np = None  # type: ignore
    _HAS_NUMPY = False


def _hash_lat(ix, iy, s: int):
    """Vectorized twin of _hash2: value for each lattice point, independent of
    array shape, so strips join seamlessly (and match across runs)."""
    U = _np.uint64
    smix = U((s + 0x9E3779B9) & 0xFFFFFFFFFFFFFFFF)
    h = (ix.astype(U) * U(374761393) + iy.astype(U) * U(668265263)
         + smix * U(1442695041)) & U(0xFFFFFFFF)
    h = (h ^ (h >> U(13))) & U(0xFFFFFFFF)
    h = (h * U(1274126177)) & U(0xFFFFFFFF)
    h = (h ^ (h >> U(16))) & U(0xFFFFFFFF)
    return (h & U(0xFFFF)).astype(_np.float64) / 65535.0


def _fbm_np(seed: int, channel: int, x0: int, y0: int, w: int, h: int,
            cell: float, octaves: int, ox: float = 0.0, oy: float = 0.0) -> list[list[float]]:
    """Vectorized value-noise fBm over GLOBAL coords (seamless across strips)."""
    assert _np is not None
    xs = (_np.arange(w, dtype=_np.float64) + x0) / cell + ox
    ys = (_np.arange(h, dtype=_np.float64) + y0) / cell + oy
    total = _np.zeros((h, w), dtype=_np.float64)
    norm = 0.0
    amp = 1.0
    for o in range(octaves):
        f = float(2 ** o)
        gx, gy = xs * f, ys * f
        # lattice window covers the coords with a 1-cell margin (works for
        # negative global coords from west/north frontier growth)
        lx0 = int(_np.floor(gx.min())) - 1
        ly0 = int(_np.floor(gy.min())) - 1
        lx1 = int(_np.ceil(gx.max())) + 1
        ly1 = int(_np.ceil(gy.max())) + 1
        jx, jy = _np.meshgrid(_np.arange(lx0, lx1 + 1), _np.arange(ly0, ly1 + 1))
        lat = _hash_lat(jx, jy, seed * 131 + channel * 101 + o)
        ix = _np.floor(gx).astype(int) - lx0
        iy = _np.floor(gy).astype(int) - ly0
        fx = gx - _np.floor(gx)
        fy = gy - _np.floor(gy)
        fx = fx * fx * (3 - 2 * fx)
        fy = fy * fy * (3 - 2 * fy)
        a = lat[iy[:, None], ix]
        b = lat[iy[:, None], ix + 1]
        c = lat[iy[:, None] + 1, ix]
        d = lat[iy[:, None] + 1, ix + 1]
        total += amp * (a + (b - a) * fx + (c - a) * fy[:, None] + (a - b - c + d) * fx * fy[:, None])
        norm += amp
        amp *= 0.5
    return (total / norm).tolist()


def _sample_fields(seed: int, x0: int, y0: int, w: int, h: int) -> tuple[list[list[float]], list[list[float]]]:
    """Elevation + moisture fields at global coords (numpy fast path, python fallback)."""
    if _HAS_NUMPY:
        elev = _fbm_np(seed, 0, x0, y0, w, h, 22.0, 4)
        moist = _fbm_np(seed, 1, x0, y0, w, h, 16.7, 3, 37.2, 11.8)
        return elev, moist
    elev = [[_fbm((x + x0) * 0.045, (y + y0) * 0.045, seed, 4)
             for x in range(w)] for y in range(h)]
    moist = [[_fbm((x + x0) * 0.06 + 37.2, (y + y0) * 0.06 + 11.8, seed + 101, 3)
              for x in range(w)] for y in range(h)]
    return elev, moist


def _classify(elev: list[list[float]], moist: list[list[float]],
              thresholds: list[float]) -> list[list[str]]:
    deep_t, water_t, mount_t = thresholds
    h, w = len(elev), len(elev[0])
    grid = [[PLAIN for _ in range(w)] for _ in range(h)]
    for y in range(h):
        erow, mrow, grow = elev[y], moist[y], grid[y]
        for x in range(w):
            e, m = erow[x], mrow[x]
            if e <= deep_t:
                grow[x] = DEEP_WATER
            elif e <= water_t:
                grow[x] = WATER
            elif e >= mount_t:
                grow[x] = MOUNTAIN
            elif e <= water_t + 0.015:
                grow[x] = SAND  # shoreline
            elif m >= 0.56:
                grow[x] = FOREST
            elif m <= 0.30 and e < water_t + 0.12:
                grow[x] = SAND  # arid lowlands
            else:
                grow[x] = PLAIN
    return grid


def _gen_terrain(rng: random.Random, w: int, h: int, seed: int) -> tuple[list[list[str]], list[list[float]], list[float]]:
    """DF-style: elevation fBm -> oceans/lakes/plains, moisture fBm ->
    forests/deserts, high elevation -> mountain ranges."""
    elev, moist = _sample_fields(seed, 0, 0, w, h)
    flat = sorted(v for row in elev for v in row)
    n = len(flat)
    thresholds = [flat[int(n * 0.10)], flat[int(n * 0.20)], flat[int(n * 0.93)]]
    grid = _classify(elev, moist, thresholds)
    _carve_rivers(grid, elev, rng, w, h)
    return grid, elev, thresholds


def gen_strip(seed: int, thresholds: list[float],
              gx0: int, gy0: int, w: int, h: int) -> list[list[str]]:
    """Generate a frontier strip at GLOBAL coords (no rivers: they stay on the
    founding continent so none dead-end at a seam)."""
    elev, moist = _sample_fields(seed, gx0, gy0, w, h)
    return _classify(elev, moist, thresholds)


def _carve_rivers(grid: list[list[str]], elev: list[list[float]],
                  rng: random.Random, w: int, h: int) -> None:
    """Rain to sea: start high, walk downhill, carve fordable rivers."""
    n_rivers = rng.randint(4, 7)
    flat_e = sorted(v for row in elev for v in row)
    high_t = flat_e[int(len(flat_e) * 0.80)]
    for _ in range(n_rivers):
        starts = [(x, y) for y in range(h) for x in range(w)
                  if elev[y][x] >= high_t and grid[y][x] == MOUNTAIN]
        if not starts:
            starts = [(x, y) for y in range(h) for x in range(w)
                      if grid[y][x] in (PLAIN, FOREST)]
        x, y = rng.choice(starts)
        for _ in range(260):
            if grid[y][x] in (WATER, DEEP_WATER, RIVER):
                break
            if grid[y][x] not in (CITY_TILE,):
                grid[y][x] = RIVER
                if rng.random() < 0.25:
                    nx, ny = x + rng.choice((-1, 1)), y
                    if 0 <= nx < w and grid[ny][nx] in BUILDABLE:
                        grid[ny][nx] = RIVER
            # step to lowest-elevation neighbor (+ jitter so rivers meander)
            best, best_v = None, None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        v = elev[ny][nx] + rng.random() * 0.02
                        if best_v is None or v < best_v:
                            best, best_v = (nx, ny), v
            if best is None:
                break
            x, y = best


def _carve_road(grid: list[list[str]], ax: int, ay: int, bx: int, by: int) -> None:
    """L-shaped road between two cities; bridges rivers, skirts seas and peaks."""
    h, w = len(grid), len(grid[0])
    x, y = ax, ay
    while x != bx:
        x += 1 if bx > x else -1
        if grid[y][x] in (PLAIN, FOREST, SAND, RIVER):
            grid[y][x] = ROAD_TILE
    while y != by:
        y += 1 if by > y else -1
        if grid[y][x] in (PLAIN, FOREST, SAND, RIVER):
            grid[y][x] = ROAD_TILE


def _component(grid: list[list[str]], sx: int, sy: int) -> set[tuple[int, int]]:
    """Walkable connected component containing (sx, sy). Empty set if blocked."""
    h, w = len(grid), len(grid[0])
    if not (0 <= sx < w and 0 <= sy < h) or grid[sy][sx] not in WALKABLE:
        return set()
    seen = {(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                if grid[ny][nx] in WALKABLE:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    return seen


def _walkable_spot(grid: list[list[str]], rng: random.Random,
                   allowed: set[tuple[int, int]] | None = None) -> tuple[int, int]:
    h, w = len(grid), len(grid[0])
    for _ in range(800):
        x, y = rng.randrange(w), rng.randrange(h)
        if grid[y][x] in BUILDABLE and (allowed is None or (x, y) in allowed):
            return x, y
    if allowed:
        for x, y in allowed:
            if grid[y][x] in BUILDABLE:
                return x, y
    return w // 2, h // 2


REGION_ADJ = ["Ashen", "Verdant", "Howling", "Ember", "Thorned", "Misty",
              "Golden", "Grim", "Silent", "Sunless", "Hollow", "Crimson"]
REGION_NOUN = ["Expanse", "Reaches", "Marches", "Vale", "Wastes", "Wilds",
               "Fells", "Moors", "Steppe", "Barrens"]

# Class words hunted in the books (case-insensitive). Each maps to one of six
# starting packages, so a necromancer-heavy shelf yields necromancers.
CLASS_TEMPLATES = {
    "warrior": {"mods": {"STR": 2, "CON": 1}, "skills": {"blades": 15},
                "gear": ["weapon", "armor"], "spells": [],
                "desc": "Steel answers every question."},
    "mage": {"mods": {"WIS": 2, "CHA": 1}, "skills": {"lore": 15},
             "gear": ["amulet", "ring"], "spells": ["bolt", "mend"],
             "desc": "The books taught them fire."},
    "ranger": {"mods": {"SPD": 2, "CON": 1}, "skills": {"survival": 15},
               "gear": ["weapon", "armor"], "spells": [],
               "desc": "At home nowhere and everywhere."},
    "rogue": {"mods": {"LUK": 2, "SPD": 1}, "skills": {"blades": 5, "survival": 10},
              "gear": ["weapon", "ring"], "spells": ["blink"],
              "desc": "Gone before the echo."},
    "cleric": {"mods": {"CON": 2, "WIS": 1}, "skills": {"speech": 10, "lore": 5},
               "gear": ["armor", "amulet"], "spells": ["mend"],
               "desc": "Someone has to bury the heroes."},
    "bard": {"mods": {"CHA": 2, "LUK": 1}, "skills": {"speech": 15},
             "gear": ["ring", "amulet"], "spells": [],
             "desc": "They will sing of this. Exaggerating."},
    "sorcerer": {"mods": {"WIS": 2, "LUK": 1}, "skills": {"lore": 10, "arcana": 10},
                 "gear": ["ring", "amulet"], "spells": ["spark", "bolt"],
                 "desc": "Power they did not study for."},
    "paladin": {"mods": {"CON": 2, "CHA": 1}, "skills": {"speech": 10, "medicine": 10},
                "gear": ["weapon", "armor"], "spells": ["mend", "smite"],
                "desc": "An oath with a sword behind it."},
}
CLASSICS = ["warrior", "mage", "ranger", "rogue", "cleric", "bard", "sorcerer", "paladin"]
# Derivatives are not paint: each word bends its template (extra attrs/skills,
# a styled starting blade, sometimes a swapped spell) and carries its own desc.
DERIVATIVES = {
    "mage": ("Counts stars and crows-nests alike.", {}, {}, ["amulet", "ring"], ["bolt", "mend"]),
    "wizard": ("Bearded, robed, always right.", {"WIS": 1}, {"arcana": 5}, ["amulet", "ring"], ["bolt", "mend"]),
    "sorcerer": ("Power they did not study for.", {"LUK": 1}, {"arcana": 5}, ["ring", "amulet"], ["spark", "bolt"]),
    "witch": ("Knows which herbs bite back.", {"WIS": 1}, {"medicine": 5}, ["ring", "amulet"], ["frostbite", "mend"]),
    "warlock": ("Signed in something wet.", {"CHA": 1}, {"arcana": 5}, ["weapon:swift", "ring"], ["smite", "spark"]),
    "necromancer": ("Polite to the dead. Rude to the living.", {"WIS": 1}, {"lore": 5}, ["amulet", "ring"], ["fury", "mend"]),
    "priest": ("Buries heroes, bills gods.", {"CHA": 1}, {"speech": 5}, ["armor", "amulet"], ["mend"]),
    "cleric": ("Someone has to bury the heroes.", {"CON": 1}, {"medicine": 5}, ["armor", "amulet"], ["mend", "turn"]),
    "paladin": ("An oath with a sword behind it.", {"CHA": 1}, {"medicine": 5}, ["weapon:sword", "armor"], ["mend", "smite"]),
    "monk": ("Fists first, questions never.", {"SPD": 1}, {"survival": 5}, ["armor", "ring"], ["mend"]),
    "shaman": ("Drinks with spirits. Usually wins.", {"WIS": 1}, {"survival": 5}, ["amulet", "ring"], ["mend", "fury"]),
    "druid": ("Married the treeline.", {"CON": 1}, {"survival": 5}, ["ring", "amulet"], ["charm", "mend"]),
    "knight": ("Oiled armor, oiled manners.", {"CON": 1}, {"speech": 5}, ["weapon:sword", "armor"], []),
    "warrior": ("Steel answers every question.", {"STR": 1}, {}, ["weapon", "armor"], []),
    "barbarian": ("Solves doors by removing walls.", {"STR": 2}, {}, ["weapon:heavy", "armor"], []),
    "captain": ("Everyone's marching orders.", {"CHA": 1}, {"speech": 5}, ["weapon:sword", "armor"], []),
    "guard": ("Has seen it all. Twice on Sundays.", {"CON": 1}, {"survival": 5}, ["weapon:spear", "armor"], []),
    "soldier": ("A pike, a pay chest, a prayer.", {}, {"survival": 5}, ["weapon:spear", "armor"], []),
    "fighter": ("Punches up for a living.", {"STR": 1}, {"blades": 5}, ["weapon", "armor"], []),
    "ranger": ("At home nowhere and everywhere.", {"SPD": 1}, {}, ["bow", "armor"], []),
    "hunter": ("Counts teeth. Mostly not their own.", {"SPD": 1}, {"salvage": 5}, ["bow", "armor"], []),
    "archer": ("Kills you from the next parish.", {"SPD": 1}, {"blades": 5}, ["bow", "ring"], []),
    "scout": ("First in, first out.", {"SPD": 1, "LUK": 1}, {}, ["weapon:swift", "armor"], ["sight"]),
    "rogue": ("Gone before the echo.", {"LUK": 1}, {"sneak": 5}, ["weapon:swift", "ring"], ["blink"]),
    "thief": ("Your purse was always theirs.", {"LUK": 2}, {}, ["weapon:swift", "ring"], ["blink"]),
    "assassin": ("A whisper with a knife.", {"LUK": 1, "SPD": 1}, {}, ["weapon:swift", "ring"], ["blink"]),
    "bard": ("They will sing of this. Exaggerating.", {"CHA": 1}, {}, ["ring", "amulet"], ["charm"]),
    "minstrel": ("Softer songs, sharper ears.", {"CHA": 1}, {"lore": 5}, ["ring", "amulet"], []),
    "artificer": ("Half mage, half locksmith.", {"WIS": 1}, {"salvage": 5}, ["ring", "amulet"], ["spark", "mend"]),
}
CLASS_WORDS = {
    "mage": "mage", "wizard": "mage", "sorcerer": "mage", "witch": "mage",
    "warlock": "mage", "necromancer": "mage",
    "priest": "cleric", "cleric": "cleric", "paladin": "cleric",
    "monk": "cleric", "shaman": "cleric", "druid": "ranger",
    "knight": "warrior", "warrior": "warrior", "barbarian": "warrior",
    "captain": "warrior", "guard": "warrior", "soldier": "warrior",
    "ranger": "ranger", "hunter": "ranger", "archer": "ranger", "scout": "ranger",
    "rogue": "rogue", "thief": "rogue", "assassin": "rogue",
    "bard": "bard", "minstrel": "bard",
    "barbarian": "warrior", "fighter": "warrior",
    "sorcerer": "sorcerer", "warlock": "sorcerer",
    "paladin": "paladin", "artificer": "mage",
}


def extract_classes(corpus_text: str) -> list[dict]:
    """Book-first classes: the shelf's own words, filled to six with classics."""
    import re
    from collections import Counter
    low = corpus_text.lower()
    hits: dict[str, Counter] = {}
    for word, tpl in CLASS_WORDS.items():
        n = len(re.findall(rf"\b{re.escape(word)}s?\b", low))
        if n:
            hits.setdefault(tpl, Counter())[word] += n
    classes = []
    per_tpl: dict[str, int] = {}
    for tpl, words in sorted(hits.items(), key=lambda kv: -sum(kv[1].values())):
        for word, _ in words.most_common(4):
            if len(classes) >= 12 or per_tpl.get(tpl, 0) >= 4:
                break
            name = word.capitalize()
            base = dict(CLASS_TEMPLATES[tpl])
            desc, dm, ds, gear, spells = DERIVATIVES.get(word, (base["desc"], {}, {}, base["gear"], base["spells"]))
            mods = dict(base["mods"])
            for k, v in dm.items():
                mods[k] = mods.get(k, 0) + v
            skills = dict(base["skills"])
            for k, v in ds.items():
                skills[k] = skills.get(k, 0) + v
            classes.append({"id": name.lower(), "name": name, "template": tpl, "book": True,
                            "mods": mods, "skills": skills, "gear": gear, "spells": spells,
                            "desc": desc})
            per_tpl[tpl] = per_tpl.get(tpl, 0) + 1
        if len(classes) >= 12:
            break
    for tpl in CLASSICS:
        if len(classes) >= max(8, min(12, len(classes) + 2)):
            break
        if tpl not in {c["template"] for c in classes}:
            base = dict(CLASS_TEMPLATES[tpl])
            desc, dm, ds, gear, spells = DERIVATIVES.get(tpl, (base["desc"], {}, {}, base["gear"], base["spells"]))
            mods = dict(base["mods"])
            for k, v in dm.items():
                mods[k] = mods.get(k, 0) + v
            skills = dict(base["skills"])
            for k, v in ds.items():
                skills[k] = skills.get(k, 0) + v
            classes.append({"id": tpl, "name": tpl.capitalize(), "template": tpl, "book": False,
                            "mods": mods, "skills": skills, "gear": gear, "spells": spells,
                            "desc": desc})
    return classes


ELEMENT_WORDS = {
    "ember": ["ember", "fire", "flame", "ash", "burn", "furnace", "cinder", "magma",
              "forge", "pyre", "inferno", "scorch"],
    "frost": ["frost", "ice", "winter", "snow", "frozen", "glacier", "blizzard", "cold"],
    "storm": ["storm", "sea", "thunder", "lightning", "tempest", "wind", "rain", "ocean"],
    "umbral": ["shadow", "death", "night", "dark", "necro", "blood", "void", "crypt"],
}
OPPOSITE = {"ember": "frost", "frost": "ember", "storm": "umbral", "umbral": "storm"}


def elemental_climate(corpus_text: str) -> dict:
    """The shelf's elemental weather: what the books burn with, the realm burns with."""
    import re
    low = corpus_text.lower()
    weights = {}
    for el, words in ELEMENT_WORDS.items():
        weights[el] = sum(len(re.findall(rf"\b{re.escape(w)}\w*\b", low)) for w in words)
    total = sum(weights.values()) or 1
    return {el: 0.1 + 0.9 * (n / total) for el, n in weights.items()}


def roll_climate(rng: random.Random, climate: dict) -> str:
    els = sorted(climate)
    r = rng.random() * sum(climate[e] for e in els)
    for e in els:
        r -= climate[e]
        if r <= 0:
            return e
    return els[-1]


def _name_regions(rng: random.Random, w: int, h: int,
                  terms: list[str]) -> list[Region]:
    """DF-style: the map is divided into named tracts quoted in banners/quests."""
    adjs = [t.capitalize() for t in terms[:6]] + REGION_ADJ
    rng.shuffle(adjs)
    nouns = list(REGION_NOUN)
    rng.shuffle(nouns)
    regions = []
    cols, rows = 3, 2
    i = 0
    for cy in range(rows):
        for cx in range(cols):
            name = f"The {adjs[i % len(adjs)]} {nouns[i % len(nouns)]}"
            i += 1
            regions.append(Region(name=name,
                                  x0=cx * w // cols, y0=cy * h // rows,
                                  x1=(cx + 1) * w // cols, y1=(cy + 1) * h // rows))
    return regions


def _scale_count(rng: random.Random, lo: int, hi: int, area: int,
                   floor: int) -> int:
    """Content density scales with map area (base: 150x85 continent)."""
    return max(floor, round(rng.uniform(lo, hi) * area / (150 * 85)))


FACTION_TITLES = ["Compact", "Dominion", "Horde", "Court", "Clan", "Kingdom"]


def assign_factions(rng: random.Random, races: list[Race],
                    cities: list[City]) -> list[Faction]:
    """Split races into 2-4 powers, deal cities to the nearest capital, and
    start at least one war (symmetric)."""
    if not races or not cities:
        return []
    n = max(2, min(4, len(races)))
    titles = list(FACTION_TITLES)
    rng.shuffle(titles)
    factions = [Faction(id=f"fac{i}", name=f"{races[i].name} {titles[i % len(titles)]}",
                        race=races[i].name) for i in range(n)]
    capitals = rng.sample(cities, min(n, len(cities)))
    for i, cap in enumerate(capitals):
        factions[i % n].cities.append(cap.name)
        cap.faction = factions[i % n].id
    for c in cities:
        if c.faction:
            continue
        best = min(capitals, key=lambda k: abs(k.x - c.x) + abs(k.y - c.y))
        fid = next(f.id for f in factions if best.name in f.cities)
        c.faction = fid
        next(f for f in factions if f.id == fid).cities.append(c.name)
    # wars: random pairs, at least one
    pairs = [(a, b) for i, a in enumerate(factions) for b in factions[i + 1:]]
    rng.shuffle(pairs)
    started = False
    for a, b in pairs:
        if not started or rng.random() < 0.3:
            a.at_war.append(b.id)
            b.at_war.append(a.id)
            started = True
    return factions


def faction_name(world: "World", fid: str) -> str:
    for f in world.factions:
        if f.id == fid:
            return f.name
    return fid or "the wilds"


def generate_world(corpus_text: str, seed: int | None = None,
                   width: int = 300, height: int = 170) -> World:
    seed = seed if seed is not None else random.randrange(1_000_000)
    rng = random.Random(seed)
    lore: Lore = extract_entities(corpus_text) if corpus_text.strip() else Lore()

    grid, _elev, thresholds = _gen_terrain(rng, width, height, seed)
    regions = _name_regions(rng, width, height, lore.terms[:20])

    # Races: mutate extracted groups; fall back to classics. Don't glue
    # "folk" onto map names -- it produced Thornwallfolk-style mush.
    race_base = list(lore.groups)
    if len(race_base) < 3:
        race_base += [t.capitalize() for t in lore.terms[:3]
                      if t.capitalize() not in race_base]
    race_names = unique_names(race_base, min(8, max(5, len(race_base) + 2)),
                              rng, FALLBACK_RACES)
    traits = ["hardy", "arcane", "nomadic", "seafaring", "mountain-born", "forest-wise",
              "rune-keepers", "night-eyed", "storm-touched", "ember-blooded"]
    rng.shuffle(traits)
    races = [Race(name=n, trait=traits[i % len(traits)],
                  origin_term=lore.groups[i] if i < len(lore.groups) else "")
             for i, n in enumerate(race_names)]
    blood = list(BLOODLINES)
    rng.shuffle(blood)
    for i, r in enumerate(races):
        b = blood[i % len(blood)]
        r.mods = dict(b["mods"])
        r.skill = b["skill"]
        r.blurb = b["blurb"]

    # Cities: density scales with map area, all on the main landmass so
    # every town is reachable on foot from every other.
    mainland = _component(grid, width // 2, height // 2)
    if not mainland:
        mainland = _component(grid, *_walkable_spot(grid, rng))
    area = width * height
    n_cities = _scale_count(rng, 10, 15, area, 6)
    city_names = unique_names(lore.places, n_cities, rng, FALLBACK_CITY_STEMS)
    cities: list[City] = []
    for i, cn in enumerate(city_names):
        x, y = _walkable_spot(grid, rng, mainland)
        grid[y][x] = CITY_TILE
        origin = lore.places[i] if i < len(lore.places) else ""
        flavor = ""
        if lore.flavor_lines:
            flavor = rng.choice(lore.flavor_lines)
        cities.append(City(name=cn, x=x, y=y, origin_name=origin, flavor=flavor))
    # roads link cities in a chain so the big map stays traversable
    for a, b in zip(cities, cities[1:]):
        _carve_road(grid, a.x, a.y, b.x, b.y)

    # Sites: dungeons (D), ruins (#), shrines (*) — density scales too
    site_names = unique_names(lore.places[len(cities):] or lore.places, 10,
                              rng, FALLBACK_DUNGEONS)
    sites: list[Site] = []
    site_tiles = [DUNGEON_TILE, RUIN_TILE, SHRINE_TILE, DUNGEON_TILE, SHRINE_TILE]
    for i in range(_scale_count(rng, 7, 10, area, 4)):
        base = site_names[i % len(site_names)] if site_names else f"Grimdeep{i}"
        kind = "dungeon" if site_tiles[i % len(site_tiles)] == DUNGEON_TILE else (
            "ruin" if site_tiles[i % len(site_tiles)] == RUIN_TILE else "shrine")
        theme = ""
        if kind == "dungeon" and rng.random() < 0.35:
            theme = rng.choice(["sunken", "overgrown", "scorched"])
        label = {"dungeon": f"{base} Deep", "ruin": f"Ruins of {base}",
                 "shrine": f"Shrine of {base}"}[kind]
        if theme == "sunken":
            label = f"Sunken {label}"
        elif theme == "overgrown":
            label = f"Overgrown {label}"
        elif theme == "scorched":
            label = f"Scorched {label}"
        x, y = _walkable_spot(grid, rng, mainland)
        grid[y][x] = site_tiles[i % len(site_tiles)]
        origin = lore.places[(len(cities) + i) % len(lore.places)] if lore.places else ""
        sites.append(Site(name=label, x=x, y=y, kind=kind, origin_name=origin, theme=theme))

    # Steadings: watchtowers (!), bandit camps (X), farms (v)
    stead_base = [t.capitalize() for t in lore.terms[6:14]] or ["Grey", "Oak"]
    stead_names = unique_names(stead_base, 6, rng, FALLBACK_STEADS)
    stead_kinds = [("tower", TOWER_TILE, " Watch"), ("camp", CAMP_TILE, " Camp"),
                   ("farm", FARM_TILE, " Farm")]
    rng.shuffle(stead_kinds)
    for i in range(_scale_count(rng, 2, 4, area, 2)):
        kind, tile, suffix = stead_kinds[i % len(stead_kinds)]
        base = stead_names[i % len(stead_names)] if stead_names else f"Grey{i}"
        x, y = _walkable_spot(grid, rng, mainland)
        grid[y][x] = tile
        sites.append(Site(name=f"{base}{suffix}", x=x, y=y, kind=kind,
                          origin_name=stead_base[i % len(stead_base)] if stead_base else ""))

    # Characters: mouths scale with the map
    n_chars = _scale_count(rng, 22, 32, area, 12)
    char_names = unique_names(lore.people, n_chars, rng, FALLBACK_NAME_STEMS)
    roles = ["merchant", "guard", "healer", "scout", "elder", "bandit",
             "bard", "blacksmith", "mage", "ranger"]
    characters: list[Character] = []
    for i, cn in enumerate(char_names):
        race = rng.choice(races).name if races else "Human"
        city = rng.choice(cities).name if cities else "Wilderland"
        role = roles[i % len(roles)] if i < len(roles) else rng.choice(roles)
        hostile = role == "bandit"
        hp = rng.randint(25, 45) if hostile else rng.randint(15, 30)
        atk = rng.randint(5, 10) if hostile else rng.randint(2, 5)
        origin = lore.people[i] if i < len(lore.people) else ""
        dlg = rng.choice(lore.flavor_lines) if lore.flavor_lines else ""
        characters.append(Character(name=cn, race=race, city=city, role=role,
                                    hp=hp, atk=atk, origin_name=origin, dialogue=dlg))

    # Founding years + founders: cheap DF-style history for banners/rumors
    founder_pool = [c.name for c in characters] or list(lore.people) or ["the First"]
    for c in cities:
        c.founded = rng.randint(100, 900)
        c.founder = rng.choice(founder_pool)

    # Factions: powers, territory, and at least one war
    factions = assign_factions(rng, races, cities)
    city_faction = {c.name: c.faction for c in cities}
    climate = elemental_climate(corpus_text)

    # Drop 3: every city market stocks lore-named gear
    from .items import gen_shop_stock
    shops = {c.name: gen_shop_stock(lore.relic_words or lore.terms, rng, rng.randint(4, 6), tier=1,
                                    climate=climate)
             for c in cities}

    # Drop 4: playable classes are the shelf's own words (mage? captain?),
    # filled to six with classics.
    classes = extract_classes(corpus_text)
    # Quests: most start as unheard rumors (dormant) revealed via givers;
    # two starters (a delivery + something bloody) are known from the outset.
    built = build_quests(characters, cities, sites, (lore.relic_words + lore.terms)[:20],
                         lore.flavor_lines, rng, exclude=set(),
                         count=max(8, round(14 * area / (150 * 85))),
                         factions=factions, city_faction=city_faction, grid=grid)
    quests: list = []
    dormant: list = []
    for q in built:
        if len(quests) < 2 and q.kind not in {s.kind for s in quests}:
            quests.append(q)
        else:
            dormant.append(q)

    str_grid = ["".join(row) for row in grid]
    world = World(seed=seed, width=width, height=height, grid=str_grid,
                  races=races, cities=cities, factions=factions, sites=sites,
                  regions=regions,
                  characters=characters,
                  quests=quests, dormant_quests=dormant, completed_quests=[],
                  lore_terms=lore.terms[:20],
                  elev_thresholds=thresholds, shops=shops, classes=classes,
                   climate=climate,
                  lore_people=lore.people[:40], lore_places=lore.places[:24],
                  lore_groups=lore.groups[:10], relic_words=lore.relic_words,
                  book_events=list(getattr(lore, "book_events", []) or []))
    # book-mined happenings seed gated sagas + single rumors (high book share:
    # top pool of 20 -> 8 sagas x 3 parts + 12 singles). Part I dormant, II/III
    # vaulted in world.book_sagas. Givers/targets reuse mined names on match.
    world.book_sagas = {}
    try:
        from .quests import Quest as _Q
        beats = {"battle": ["explore", "bounty", "deliver"],
                 "siege": ["deliver", "hunt", "explore"],
                 "exodus": ["escort", "deliver", "explore"],
                 "union": ["deliver", "escort", "tribute"],
                 "betrayal": ["deliver", "bounty", "hunt"],
                 "storm": ["explore", "deliver", "tribute"],
                 "plague": ["deliver", "explore", "tribute"],
                 "voyage": ["explore", "escort", "deliver"]}
        char_by_name = {c.name: c for c in characters}
        city_by_name = {c.name: c for c in cities}
        site_by_name = {s.name: s for s in sites}
        non_bandits = [c for c in characters if c.role != "bandit"] or characters
        bandits = [c.name for c in characters if c.role == "bandit"] or ["the Red Hood"]
        seen_ids = {q.id for q in list(quests) + list(dormant)}
        pool = list(world.book_events)[:20]

        def _mk_part(saga: str, kind: str, names: list, snip: str, giver: str,
                      giver_home: str, title_name: str, pk: str, pi: int, num: str) -> object:
            qid = f"{saga}-{pi + 1}" if saga else f"book-single-{kind}-{pi}"
            head = f"Saga of {title_name} {num}" if saga else f"Echo of {title_name} ({kind})"
            say = f"Books tell: '{snip}'" if snip else f"Old {kind} stirs."
            suf = f"({num} of III)" if saga else "(book echo)"
            if pk == "bounty":
                tgt = next((n for n in names if n in bandits), bandits[pi % len(bandits)])
                lair = ""
                dens = [s for s in sites if s.kind == "dungeon"]
                if dens:
                    lair = dens[pi % len(dens)].name
                return _Q(id=qid, kind="bounty", title=f"{head}: Bounty {tgt}",
                          giver=giver, target_enemy=tgt, target_site=lair,
                          flavor=f"{say} {giver} wants {tgt} answered {suf}.",
                          reward_gold=18, reward_xp=40, saga=saga)
            if pk == "explore":
                tgt = next((n for n in names if n in site_by_name), "")
                if not tgt and sites:
                    tgt = sites[pi % len(sites)].name
                return _Q(id=qid, kind="explore", title=f"{head}: Walk {tgt or 'the wilds'}",
                          giver=giver, target_site=tgt,
                          flavor=f"{say} Stand where it happened {suf}.",
                          reward_gold=12, reward_xp=35, saga=saga)
            if pk == "escort":
                comp = next((n for n in names if n in char_by_name and n != giver), giver)
                dests = [c.name for c in cities if c.name != giver_home]
                tgt = dests[pi % len(dests)] if dests else giver_home
                return _Q(id=qid, kind="escort", title=f"{head}: Guide {comp}",
                          giver=giver, target_city=tgt, companion=comp,
                          flavor=f"{say} See {comp} safe to {tgt} {suf}.",
                          reward_gold=16, reward_xp=35, saga=saga)
            if pk == "hunt":
                foes = [f.name for f in factions] or ["raiders"]
                foe = foes[pi % len(foes)]
                return _Q(id=qid, kind="hunt", title=f"{head}: Cull {foe}",
                          giver=giver, target_enemy=foe, amount=3,
                          flavor=f"{say} Thin their {foe} {suf}.",
                          reward_gold=16, reward_xp=40, saga=saga)
            if pk == "tribute":
                dests = [c.name for c in cities if c.name != giver_home]
                tgt = dests[pi % len(dests)] if dests else giver_home
                return _Q(id=qid, kind="tribute", title=f"{head}: Tribute for {tgt}",
                          giver=giver, target_city=tgt, amount=40,
                          flavor=f"{say} Lay 40g at {tgt} {suf}.",
                          reward_gold=8, reward_xp=35, saga=saga)
            dests = [c.name for c in cities if c.name != giver_home]
            tgt = next((n for n in names if n in city_by_name and n != giver_home), "")
            if not tgt and dests:
                tgt = dests[pi % len(dests)]
            return _Q(id=qid, kind="deliver", title=f"{head}: Word for {tgt or giver_home}",
                      giver=giver, target_city=tgt or giver_home,
                      flavor=f"{say} Carry word to {tgt or giver_home} {suf}.",
                      reward_gold=12, reward_xp=30, saga=saga)

        # per-world variety: sample 8 saga seeds from the top-20 pool
        idxs = list(range(len(pool)))
        rng.shuffle(idxs)
        saga_idxs = idxs[:8]
        single_idxs = [x for x in idxs[8:8 + 12] if x < len(pool)]
        for si, bi in enumerate(saga_idxs):
            b = pool[bi]
            kind = str(b.get("kind", "tale")) or "tale"
            names = [str(x) for x in b.get("names", []) if x]
            snip = str(b.get("snippet", ""))[:130]
            if not cities or not characters:
                break
            saga = f"saga-{si}-{kind}"
            giver = next((n for n in names if n in char_by_name), "")
            if not giver:
                giver = non_bandits[rng.randrange(len(non_bandits))].name
            giver_home = char_by_name.get(giver).city if giver in char_by_name else cities[0].name
            title_name = names[0] if names else kind
            parts = []
            for pi, pk in enumerate(beats.get(kind, ["deliver", "bounty", "explore"])):
                num = ("I", "II", "III")[pi]
                q = _mk_part(saga, kind, names, snip, giver, giver_home, title_name, pk, si * 3 + pi, num)
                if q.id in seen_ids:
                    continue
                seen_ids.add(q.id)
                parts.append(q)
            if parts:
                dormant.append(parts[0])
                if len(parts) > 1:
                    world.book_sagas[saga] = [q.to_dict() for q in parts[1:]]
        for k, bi in enumerate(single_idxs):
            b = pool[bi]
            kind = str(b.get("kind", "tale")) or "tale"
            names = [str(x) for x in b.get("names", []) if x]
            snip = str(b.get("snippet", ""))[:130]
            giver = next((n for n in names if n in char_by_name), "")
            if not giver:
                giver = non_bandits[rng.randrange(len(non_bandits))].name
            giver_home = char_by_name.get(giver).city if giver in char_by_name else cities[0].name
            title_name = names[0] if names else kind
            pk = beats.get(kind, ["deliver"])[0]
            q = _mk_part("", kind, names, snip, giver, giver_home, title_name, pk, 100 + k, "")
            q.id = f"book-single-{kind}-{k}"
            if q.id in seen_ids:
                continue
            seen_ids.add(q.id)
            dormant.append(q)
    except Exception:
        pass
    from .history import simulate
    simulate(world, rng)
    from .plot import ensure_plot
    ensure_plot(world, rng)
    return world


# ---------------- infinite frontier ----------------
# The founding continent is finite; walking to its edge grows the grid with
# noise sampled at GLOBAL coords, so new land joins seamlessly. West/north
# growth prepends rows/cols (callers shift entity coords by the returned dx/dy).

FRONTIER_STRIP = 32


def _fresh_names(base: list[str], existing: set[str], count: int,
                 rng: random.Random, fallback: list[str]) -> list[str]:
    out: list[str] = []
    guard = 0
    while len(out) < count and guard < count * 60:
        guard += 1
        for cand in unique_names(base, count - len(out), rng, fallback):
            if cand.lower() not in existing and cand not in out:
                existing.add(cand.lower())
                out.append(cand)
    return out


def _new_region_name(world: "World", rng: random.Random) -> str:
    used = {r.name for r in world.regions}
    adjs = [t.capitalize() for t in world.lore_terms[:8]] + REGION_ADJ
    for _ in range(40):
        name = f"The {rng.choice(adjs)} {rng.choice(REGION_NOUN)}"
        if name not in used:
            return name
    n = sum(1 for r in world.regions if r.name.startswith("The Far")) + 2
    return f"The Far {rng.choice(REGION_NOUN)} {n}"


def grow(world: "World", side: str, size: int = FRONTIER_STRIP) -> tuple[int, int]:
    """Grow the grid on one side. Returns (dx, dy) shift to apply to entities."""
    gw = world.gx0
    gy = world.gy0
    if side == "right":
        strip = gen_strip(world.seed, world.elev_thresholds, gw + world.width, gy,
                          size, world.height)
        rows = [list(r) for r in world.grid]
        for y, srow in enumerate(strip):
            rows[y].extend(srow)
        world.width += size
        rect = (world.width - size, 0, size, world.height)
        dx, dy = 0, 0
    elif side == "left":
        strip = gen_strip(world.seed, world.elev_thresholds, gw - size, gy,
                          size, world.height)
        rows = [srow + list(r) for srow, r in zip(strip, world.grid)]
        world.width += size
        world.gx0 -= size
        rect = (0, 0, size, world.height)
        dx, dy = size, 0
    elif side == "bottom":
        strip = gen_strip(world.seed, world.elev_thresholds, gw, gy + world.height,
                          world.width, size)
        rows = [list(r) for r in world.grid] + strip
        world.height += size
        rect = (0, world.height - size, world.width, size)
        dx, dy = 0, 0
    else:  # top
        strip = gen_strip(world.seed, world.elev_thresholds, gw, gy - size,
                          world.width, size)
        rows = strip + [list(r) for r in world.grid]
        world.height += size
        world.gy0 -= size
        rect = (0, 0, world.width, size)
        dx, dy = 0, size
    world.grid = ["".join(r) for r in rows]
    # Land prepended west/north: every pinned location shifts with the grid.
    if dx or dy:
        for c in world.cities:
            c.x += dx
            c.y += dy
        for s in world.sites:
            s.x += dx
            s.y += dy
        for r in world.regions:
            r.x0 += dx
            r.x1 += dx
            r.y0 += dy
            r.y1 += dy
    world._frontier_rect = rect  # type: ignore[attr-defined]
    return dx, dy


def settle_frontier(world: "World", rng: random.Random,
                      anchor: tuple[int, int] | None = None) -> dict:
    """Populate the freshly grown strip: region, cities, sites, roads, quests.

    Reads world._frontier_rect (local coords) set by grow(). New towns/sites go
    only on land reachable from `anchor` (the player), so the frontier is never
    a walled-off island. Returns summary.
    """
    rect = getattr(world, "_frontier_rect", None)
    if rect is None:
        return {"cities": [], "sites": [], "region": None, "quests": []}
    delattr(world, "_frontier_rect")
    rx, ry, rw, rh = rect
    grid = [list(r) for r in world.grid]
    if anchor is None:
        anchor = (world.cities[0].x, world.cities[0].y) if world.cities else (rx, ry)
    reachable = _component(grid, *anchor)

    def free_spot() -> tuple[int, int] | None:
        for _ in range(300):
            x = rng.randrange(rx, rx + rw)
            y = rng.randrange(ry, ry + rh)
            if grid[y][x] in BUILDABLE and (x, y) in reachable:
                return x, y
        return None

    existing = {c.name.lower() for c in world.cities} | {s.name.lower() for s in world.sites}
    region = Region(name=_new_region_name(world, rng), x0=rx, y0=ry, x1=rx + rw, y1=ry + rh)
    world.regions.append(region)

    base = [t.capitalize() for t in world.lore_terms[:10]] or ["Ald", "Bren"]
    new_cities: list[City] = []
    for cn in _fresh_names(base, existing, rng.randint(1, 2), rng, FALLBACK_CITY_STEMS):
        spot = free_spot()
        if not spot:
            break
        x, y = spot
        grid[y][x] = CITY_TILE
        founder_pool = [c.name for c in world.characters] or ["the First"]
        new_cities.append(City(name=cn, x=x, y=y, founded=rng.randint(100, 900),
                               founder=rng.choice(founder_pool)))
    # link each frontier town to its nearest elder city
    for nc in new_cities:
        best, best_d = None, None
        for c in world.cities:
            d = abs(c.x - nc.x) + abs(c.y - nc.y)
            if best_d is None or d < best_d:
                best, best_d = c, d
        if best:
            _carve_road(grid, best.x, best.y, nc.x, nc.y)
    world.cities.extend(new_cities)
    # frontier towns swear to the nearest existing power (if any exist)
    olds = [c for c in world.cities if c.faction and c not in new_cities]
    fmap = {f.id: f for f in world.factions}
    for nc in new_cities:
        if not olds or nc.faction:
            continue
        best = min(olds, key=lambda c: abs(c.x - nc.x) + abs(c.y - nc.y))
        nc.faction = best.faction
        if nc.name not in fmap[best.faction].cities:
            fmap[best.faction].cities.append(nc.name)
    # frontier foundings enter the annals as present-day events
    for nc in new_cities:
        nc.founded = 900
        world.history.append({"year": 900, "kind": "founding",
                              "text": f"{nc.name} raised by {nc.founder or 'settlers'}.",
                              "place": nc.name,
                              "people": [nc.founder] if nc.founder else []})
    world.history.sort(key=lambda e: (e.get("year", 0), e.get("kind", "")))

    site_tiles = [DUNGEON_TILE, RUIN_TILE, SHRINE_TILE]
    new_sites: list[Site] = []
    for base_name in _fresh_names(base, existing, rng.randint(1, 2), rng, FALLBACK_DUNGEONS):
        spot = free_spot()
        if not spot:
            break
        x, y = spot
        tile = site_tiles[len(new_sites) % len(site_tiles)]
        grid[y][x] = tile
        kind = {"D": "dungeon", "#": "ruin", "*": "shrine"}[tile]
        label = {"dungeon": f"{base_name} Deep", "ruin": f"Ruins of {base_name}",
                 "shrine": f"Shrine of {base_name}"}[kind]
        theme = ""
        if kind == "dungeon" and rng.random() < 0.35:
            theme = rng.choice(["sunken", "overgrown", "scorched"])
            label = {"sunken": f"Sunken {label}", "overgrown": f"Overgrown {label}",
                     "scorched": f"Scorched {label}"}[theme]
        new_sites.append(Site(name=label, x=x, y=y, kind=kind, theme=theme))
    # frontier steadings: a watch, a camp, or a farm where the land allows
    if rng.random() < 0.7:
        kind, tile, suffix = rng.choice([("tower", TOWER_TILE, " Watch"),
                                         ("camp", CAMP_TILE, " Camp"),
                                         ("farm", FARM_TILE, " Farm")])
        for base_name in _fresh_names(base, existing, 1, rng, FALLBACK_STEADS):
            spot = free_spot()
            if not spot:
                break
            x, y = spot
            grid[y][x] = tile
            new_sites.append(Site(name=f"{base_name}{suffix}", x=x, y=y, kind=kind))
    world.sites.extend(new_sites)

    # settlers: frontier towns get locals, so they can hand out rumors too
    settler_roles = ["merchant", "guard", "healer", "scout", "elder", "bard"]
    for nc in new_cities:
        for sn in _fresh_names(base, existing, rng.randint(1, 2), rng, FALLBACK_NAME_STEMS):
            world.characters.append(Character(
                name=sn, race=rng.choice(world.races).name if world.races else "Human",
                city=nc.name, role=rng.choice(settler_roles),
                hp=rng.randint(15, 30), atk=rng.randint(2, 5)))
        from .items import gen_shop_stock, name_pool
        world.shops[nc.name] = gen_shop_stock(name_pool(world), rng, rng.randint(3, 5), tier=2,
                                              climate=world.climate)
    world.grid = ["".join(r) for r in grid]

    # fresh rumors for the new land: unheard until someone is asked in town
    known = set(world.completed_quests) | {q.id for q in world.quests} | \
        {q.id for q in world.dormant_quests}
    fresh = build_quests(world.characters, world.cities, world.sites,
                         world.lore_terms, [], rng, exclude=known, count=3,
                         factions=world.factions,
                         city_faction={c.name: c.faction for c in world.cities},
                         grid=grid)
    got = [q for q in fresh if q.id not in known]
    world.dormant_quests.extend(got)
    return {"cities": new_cities, "sites": new_sites, "region": region, "quests": got}


def provenance_rows(world: "World") -> list[tuple[str, str, str]]:
    """DATA-tab ledger: every world thing, where the books say it came from.

    (origin, became) with origin "" meaning winds-invented (procedural filler).
    """
    rows: list[tuple[str, str, str]] = []
    for c in world.characters:
        rows.append(("SOULS", c.origin_name, f"{c.name} ({c.role} of {c.city})"))
    for c in world.cities:
        rows.append(("PLACES", c.origin_name, f"{c.name} (city)"))
    for s in world.sites:
        rows.append(("PLACES", s.origin_name, f"{s.name} ({s.kind})"))
    for r in world.races:
        boosts = ", ".join(f"+{v} {k}" for k, v in (getattr(r, "mods", None) or {}).items())
        if getattr(r, "skill", ""):
            boosts += f", {r.skill} seed" if boosts else f"{r.skill} seed"
        rows.append(("FOLK", r.origin_term, f"{r.name} ({r.trait})" + (f" [{boosts}]" if boosts else "")))
    for c in world.classes:
        origin = c.get("id", "") if c.get("book") else ""
        rows.append(("CALLINGS", origin, f"{c.get('name', '')} ({c.get('template', '')} rites)"))
    for t in world.lore_terms:
        rows.append(("MOTIFS", t, "woven verbatim into names, rumors, gear"))
    for e in world.history:
        rows.append(("ANNALS", str(e.get("year", "?")), e.get("text", "")[:80]))
    return rows


def save_world(world: World, path: str | Path) -> None:
    Path(path).write_text(json.dumps(world.to_dict(), indent=2), encoding="utf-8")


def load_world(path: str | Path) -> World:
    return World.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
