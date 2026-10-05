"""Delvable interiors (Drop 4): rooms + corridors under a site.

Layouts are deterministic from (world seed, site coords), so they cost zero
save space. Only *state* persists: boss slain, chests/tablets used.
"""
from __future__ import annotations

import random

WALL = "#"
FLOOR = "."
STAIRS = "<"
DOWN = ">"
CHEST = "C"
TABLET = "T"
ROAD_IN = "="
HOUSE = "H"
INN = "I"
SHOP = "S"
GATE = "G"

WALKABLE_IN = {FLOOR, STAIRS, DOWN, CHEST, TABLET, "~", "T", "s"}
WALKABLE_TOWN = {FLOOR, ROAD_IN, GATE}


def depth_for_seed(seed: int) -> int:
    """How many floors below: 1, 3, or 5 in seeded random order."""
    h = seed % 10
    if h <= 4:
        return 1
    if h <= 7:
        return 3
    return 5


def gen_interior(seed: int, site_name: str, kind: str, level: int = 0,
                 depth: int = 1, w: int = 40, h: int = 25, theme: str = "") -> dict:
    """Build one level: rooms, L-corridors, stairs up, stairs down (unless
    last), chest/tablet spots. Themes (sunken/overgrown/scorched) stain the
    stone. Level-seeded so floors differ but cost zero save space."""
    rng = random.Random((seed + level * 7919) & 0xFFFFFFFF)
    grid = [[WALL for _ in range(w)] for _ in range(h)]
    rooms = []
    for _ in range(60):
        if len(rooms) >= 8:
            break
        rw, rh = rng.randint(4, 9), rng.randint(3, 6)
        x, y = rng.randint(1, w - rw - 1), rng.randint(1, h - rh - 1)
        if any(x < ox + ow + 1 and ox < x + rw + 1 and
               y < oy + oh + 1 and oy < y + rh + 1 for ox, oy, ow, oh in rooms):
            continue
        rooms.append((x, y, rw, rh))
    if len(rooms) < 3:  # degenerate seed: fall back to one hall
        rooms = [(2, 2, w - 4, h - 4)]
    for x, y, rw, rh in rooms:
        for yy in range(y, y + rh):
            for xx in range(x, x + rw):
                grid[yy][xx] = FLOOR
    stain = {"sunken": "~", "overgrown": "T", "scorched": "s"}.get(theme, "")
    if stain:
        for x, y, rw, rh in rooms[1:]:
            for yy in range(y, y + rh):
                for xx in range(x, x + rw):
                    if grid[yy][xx] == FLOOR and rng.random() < 0.09:
                        grid[yy][xx] = stain
    if kind == "ruin":
        for x, y, rw, rh in rooms[1:]:
            for yy in range(y, y + rh):
                for xx in range(x, x + rw):
                    if rng.random() < 0.12 and (xx, yy) != (x, y):
                        grid[yy][xx] = WALL  # rubble pillars
    # chain rooms with L corridors
    centers = [(x + rw // 2, y + rh // 2) for x, y, rw, rh in rooms]
    for (ax, ay), (bx, by) in zip(centers, centers[1:]):
        x, y = ax, ay
        while x != bx:
            x += 1 if bx > x else -1
            grid[y][x] = FLOOR
        while y != by:
            y += 1 if by > y else -1
            grid[y][x] = FLOOR
    sx, sy = centers[0]
    grid[sy][sx] = STAIRS
    stairs_down = None
    if level < depth - 1:
        dx, dy = centers[-1]
        grid[dy][dx] = DOWN
        stairs_down = (dx, dy)
    chests = []
    for i, (x, y, rw, rh) in enumerate(rooms[1:], 1):
        if len(chests) >= 3 or rng.random() < 0.35:
            continue
        cx, cy = x + rng.randrange(rw), y + rng.randrange(rh)
        if grid[cy][cx] == FLOOR:
            grid[cy][cx] = CHEST
            chests.append({"x": cx, "y": cy, "id": f"{site_name}#{level}#chest{i}"})
    tablets = []
    if kind == "ruin":
        n = 0
        for x, y, rw, rh in rooms[1:]:
            for _ in range(6):
                if n >= 2:
                    break
                cx, cy = x + rng.randrange(rw), y + rng.randrange(rh)
                near_wall = any(grid[cy + dy][cx + dx] == WALL
                                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                                if 0 <= cx + dx < w and 0 <= cy + dy < h)
                if grid[cy][cx] == FLOOR and near_wall:
                    grid[cy][cx] = TABLET
                    tablets.append({"x": cx, "y": cy, "id": f"{site_name}#{level}#tablet{n}"})
                    n += 1
    return {"grid": ["".join(r) for r in grid], "w": w, "h": h,
            "stairs": (sx, sy), "stairs_down": stairs_down,
            "rooms": rooms, "chests": chests,
            "tablets": tablets, "boss_room": centers[-1],
            "level": level, "depth": depth}


def interior_seed(world_seed: int, x: int, y: int) -> int:
    import zlib
    return zlib.crc32(f"{world_seed}:{x}:{y}".encode()) & 0xFFFFFFFF


def gen_town(seed: int, tier: str = "town", w: int = 0, h: int = 0) -> dict:
    """A walkable town: wall ring with gates, plaza cross-streets, houses,
    an inn, shops. Tiers: hamlet (quiet), town, city (sprawl). Deterministic;
    NPCs are placed by the game layer."""
    rng = random.Random(seed ^ 0x70A1)
    dims = {"hamlet": (34, 21, 2, 8), "town": (46, 28, 3, 14), "city": (58, 34, 5, 20)}
    w, h, max_shops, max_npcs = dims.get(tier, dims["town"])
    grid = [[WALL for _ in range(w)] for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            grid[y][x] = FLOOR
    # plaza cross-streets
    for x in range(1, w - 1):
        grid[h // 2][x] = ROAD_IN
    for y in range(1, h - 1):
        grid[y][w // 2] = ROAD_IN
    # gates north + south
    gates = [(w // 2, 0), (w // 2, h - 1)]
    for gx, gy in gates:
        grid[gy][gx] = GATE
    free = [(x, y) for y in range(2, h - 2) for x in range(2, w - 2)
            if grid[y][x] == FLOOR
            and abs(x - w // 2) > 1 and abs(y - h // 2) > 1]
    rng.shuffle(free)

    def claim(rw: int, rh: int) -> tuple[int, int] | None:
        for i, (x, y) in enumerate(free):
            cells = [(x + dx, y + dy) for dy in range(rh) for dx in range(rw)]
            if all(0 <= cx < w and 0 <= cy < h and grid[cy][cx] == FLOOR for cx, cy in cells):
                for cx, cy in cells:
                    grid[cy][cx] = None  # type: ignore
                free[:] = [(fx, fy) for fx, fy in free
                           if not (x - 1 <= fx < x + rw + 1 and y - 1 <= fy < y + rh + 1)]
                return x, y
        return None

    houses = []
    for _ in range(rng.randint(4, 6 + w // 6)):
        spot = claim(2, 2)
        if spot:
            houses.append(spot)
    for x, y in houses:
        for dy in range(2):
            for dx in range(2):
                grid[y + dy][x + dx] = HOUSE
    inn = claim(3, 2)
    if inn:
        for dy in range(2):
            for dx in range(3):
                grid[inn[1] + dy][inn[0] + dx] = INN
    shops = []
    for _ in range(rng.randint(1, max_shops)):
        spot = claim(1, 1)
        if spot:
            shops.append({"x": spot[0], "y": spot[1]})
    for sh in shops:
        grid[sh["y"]][sh["x"]] = SHOP
    # scrub any leftover claim markers
    for y in range(h):
        for x in range(w):
            if grid[y][x] is None:  # type: ignore
                grid[y][x] = FLOOR
    # building-adjacent floor spots for NPCs
    npc_spots = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)
                 if grid[y][x] in (FLOOR, ROAD_IN)]
    rng.shuffle(npc_spots)
    return {"grid": ["".join(r) for r in grid], "w": w, "h": h,
            "gates": gates, "houses": houses, "inn": inn, "shops": shops,
            "npc_spots": npc_spots[:64], "tier": tier, "max_npcs": max_npcs}
