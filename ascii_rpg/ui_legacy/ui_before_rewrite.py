"""Tabbed game shell: MAP | CHARACTERS | BOOKS | SAVES | SETTINGS (pygame, ASCII)."""
from __future__ import annotations

import os
import random
import subprocess
import sys
import time
from pathlib import Path

from .game import (GameState, Player, Enemy, new_game, move_player,
                   interact, heal, rest, combat_attack, combat_heavy,
                   combat_quick, combat_defend, use_consumable,
                   combat_shoot, combat_flee, respawn,
                   region_at, ATTRS, ATTRS_BASE, clock_str, city_shop,
                   shop_buy, shop_sell, equip_item, unequip_item, destroy_item)
from .items import SLOTS, item_line, eff_atk, eff_max_hp, name_pool
from .sfx import play as sfx, set_enabled as sfx_set
from .ingest import collect_book_files, load_corpus
from .saves import (list_saves, write_save, read_save, delete_save,
                    load_settings, save_settings, migrate_legacy_world)
from .worldgen import World, generate_world, WALKABLE

TABS = ["MAP", "CHARACTERS", "BOOKS", "SAVES", "SETTINGS", "INVENTORY", "DATA"]


def _tile_icon(pg, surf, kind: str, X: int, Y: int, s: int, wx: int, wy: int) -> None:
    """Drawn-sprite tile (option 2): shapes instead of ASCII letters.

    kind: map tile char, or 'E' foe / '@' player. Deterministic speckle
    from tile coords keeps it stable frame to frame.
    """
    v = (wx * 7 + wy * 13) % 5
    pad = max(1, s // 11)
    x0, y0, x1, y1 = X + pad, Y + pad, X + s - pad, Y + s - pad
    cx, cy = X + s // 2, Y + s // 2

    def speck(n: int, color, area=(x0, y0, x1, y1)):
        for i in range(n):
            px = area[0] + (wx * 5 + wy * 11 + i * 7) % max(1, area[2] - area[0])
            py = area[1] + (wx * 3 + wy * 7 + i * 13) % max(1, area[3] - area[1])
            surf.set_at((px, py), color)

    if kind == ".":
        pg.draw.rect(surf, (26, 34, 24), (X, Y, s, s))
        speck(2, (38, 48, 34))
    elif kind == "T":
        pg.draw.rect(surf, (24, 33, 22), (X, Y, s, s))
        pg.draw.rect(surf, (90, 60, 35), (cx - 1, y1 - s // 4, 3, s // 4))
        pg.draw.polygon(surf, (34, 110, 48),
                        [(cx, y0), (x1, y1 - s // 5), (x0, y1 - s // 5)])
        pg.draw.polygon(surf, (46, 140, 62),
                        [(cx, y0), (cx, y1 - s // 5), (x0 + 1, y1 - s // 5)])
    elif kind == "^":
        pg.draw.rect(surf, (30, 30, 36), (X, Y, s, s))
        pg.draw.polygon(surf, (130, 130, 140), [(cx, y0), (x1, y1), (x0, y1)])
        pg.draw.polygon(surf, (235, 235, 240),
                        [(cx, y0), (cx + s // 6, y0 + s // 4), (cx - s // 6, y0 + s // 4)])
    elif kind == ",":
        pg.draw.rect(surf, (26, 64, 118), (X, Y, s, s))
        pg.draw.line(surf, (90, 150, 210), (x0, cy), (x1, cy), 1)
    elif kind == "~":
        pg.draw.rect(surf, (18, 46, 100), (X, Y, s, s))
        pg.draw.line(surf, (80, 140, 200), (x0, cy - 2), (x1, cy - 2), 1)
        pg.draw.line(surf, (60, 120, 185), (x0, cy + 2), (x1, cy + 2), 1)
    elif kind == "r":
        pg.draw.rect(surf, (26, 34, 24), (X, Y, s, s))
        pg.draw.rect(surf, (50, 110, 180), (cx - s // 6, Y, s // 3, s))
        pg.draw.line(surf, (130, 190, 240), (cx - s // 6, Y), (cx - s // 6, Y + s), 1)
    elif kind == "s":
        pg.draw.rect(surf, (118, 100, 66), (X, Y, s, s))
        speck(3, (140, 122, 84))
    elif kind == "=":
        pg.draw.rect(surf, (62, 50, 34), (X, Y, s, s))
        pg.draw.rect(surf, (139, 117, 82), (X, cy - 1, s, 3))
    elif kind == "O":
        pg.draw.rect(surf, (30, 28, 22), (X, Y, s, s))
        pg.draw.rect(surf, (150, 110, 50), (cx - s // 5, cy - 1, s // 2.5, s // 3 + 2))
        pg.draw.polygon(surf, (255, 215, 0),
                        [(cx - s // 4, cy - 1), (cx + s // 4, cy - 1), (cx, y0 + 1)])
        pg.draw.rect(surf, (40, 26, 12), (cx - 1, cy + 1, 3, s // 4))
    elif kind == "D":
        pg.draw.rect(surf, (28, 18, 40), (X, Y, s, s))
        pg.draw.rect(surf, (150, 100, 200), (cx - s // 4, y0 + 2, s // 2, y1 - y0 - 2), 1)
        pg.draw.rect(surf, (8, 4, 14), (cx - s // 4 + 2, y0 + 5, s // 2 - 4, y1 - y0 - 7))
    elif kind == "#":
        pg.draw.rect(surf, (80, 68, 48), (X, Y, s, s))
        pg.draw.rect(surf, (170, 158, 130), (x0 + 1, y0 + 2, 3, (y1 - y0) // 2 + v % 3))
        pg.draw.rect(surf, (150, 138, 112), (x1 - 4, y0 + 4, 3, (y1 - y0) // 2 - 1 + v % 3))
    elif kind == "*":
        pg.draw.rect(surf, (14, 30, 42), (X, Y, s, s))
        pg.draw.circle(surf, (60, 140, 170), (cx, cy), s // 3, 1)
        pg.draw.polygon(surf, (140, 230, 255),
                        [(cx, y0 + 2), (x1 - 2, cy), (cx, y1 - 2), (x0 + 2, cy)])
    elif kind == "<":
        pg.draw.rect(surf, (24, 22, 30), (X, Y, s, s))
        for i in range(3):
            yy = y0 + 3 + i * (s // 4)
            pg.draw.line(surf, (200, 180, 120), (x0 + 2, yy), (x1 - 2, yy), 2)
    elif kind == "C":
        pg.draw.rect(surf, (30, 24, 16), (X, Y, s, s))
        pg.draw.rect(surf, (150, 110, 50), (x0 + 2, cy - s // 6, s - 2 * pad - 4, s // 3))
        pg.draw.rect(surf, (255, 215, 0), (x0 + 2, cy - s // 6, s - 2 * pad - 4, s // 3), 1)
        pg.draw.rect(surf, (255, 215, 0), (cx - 1, cy - s // 6, 3, s // 3))
    elif kind == "TAB":
        pg.draw.rect(surf, (44, 40, 32), (X, Y, s, s))
        pg.draw.rect(surf, (170, 158, 130), (cx - s // 5, y0 + 2, s // 2.5, s - 4))
        pg.draw.line(surf, (110, 100, 80), (cx - s // 5 + 2, y0 + 6), (cx + s // 5, y0 + 6), 1)
        pg.draw.line(surf, (110, 100, 80), (cx - s // 5 + 2, y0 + 10), (cx + s // 5, y0 + 10), 1)
    elif kind == "B":
        pg.draw.rect(surf, (50, 10, 10), (X, Y, s, s))
        pg.draw.circle(surf, (255, 60, 60), (cx, cy), s // 3)
        pg.draw.circle(surf, (255, 255, 255), (cx - s // 9, cy - 1), max(1, s // 12))
        pg.draw.circle(surf, (255, 255, 255), (cx + s // 9, cy - 1), max(1, s // 12))
    elif kind == "n":
        pg.draw.rect(surf, (26, 32, 24), (X, Y, s, s))
        pg.draw.circle(surf, (120, 200, 130), (cx, cy), s // 4)
    elif kind == "H":
        pg.draw.rect(surf, (30, 28, 22), (X, Y, s, s))
        pg.draw.rect(surf, (130, 100, 60), (x0 + 2, cy - 1, s - 2 * pad - 4, s // 2 + 1))
        pg.draw.polygon(surf, (90, 60, 35),
                        [(x0 + 1, cy - 1), (x1 - 1, cy - 1), (cx, y0 + 1)])
    elif kind == "I":
        pg.draw.rect(surf, (30, 28, 22), (X, Y, s, s))
        pg.draw.rect(surf, (150, 130, 70), (x0 + 1, y0 + 3, s - 2 * pad - 2, s - 2 * pad - 4))
        pg.draw.rect(surf, (255, 230, 150), (cx - 1, cy - 2, 3, 6))
    elif kind == "S":
        pg.draw.rect(surf, (30, 28, 22), (X, Y, s, s))
        pg.draw.rect(surf, (70, 130, 150), (x0 + 2, cy - 1, s - 2 * pad - 4, s // 3 + 1))
        pg.draw.line(surf, (200, 230, 240), (x0 + 2, cy - 1), (x1 - 2, cy - 1), 1)
    elif kind == "G":
        pg.draw.rect(surf, (60, 55, 40), (X, Y, s, s))
        pg.draw.rect(surf, (20, 18, 12), (cx - s // 6, Y, s // 3, s))
    elif kind == "!":
        pg.draw.rect(surf, (26, 34, 24), (X, Y, s, s))
        pg.draw.polygon(surf, (160, 150, 120), [(cx, y0 + 1), (x1 - 2, y1), (x0 + 2, y1)])
        pg.draw.rect(surf, (255, 215, 0), (cx - 1, y0 + 3, 3, 3))
    elif kind == "X":
        pg.draw.rect(surf, (40, 26, 20), (X, Y, s, s))
        pg.draw.polygon(surf, (200, 120, 60), [(cx, y0 + 2), (x1 - 2, y1 - 2), (x0 + 2, y1 - 2)])
        pg.draw.line(surf, (255, 80, 60), (x0 + 2, y0 + 2), (x1 - 2, y1 - 2), 1)
    elif kind == "v":
        pg.draw.rect(surf, (50, 70, 36), (X, Y, s, s))
        for i in range(3):
            yy = y0 + 3 + i * (s // 4)
            pg.draw.line(surf, (120, 180, 90), (x0 + 2, yy), (x1 - 2, yy), 1)
    elif kind == "E":
        pg.draw.rect(surf, (40, 16, 16), (X, Y, s, s))
        pg.draw.circle(surf, (220, 60, 60), (cx, cy), s // 3)
        pg.draw.circle(surf, (20, 8, 8), (cx - s // 9, cy - 1), max(1, s // 12))
        pg.draw.circle(surf, (20, 8, 8), (cx + s // 9, cy - 1), max(1, s // 12))
    elif kind == "e":
        pg.draw.rect(surf, (40, 28, 12), (X, Y, s, s))
        pg.draw.circle(surf, (230, 150, 60), (cx, cy), s // 3)
        pg.draw.circle(surf, (30, 16, 6), (cx - s // 9, cy - 1), max(1, s // 12))
        pg.draw.circle(surf, (30, 16, 6), (cx + s // 9, cy - 1), max(1, s // 12))
    elif kind == "U":
        pg.draw.rect(surf, (20, 24, 20), (X, Y, s, s))
        pg.draw.circle(surf, (190, 200, 190), (cx, cy), s // 3)
        pg.draw.circle(surf, (10, 20, 10), (cx - s // 9, cy - 1), max(1, s // 12))
        pg.draw.circle(surf, (10, 20, 10), (cx + s // 9, cy - 1), max(1, s // 12))
    elif kind == "R":
        pg.draw.rect(surf, (16, 20, 40), (X, Y, s, s))
        pg.draw.circle(surf, (120, 160, 220), (cx, cy), s // 3)
        pg.draw.circle(surf, (10, 14, 26), (cx - s // 9, cy - 1), max(1, s // 12))
        pg.draw.circle(surf, (10, 14, 26), (cx + s // 9, cy - 1), max(1, s // 12))
    elif kind == "a":
        pg.draw.rect(surf, (34, 22, 10), (X, Y, s, s))
        pg.draw.circle(surf, (200, 130, 60), (cx, cy), s // 4)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pg.draw.line(surf, (200, 130, 60),
                         (cx, cy), (cx + dx * (s // 2 - 1), cy + dy * (s // 2 - 1)), 1)
    elif kind == "g":
        pg.draw.rect(surf, (16, 20, 26), (X, Y, s, s))
        pg.draw.circle(surf, (150, 190, 220), (cx, cy), s // 3, 2)
        pg.draw.circle(surf, (150, 190, 220), (cx, cy - 1), max(1, s // 10))
    elif kind == "M":
        pg.draw.rect(surf, (26, 26, 30), (X, Y, s, s))
        pg.draw.rect(surf, (140, 140, 150), (x0 + 3, y0 + 5, s - 2 * pad - 6, s - 2 * pad - 8))
        pg.draw.rect(surf, (90, 90, 100), (x0 + 3, y0 + 5, s - 2 * pad - 6, 3))
    elif kind == "W":
        pg.draw.rect(surf, (44, 14, 10), (X, Y, s, s))
        pg.draw.polygon(surf, (240, 120, 50),
                        [(x0 + 1, y1 - 2), (cx, y0 + 2), (x1 - 1, y1 - 2)])
        pg.draw.circle(surf, (255, 200, 120), (cx, cy), max(1, s // 8))
    elif kind == "@":
        pg.draw.circle(surf, (240, 240, 245), (cx, cy), s // 3)
        pg.draw.circle(surf, (255, 215, 0), (cx, cy), s // 3, 1)
        pg.draw.circle(surf, (90, 160, 255), (cx, cy - s // 7), max(1, s // 10))
    else:
        pg.draw.rect(surf, (26, 34, 24), (X, Y, s, s))
        speck(2, (38, 48, 34))


PANEL_BG = (18, 22, 32)
PANEL_LINE = (42, 48, 68)
TEXT_DIM = (148, 154, 172)
TEXT_MID = (200, 204, 218)


def _panel(pg, screen, rect, border=PANEL_LINE) -> None:
    """One rounded card. Every sidebar section and modal shares it."""
    pg.draw.rect(screen, PANEL_BG, rect, border_radius=8)
    pg.draw.rect(screen, border, rect, 1, border_radius=8)


def _bar(pg, screen, x: int, y: int, w: int, h: int, frac: float,
         fill: tuple, bg: tuple, label: str = "", font=None) -> None:
    """Pill bar with an optional centered label."""
    frac = max(0.0, min(1.0, frac))
    pg.draw.rect(screen, bg, (x, y, w, h), border_radius=h // 2)
    if frac > 0:
        pg.draw.rect(screen, fill, (x, y, max(h, int(w * frac)), h), border_radius=h // 2)
    if label and font is not None:
        img = font.render(label, True, (255, 255, 255))
        screen.blit(img, (x + w // 2 - img.get_width() // 2, y + h // 2 - img.get_height() // 2))


def _pills(pg, screen, x: int, y: int, items: list, font) -> int:
    """Row of status pills [(text, color)]. Returns height used (0 if none)."""
    cx = x
    for text, color in items:
        img = font.render(text, True, color)
        r = pg.Rect(cx, y, img.get_width() + 12, 18)
        pg.draw.rect(screen, (26, 31, 46), r, border_radius=9)
        pg.draw.rect(screen, color, r, 1, border_radius=9)
        screen.blit(img, (cx + 6, y + 2))
        cx += r.width + 6
    return 22 if items else 0


def _spawn(world: World, rng: random.Random) -> tuple[int, int]:
    grid = world.grid
    h, w = len(grid), len(grid[0])
    for _ in range(500):
        x, y = rng.randrange(w), rng.randrange(h)
        if grid[y][x] in WALKABLE:
            return x, y
    return w // 2, h // 2


def random_player(world: World, name: str, race: str, rng: random.Random,
                  attrs: dict | None = None) -> Player:
    x, y = _spawn(world, rng)
    a = dict(ATTRS_BASE)
    if attrs:
        a.update({k: max(1, min(10, int(v))) for k, v in attrs.items() if k in a})
    else:
        for k in a:
            a[k] = 4 + rng.randint(0, 3)
    hp = 30 + a["CON"] * 4 + rng.randint(0, 10)
    atk = 5 + a["STR"] // 2 + rng.randint(0, 3)
    mana = 8 + a["WIS"] * 4
    return Player(x=x, y=y, hp=hp, max_hp=hp, atk=atk, gold=20,
                  name=name or "Wanderer", race=race, attrs=a,
                  mana=mana, max_mana=mana)


class App:
    def __init__(self, root: str | Path, books: str | Path = "books",
                 seed: int | None = None) -> None:
        self.root = Path(root)
        self.books_dir = self.root / books if not Path(books).is_absolute() else Path(books)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.settings = load_settings(self.root)
        migrate_legacy_world(self.root)
        self.tab = "MAP"
        self.sel = 0
        self.typing: tuple[str, str] | None = None  # (field, buffer)
        self.pending_name = ""
        self.pending_race = ""
        self.pending_class: dict | None = None
        self.class_idx = 0
        self.race_idx = 0
        self.spellbook_open = False
        self.alloc: dict | None = None
        self.alloc_left = 0
        self.attr_idx = 0
        self.attr_focus = False
        self.book_files: list[Path] = []
        self.msg = ""
        self.started = False
        self.title_sel = 0
        self.title_mode = "menu"  # menu | load
        self._title_rects: list = []
        self.tracked_id: str | None = None
        self.caravan_open = False
        self.caravan_sel = 0
        self.oath_open = False
        self.oath_sel = 0
        self.draft_open = False
        self.show_legend = False
        self.journal = False
        self.shop_open: str | None = None
        self.shop_rows_cache: list | None = None
        self.shop_sel = 0
        self.shop_mode = "buy"
        self.inv_sel = 0
        self._mm_key = None
        self._mm_base = None
        self.last_autosave = time.time()
        self.save_name = "slot1"
        saves = list_saves(self.root)
        if saves and seed is None:
            self.save_name = saves[0]["name"]
        self.world: World | None = None
        self.roster: list[Player] = []
        self.active = 0
        self.state: GameState | None = None
        self.just_created = False
        self.wiz: dict | None = None  # title-screen hero creation
        self.spellbook_open = False
        self.load_or_create(self.save_name, seed=seed)

    # ---------- persistence ----------
    def persist(self) -> None:
        if not self.world or not self.state:
            return
        # sync active player object back into roster
        if self.roster:
            self.roster[self.active] = self.state.player
        write_save(self.root, self.save_name, self.world.to_dict(),
                   [p.to_dict() for p in self.roster], self.active,
                   [e.__dict__ for e in self.state.enemies])

    def load_or_create(self, name: str, seed: int | None = None) -> None:
        self.persist() if self.world else None
        self.save_name = name
        try:
            wd, roster_d, active, enemies_d = read_save(self.root, name)
            self.world = World.from_dict(wd)
            self.roster = [Player.from_dict(d) for d in roster_d]
            self.active = min(active, max(0, len(self.roster) - 1))
            self.just_created = False
        except FileNotFoundError:
            corpus = self._corpus()
            s = seed if seed is not None else random.randrange(1_000_000)
            self.world = generate_world(corpus, seed=s)
            self.roster, self.active = [], 0
            enemies_d = []
            self.just_created = True
            self.persist()
        assert self.world is not None
        from .plot import ensure_plot
        if not self.world.plot:
            ensure_plot(self.world, random.Random(self.world.seed + 4242))
            self.persist()
        if self.roster:
            player = self.roster[self.active]
        else:
            from .game import apply_race_package
            player = random_player(self.world, "Wanderer",
                                   self.world.races[0].name if self.world.races else "Human",
                                   random.Random(self.world.seed))
            blood = next((r for r in self.world.races if r.name == player.race), None)
            if blood is not None:
                apply_race_package(player, blood)
            self.roster = [player]
            self.active = 0
        self.state = new_game(self.world, seed=self.world.seed + 999,
                              player=player,
                              difficulty=self.settings.get("difficulty", "normal"))
        self.state.roster = self.roster
        # resume an interrupted delve: rebuild the dungeon, fresh foes
        snap = self.world.active_interior
        if isinstance(snap, dict) and snap.get("site"):
            from .game import descend
            site = next((s for s in self.world.sites if s.name == snap["site"]), None)
            if site is None:
                site = next((c for c in self.world.cities if c.name == snap["site"]), None)
            if site is not None:
                kept_ow = snap.get("ow_enemies", [])
                kept_rx, kept_ry = snap.get("return_x", 0), snap.get("return_y", 0)
                descend(self.state, site, random.Random(self.world.seed), quiet=True)
                self.world.active_interior["ow_enemies"] = kept_ow
                self.world.active_interior["return_x"] = kept_rx
                self.world.active_interior["return_y"] = kept_ry
                if self.state.interior.get("kind") == "city":
                    gx, gy = self.state.interior["gates"][0]
                    self.state.player.x, self.state.player.y = gx, gy + 1
                else:
                    sx, sy = self.state.interior["stairs"]
                    self.state.player.x, self.state.player.y = sx, sy
                self.state.log("You wake where you fell asleep.")
            else:
                self.world.active_interior = None
        # restore shared enemies if save had them
        if enemies_d:
            try:
                self.state.enemies = [Enemy(**e) for e in enemies_d]
            except Exception:
                pass
        self.persist()
        self.refresh_books()

    def _corpus(self) -> str:
        files = collect_book_files(self.books_dir)
        try:
            return load_corpus(files) if files else ""
        except Exception:
            return ""

    def refresh_books(self) -> None:
        self.book_files = collect_book_files(self.books_dir)

    def regen(self, seed: int | None = None) -> None:
        corpus = self._corpus()
        s = seed if seed is not None else random.randrange(1_000_000)
        self.world = generate_world(corpus, seed=s)
        # respawn roster on new map
        rng = random.Random(s)
        for p in self.roster:
            p.x, p.y = _spawn(self.world, rng)
            p.hp = p.max_hp
        self.state = new_game(self.world, player=self.roster[self.active] if self.roster else None,
                              difficulty=self.settings.get("difficulty", "normal"))
        self.state.roster = self.roster
        self.state.log(f"World reborn from {len(self.book_files)} book(s), seed {s}.")
        self.persist()

    # ---------- characters ----------
    def new_character(self, name: str, race: str, attrs: dict | None = None,
                      cls: dict | None = None) -> None:
        from .game import apply_class_package, apply_race_package
        assert self.world and self.state
        p = random_player(self.world, name, race, random.Random(), attrs)
        blood = next((r for r in self.world.races if r.name == race), None)
        if blood is not None:
            apply_race_package(p, blood)
        if cls:
            apply_class_package(p, cls, name_pool(self.world), random.Random(),
                                climate=self.world.climate)
        self.roster.append(p)
        self.active = len(self.roster) - 1
        self.state.player = p
        self.state.log(f"{name} ({race}) joins {self.save_name}.")
        self.persist()

    def switch_character(self, i: int) -> None:
        assert self.state
        if not (0 <= i < len(self.roster)):
            return
        # stash current pos/hp into roster slot
        self.roster[self.active] = self.state.player
        self.active = i
        self.state.player = self.roster[i]
        self.state.in_combat_with = None
        self.state.log(f"Now playing {self.state.player.name}.")
        self.persist()

    # ---------- pygame ----------
    def run(self) -> None:
        try:
            import pygame
        except ImportError:
            raise SystemExit("pygame not installed. Run: pip install -r requirements.txt")
        pg = pygame
        pg.init()
        sfx_set(self.settings.get("sound", True))
        TILE = int(self.settings.get("tile", 22))
        VW, VH = 33, 21
        SIDE = 330
        TAB_H, HUD_H = 34, 158
        MW = VW * TILE
        W, H = MW + SIDE, TAB_H + VH * TILE + HUD_H
        screen = pg.display.set_mode((W, H))
        pg.display.set_caption("Inkbound Realms - ASCII RPG")
        font = pg.font.SysFont("consolas,courier new,monospace", max(12, TILE - 4))
        small = pg.font.SysFont("consolas,courier new,monospace", 15)
        tiny = pg.font.SysFont("consolas,courier new,monospace", 13)
        big = pg.font.SysFont("consolas,courier new,monospace", 40)
        BG, PANEL, ACC = (12, 14, 20), (22, 26, 36), (255, 215, 0)
        COLORS = {".": (120, 160, 120), ",": (70, 130, 180), "~": (40, 90, 200),
                  "r": (90, 150, 220), "s": (190, 165, 110),
                  "T": (40, 140, 60), "^": (150, 150, 160), "O": (255, 215, 0),
                  "D": (190, 120, 255), "#": (200, 170, 120), "=": (150, 120, 70),
                  "*": (120, 220, 255)}
        if not self.settings.get("color", True):
            COLORS = {k: (200, 200, 200) for k in COLORS}
        clock = pg.time.Clock()
        running = True

        def draw_tabs() -> list:
            rects = []
            x = 6
            for i, t in enumerate(TABS):
                label = f"{i+1}:{t}"
                img = tiny.render(label, True, ACC if t == self.tab else (180, 180, 180))
                r = pg.Rect(x, 6, img.get_width() + 18, 24)
                pg.draw.rect(screen, PANEL if t != self.tab else (40, 46, 64), r, border_radius=4)
                screen.blit(img, (x + 9, 9))
                rects.append((r, t))
                x += r.width + 6
            hint = tiny.render(f"{self.save_name}  seed {self.world.seed if self.world else '?'}",
                               True, (130, 130, 130))
            screen.blit(hint, (W - hint.get_width() - 10, 10))
            return rects

        def line(txt: str, y: int, color=(220, 220, 220), f=small):
            screen.blit(f.render(txt[:110], True, color), (12, y))

        assert self.world and self.state
        from .game import _tally
        _tally(self.world, "sessions")
        self.persist()
        session_start = time.time()
        tab_rects: list = []
        while running:
            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    running = False
                elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
                    if not self.started:
                        for r, act in self._title_rects:
                            if r.collidepoint(ev.pos):
                                self._title_action(act)
                                break
                        continue
                    for r, t in tab_rects:
                        if r.collidepoint(ev.pos):
                            self.persist()
                            self.tab = t
                            self.shop_open = None
                            self.shop_rows_cache = None
                            self.sel = 0
                elif ev.type == pg.KEYDOWN:
                    k = ev.key
                    if not self.started:
                        if self.typing:
                            field, buf = self.typing
                            if k == pg.K_RETURN:
                                self._confirm_typing()
                            elif k == pg.K_ESCAPE:
                                self.typing = None
                                self.pending_name, self.pending_race = "", ""
                                self.alloc, self.alloc_left = None, 0
                                self.pending_class = None
                                if self.wiz is not None:
                                    self.wiz, self.title_mode = None, "menu"
                            elif k == pg.K_BACKSPACE:
                                self.typing = (field, buf[:-1])
                            elif ev.unicode and ev.unicode.isprintable() and len(buf) < 24:
                                self.typing = (field, buf + ev.unicode)
                            continue
                        if self.title_mode == "load":
                            saves = list_saves(self.root)
                            if k == pg.K_UP:
                                self.sel = max(0, self.sel - 1)
                            elif k == pg.K_DOWN:
                                self.sel = max(0, min(max(0, len(saves) - 1), self.sel + 1))
                            elif k in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE) and saves:
                                self.load_or_create(saves[self.sel]["name"])
                                self.started, self.tab = True, "MAP"
                            elif k == pg.K_ESCAPE:
                                self.title_mode = "menu"
                            continue
                        if self.wiz is not None:
                            self._wiz_key(pg, k)
                            continue
                        if k == pg.K_UP:
                            self.title_sel = max(0, self.title_sel - 1)
                        elif k == pg.K_DOWN:
                            self.title_sel = min(2, self.title_sel + 1)
                        elif k in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                            if self.title_sel == 0:
                                self.typing = ("save_name", "")
                            elif self.title_sel == 1:
                                self.title_mode, self.sel = "load", 0
                            else:
                                running = False
                        elif k == pg.K_q:
                            running = False
                        continue
                    # global tab shortcuts
                    if self.typing:
                        field, buf = self.typing
                        if k == pg.K_RETURN:
                            self._confirm_typing()
                        elif k == pg.K_ESCAPE:
                            self.typing = None
                            self.pending_name, self.pending_race = "", ""
                            self.alloc, self.alloc_left = None, 0
                        elif k == pg.K_BACKSPACE:
                            self.typing = (field, buf[:-1])
                        elif ev.unicode and ev.unicode.isprintable() and len(buf) < 24:
                            self.typing = (field, buf + ev.unicode)
                        continue
                    if k in (pg.K_1, pg.K_2, pg.K_3, pg.K_4, pg.K_5, pg.K_6, pg.K_7):
                        if self.spellbook_open and self.tab == "MAP" and pg.K_1 <= k <= pg.K_9:
                            pass  # digits cast while the book is open
                        elif self.draft_open and self.tab == "CHARACTERS" and pg.K_1 <= k <= pg.K_4:
                            pass  # digits draft while the draft is open
                        else:
                            self.persist()
                            self.tab = TABS[k - pg.K_1]
                            self.shop_open = None
                            self.shop_rows_cache = None
                            self.spellbook_open = False
                            sfx("ui")
                            self.sel = 0
                            continue
                    if k == pg.K_q and self.tab == "MAP" and not self.state.in_combat_with:
                        running = False
                        continue
                    if k == pg.K_j and self.tab == "MAP":
                        self.journal = not self.journal
                        continue
                    if k == pg.K_l and self.tab == "MAP":
                        self.show_legend = not self.show_legend
                        continue
                    if k == pg.K_r and self.tab == "MAP" and self.state.player.hp <= 0:
                        respawn(self.state)
                        self.persist()
                        continue
                    self._key(pg, k)
            # autosave
            if time.time() - self.last_autosave > 60:
                self.persist()
                self.last_autosave = time.time()

            screen.fill(BG)
            if not self.started:
                self._draw_title(screen, big, small, tiny, W, H, ACC, PANEL, BG)
                pg.display.flip()
                clock.tick(30)
                continue
            tab_rects = draw_tabs()
            top = TAB_H
            if self.tab == "MAP":
                self._draw_map(pg, screen, font, small, tiny, big, COLORS, VW, VH, top, TILE, MW, SIDE, W, H, ACC, PANEL, BG)
            elif self.tab == "CHARACTERS":
                self._draw_chars(pg, screen, small, tiny, top, H, ACC, PANEL)
            elif self.tab == "BOOKS":
                self._draw_books(screen, small, tiny, top, H, ACC)
            elif self.tab == "SAVES":
                self._draw_saves(screen, small, tiny, top, H, ACC)
            elif self.tab == "SETTINGS":
                self._draw_settings(screen, small, tiny, top, H, ACC)
            elif self.tab == "INVENTORY":
                self._draw_inventory(pg, screen, small, tiny, top, H, ACC, PANEL)
            elif self.tab == "DATA":
                self._draw_data(screen, small, tiny, top, H, ACC, PANEL)
            # typing overlay
            if self.typing:
                field, buf = self.typing
                prompt = "Character name" if field == "char_name" else "Save name"
                box = pg.Rect(W // 2 - 180, H // 2 - 40, 360, 80)
                pg.draw.rect(screen, (30, 34, 48), box, border_radius=6)
                pg.draw.rect(screen, ACC, box, 2, border_radius=6)
                screen.blit(small.render(f"{prompt}: {buf}_", True, (255, 255, 255)),
                            (box.x + 16, box.y + 28))
            if self.msg:
                screen.blit(tiny.render(self.msg[:110], True, ACC), (12, H - 22))
            pg.display.flip()
            clock.tick(30)
        _tally(self.world, "minutes", max(1, int((time.time() - session_start) // 60)))
        self.persist()
        save_settings(self.root, self.settings)
        pg.quit()

    # ----- input handling per tab -----
    def _key(self, pg, k: int) -> None:
        assert self.state and self.world
        st = self.state
        if self.tab == "MAP":
            if st.in_combat_with:
                if k == pg.K_a:
                    combat_attack(st)
                elif k == pg.K_h:
                    combat_heavy(st)
                elif k == pg.K_q:
                    combat_quick(st)
                elif k == pg.K_d:
                    combat_defend(st)
                elif k == pg.K_p:
                    self._use_sub(st, "potion")
                elif k == pg.K_b:
                    self._use_sub(st, "bomb")
                elif k == pg.K_v:
                    self._use_sub(st, "smoke")
                elif k == pg.K_u:
                    self._use_sub(st, "quiver")
                elif k == pg.K_r:
                    combat_shoot(st)
                elif k == pg.K_f:
                    combat_flee(st)
                elif k == pg.K_c:
                    self.spellbook_open = not self.spellbook_open
                elif k == pg.K_ESCAPE:
                    self.spellbook_open = False
                elif self.spellbook_open and k in (pg.K_1, pg.K_2, pg.K_3, pg.K_4,
                                                   pg.K_5, pg.K_6, pg.K_7, pg.K_8,
                                                   pg.K_9):
                    from .game import cast_spell
                    known = self._known_spells()
                    idx = k - pg.K_1
                    if idx < len(known) and cast_spell(st, known[idx]["id"]):
                        sfx("spell")
                        self.persist()
                self.persist()
            elif self.shop_open is not None:
                self._shop_key(pg, k)
            elif self.caravan_open:
                if k in (pg.K_f, pg.K_ESCAPE):
                    self.caravan_open = False
                elif k == pg.K_UP:
                    self.caravan_sel = max(0, self.caravan_sel - 1)
                elif k == pg.K_DOWN:
                    dests = self._caravan_dests()
                    self.caravan_sel = min(max(0, len(dests) - 1), self.caravan_sel + 1)
                elif k == pg.K_RETURN:
                    from .game import caravan_ride
                    dests = self._caravan_dests()
                    if dests and caravan_ride(self.state, dests[self.caravan_sel][0]):
                        self.caravan_open = False
                        self.persist()
                    sfx("ui")
            elif self.oath_open:
                from .game import faction_rows, swear_oath, forswear_oath
                rows = faction_rows(st)
                if k in (pg.K_o, pg.K_ESCAPE):
                    self.oath_open = False
                elif k == pg.K_UP:
                    self.oath_sel = max(0, self.oath_sel - 1)
                elif k == pg.K_DOWN:
                    self.oath_sel = min(max(0, len(rows) - 1), self.oath_sel + 1)
                elif k == pg.K_RETURN and rows:
                    sel = rows[min(self.oath_sel, len(rows) - 1)]
                    if sel["oath"]:
                        forswear_oath(st)
                    else:
                        swear_oath(st, sel["id"])
                    self.persist()
                    sfx("ui")
            else:
                if st.world.ending and k == pg.K_RETURN:
                    st.world.ending = ""
                    self.persist()
                    return
                if k in (pg.K_UP, pg.K_w):
                    move_player(st, 0, -1)
                elif k in (pg.K_DOWN, pg.K_s):
                    move_player(st, 0, 1)
                elif k in (pg.K_LEFT, pg.K_a):
                    move_player(st, -1, 0)
                elif k in (pg.K_RIGHT, pg.K_d):
                    move_player(st, 1, 0)
                elif k == pg.K_e:
                    interact(st)
                elif k == pg.K_h:
                    heal(st)
                elif k == pg.K_z:
                    rest(st)
                    self.persist()
                elif k == pg.K_b:
                    if st.interior is not None and st.interior.get("kind") == "city":
                        doors = st.interior.get("shop_buildings", [])
                        near = [i for i, d in enumerate(doors)
                                if abs(d["x"] - st.player.x) + abs(d["y"] - st.player.y) <= 1]
                        if near:
                            from .game import shop_rows
                            self.shop_open = st.interior["site"]
                            self.shop_rows_cache = shop_rows(st, near[0])
                            self.shop_sel, self.shop_mode = 0, "buy"
                            sfx("ui")
                        else:
                            st.log("No shop door near. Look for S.")
                    elif city_shop(st) is not None:
                        from .game import shop_rows
                        self.shop_open = next(
                            c.name for c in self.world.cities
                            if c.x == st.player.x and c.y == st.player.y)
                        self.shop_rows_cache = shop_rows(st)
                        self.shop_sel, self.shop_mode = 0, "buy"
                        sfx("ui")
                    else:
                        st.log("Shops only in cities (O).")
                elif k == pg.K_t:
                    self._cycle_tracked()
                elif k == pg.K_r:
                    combat_shoot(st)
                    self.persist()
                elif k == pg.K_u:
                    self._use_sub(st, "quiver")
                elif k == pg.K_f:
                    if self._in_city_tile():
                        self.caravan_open = True
                        self.caravan_sel = 0
                        self.spellbook_open = False
                        self.oath_open = False
                        sfx("ui")
                    else:
                        st.log("Caravans leave from cities (O).")
                elif k == pg.K_c:
                    if st.player.spells:
                        opening = not self.spellbook_open
                        self.spellbook_open = opening
                        if opening:
                            self.caravan_open = False
                            self.oath_open = False
                            self.shop_open = None
                            self.shop_rows_cache = None
                    else:
                        st.log("No spells known. Shrines (*) teach the willing.")
                elif k == pg.K_o:
                    self.oath_open = not self.oath_open
                    self.oath_sel = 0
                    sfx("ui")
                elif self.spellbook_open and k in (pg.K_1, pg.K_2, pg.K_3, pg.K_4,
                                                       pg.K_5, pg.K_6, pg.K_7, pg.K_8,
                                                       pg.K_9):
                    from .game import cast_spell
                    known = self._known_spells()
                    idx = k - pg.K_1
                    if idx < len(known) and cast_spell(st, known[idx]["id"]):
                        self.spellbook_open = False
                        sfx("spell")
                        self.persist()
                elif self.spellbook_open and k == pg.K_ESCAPE:
                    self.spellbook_open = False
        elif self.tab == "CHARACTERS":
            n = len(self.roster)
            if self.alloc is not None:  # attribute point-buy mode
                if k == pg.K_UP:
                    self.attr_idx = max(0, self.attr_idx - 1)
                elif k == pg.K_DOWN:
                    self.attr_idx = min(len(ATTRS) - 1, self.attr_idx + 1)
                elif k == pg.K_LEFT:
                    key = ATTRS[self.attr_idx]
                    if self.alloc[key] > 1:
                        self.alloc[key] -= 1
                        self.alloc_left += 1
                elif k == pg.K_RIGHT:
                    key = ATTRS[self.attr_idx]
                    if self.alloc_left > 0:
                        self.alloc[key] += 1
                        self.alloc_left -= 1
                elif k == pg.K_RETURN:
                    self.new_character(self.pending_name, self.pending_race, self.alloc,
                                       self.pending_class if isinstance(self.pending_class, dict) else None)
                    leftover = self.alloc_left
                    if leftover and self.roster:
                        self.roster[-1].unspent += leftover
                    self.pending_name, self.pending_race = "", ""
                    self.pending_class = None
                    self.alloc, self.alloc_left = None, 0
                    self.msg = f"Created {self.roster[-1].name}."
                elif k == pg.K_ESCAPE:
                    self.pending_name, self.pending_race = "", ""
                    self.pending_class = None
                    self.alloc, self.alloc_left = None, 0
                return
            if self.pending_class is False:  # class-pick mode (False = choosing)
                classes = self.world.classes or []
                if k == pg.K_LEFT:
                    self.class_idx = (self.class_idx - 1) % len(classes)
                elif k == pg.K_RIGHT:
                    self.class_idx = (self.class_idx + 1) % len(classes)
                elif k == pg.K_RETURN:
                    self.pending_class = classes[self.class_idx]
                    self.alloc = dict(ATTRS_BASE)
                    self.alloc_left = 8
                    self.attr_idx = 0
                elif k == pg.K_ESCAPE:
                    self.pending_class = None
                    self.pending_name = ""
                return
            if self.pending_name and self.pending_class is None:  # race-pick mode
                races = [r.name for r in self.world.races] or ["Human"]
                if k == pg.K_LEFT:
                    self.race_idx = (self.race_idx - 1) % len(races)
                elif k == pg.K_RIGHT:
                    self.race_idx = (self.race_idx + 1) % len(races)
                elif k == pg.K_RETURN:
                    self.pending_race = races[self.race_idx]
                    if self.world.classes:
                        self.pending_class = False  # type: ignore[assignment]
                        self.class_idx = 0
                    else:
                        self.alloc = dict(ATTRS_BASE)
                        self.alloc_left = 8
                        self.attr_idx = 0
                elif k == pg.K_ESCAPE:
                    self.pending_name = ""
                    self.pending_class = None
                return
            if self.draft_open:
                from .perks import draft_offer, take_draft
                if k in (pg.K_ESCAPE, pg.K_p):
                    self.draft_open = False
                elif k in (pg.K_1, pg.K_2, pg.K_3, pg.K_4):
                    assert self.state
                    hero = self.roster[self.sel] if 0 <= self.sel < len(self.roster) else None
                    if hero is not None and take_draft(self.state, k - pg.K_1, hero):
                        self.draft_open = False
                        self.persist()
                        sfx("quest")
                return
            if k == pg.K_TAB:
                self.attr_focus = not self.attr_focus
                self.attr_idx = 0
                return
            if self.attr_focus and n:
                p = self.roster[self.sel]
                if k == pg.K_UP:
                    self.attr_idx = max(0, self.attr_idx - 1)
                elif k == pg.K_DOWN:
                    self.attr_idx = min(len(ATTRS) - 1, self.attr_idx + 1)
                elif k == pg.K_RIGHT and p.unspent > 0:
                    key = ATTRS[self.attr_idx]
                    p.attrs[key] = p.attrs.get(key, 4) + 1
                    p.unspent -= 1
                    if key == "CON":
                        p.max_hp += 4
                        p.hp += 4
                    self.persist()
                    self.msg = f"{p.name}: {key} -> {p.attrs[key]} ({p.unspent} points left)."
                elif k in (pg.K_LEFT, pg.K_ESCAPE):
                    self.attr_focus = False
                return
            if k == pg.K_UP:
                self.sel = max(0, self.sel - 1)
            elif k == pg.K_DOWN:
                self.sel = max(0, min(max(0, n - 1), self.sel + 1))
            elif k == pg.K_RETURN and n:
                self.switch_character(self.sel)
            elif k == pg.K_n:
                self.typing = ("char_name", "")
            elif k == pg.K_d and n > 1:
                del self.roster[self.sel]
                self.sel = max(0, self.sel - 1)
                if self.active >= len(self.roster):
                    self.active = 0
                self.state.player = self.roster[self.active]
                self.persist()
            elif k == pg.K_p and n:
                from .perks import drafts_pending
                if drafts_pending(self.roster[self.sel]):
                    self.draft_open = True
                    sfx("ui")
                else:
                    self.msg = "No perk draft waits (one every 5th level)."
        elif self.tab == "BOOKS":
            if k == pg.K_r:
                self.refresh_books()
                self.regen()
                self.msg = f"Regenerated seed {self.world.seed} from {len(self.book_files)} book(s)."
            elif k == pg.K_o:
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(str(self.books_dir))  # type: ignore
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(self.books_dir)])
                    else:
                        subprocess.Popen(["xdg-open", str(self.books_dir)])
                except Exception as e:
                    self.msg = f"Cannot open folder: {e}"
        elif self.tab == "SAVES":
            saves = list_saves(self.root)
            if k == pg.K_UP:
                self.sel = max(0, self.sel - 1)
            elif k == pg.K_DOWN:
                self.sel = max(0, min(max(0, len(saves) - 1), self.sel + 1))
            elif k == pg.K_RETURN and saves:
                self.load_or_create(saves[self.sel]["name"])
                self.msg = f"Loaded {self.save_name}."
            elif k == pg.K_n:
                self.typing = ("save_name", "")
            elif k == pg.K_d and saves and len(saves) > 1:
                delete_save(self.root, saves[self.sel]["name"])
                self.sel = 0
                self.load_or_create(list_saves(self.root)[0]["name"])
        elif self.tab == "SETTINGS":
            opts = ["graphics", "sound", "tile", "difficulty", "color"]
            if k == pg.K_UP:
                self.sel = max(0, self.sel - 1)
            elif k == pg.K_DOWN:
                self.sel = min(len(opts) - 1, self.sel + 1)
            elif k in (pg.K_LEFT, pg.K_RIGHT):
                d = -1 if k == pg.K_LEFT else 1
                cur = opts[self.sel]
                if cur == "graphics":
                    order = ["icons", "ascii"]
                    g = self.settings.get("graphics", "icons")
                    self.settings["graphics"] = order[(order.index(g) + d) % 2]
                    self.msg = f"Graphics: {self.settings['graphics']} (live)."
                elif cur == "sound":
                    self.settings["sound"] = not self.settings.get("sound", True)
                    sfx_set(self.settings["sound"])
                    sfx("ui")
                    self.msg = f"Sound: {'on' if self.settings['sound'] else 'off'}."
                elif cur == "tile":
                    tiles = [18, 22, 28]
                    t = int(self.settings.get("tile", 22))
                    t = tiles[min(len(tiles) - 1, max(0, tiles.index(t) + d if t in tiles else 1))]
                    self.settings["tile"] = t
                    self.msg = "Tile size applies on restart."
                elif cur == "difficulty":
                    order = ["easy", "normal", "hard"]
                    cur_d = self.settings.get("difficulty", "normal")
                    self.settings["difficulty"] = order[(order.index(cur_d) + d) % 3]
                elif cur == "color":
                    self.settings["color"] = not self.settings.get("color", True)
                    self.msg = "Color mode applies on restart."
            elif k == pg.K_s:
                save_settings(self.root, self.settings)
                self.persist()
                self.msg = "Settings + save stored."
        elif self.tab == "INVENTORY":
            assert self.state
            p = self.state.player
            n = len(p.inventory) + len(SLOTS)
            if k == pg.K_UP:
                self.inv_sel = max(0, self.inv_sel - 1)
            elif k == pg.K_DOWN:
                self.inv_sel = min(max(0, n - 1), self.inv_sel + 1)
            elif k == pg.K_RETURN:
                if self.inv_sel < len(SLOTS):
                    unequip_item(self.state, SLOTS[self.inv_sel])
                else:
                    equip_item(self.state, self.inv_sel - len(SLOTS))
                self.persist()
            elif k == pg.K_d:
                if self.inv_sel >= len(SLOTS):
                    destroy_item(self.state, self.inv_sel - len(SLOTS))
                    self.inv_sel = max(len(SLOTS), self.inv_sel - 1)
                    self.persist()
        elif self.tab == "DATA":
            if k == pg.K_UP:
                self.sel = max(0, self.sel - 1)
            elif k == pg.K_DOWN:
                self.sel += 1

    def _known_spells(self) -> list:
        from .magic import spellbook, bloodprice_def
        assert self.state and self.world
        known = [s for s in spellbook(name_pool(self.world))
                 if s["id"] in self.state.player.spells]
        if "bloodprice" in (self.state.player.spells or []):
            known.append(bloodprice_def())
        return known

    def _in_city_tile(self) -> bool:
        assert self.state
        p = self.state.player
        return self.state.interior is None and any(
            c.x == p.x and c.y == p.y for c in self.world.cities)

    def _use_sub(self, st, sub: str) -> None:
        """Combat hotkey: use the first pack consumable of one kind."""
        idx = next((i for i, it in enumerate(st.player.inventory)
                    if (it.get("kind") or "") == "consumable"
                    and it.get("sub") == sub), -1)
        if idx < 0:
            st.log(f"No {sub} in your pack (shops + loot carry them).")
            return
        use_consumable(st, idx)
        self.persist()

    def _caravan_dests(self) -> list[tuple[str, int]]:
        """Visited cities (except here) with fares, nearest first."""
        assert self.state and self.world
        p = self.state.player
        out = []
        for c in self.world.cities:
            if (c.x, c.y) == (p.x, p.y):
                continue
            if c.name in (self.world.visited or []):
                dist = abs(c.x - p.x) + abs(c.y - p.y)
                out.append((c.name, max(5, dist // 5)))
        return sorted(out, key=lambda t: t[1])

    def _in_town(self) -> bool:
        return bool(self.state and self.state.interior
                    and self.state.interior.get("kind") == "city")

    def _shop_building(self) -> int | None:
        if not self._in_town():
            return None
        assert self.state
        doors = self.state.interior.get("shop_buildings", [])
        near = [i for i, d in enumerate(doors)
                if abs(d["x"] - self.state.player.x) + abs(d["y"] - self.state.player.y) <= 1]
        return near[0] if near else 0

    def _shop_key(self, pg, k: int) -> None:
        """Buy/sell/reforge overlay keys. Left/Right flips panels, Enter transacts."""
        from .game import shop_rows, reforge_rows, shop_reforge
        assert self.state and self.shop_open is not None
        st = self.state
        if self.shop_mode == "buy":
            rows = [(k2, it) for k2, it in (self.shop_rows_cache or shop_rows(st))]
        else:
            rows = [(-1, it) for it in st.player.inventory]
        locators = reforge_rows(st) if self.shop_mode == "reforge" else []
        if k in (pg.K_b, pg.K_ESCAPE):
            self.shop_open = None
            self.shop_rows_cache = None
            self.shop_rows_cache = None
        elif k == pg.K_UP:
            n = len(locators) if self.shop_mode == "reforge" else len(rows)
            self.shop_sel = max(0, self.shop_sel - 1)
        elif k == pg.K_DOWN:
            n = len(locators) if self.shop_mode == "reforge" else len(rows)
            self.shop_sel = max(0, min(max(0, n - 1), self.shop_sel + 1))
        elif k in (pg.K_LEFT, pg.K_RIGHT):
            order = ["buy", "sell", "reforge"]
            nxt = (order.index(self.shop_mode) + (1 if k == pg.K_RIGHT else -1)) % 3
            self.shop_mode = order[nxt]
            self.shop_sel = 0
        elif k == pg.K_RETURN:
            if self.shop_mode == "buy":
                if rows and shop_buy(st, rows[self.shop_sel][0]):
                    self.shop_rows_cache = shop_rows(
                        st, self._shop_building()) if self._in_town() else shop_rows(st)
            elif self.shop_mode == "reforge":
                if locators:
                    shop_reforge(st, locators[min(self.shop_sel, len(locators) - 1)])
            else:
                shop_sell(st, self.shop_sel)
            self.shop_sel = 0
            self.persist()

    def _confirm_typing(self) -> None:
        assert self.world
        if not self.typing:
            return
        field, buf = self.typing
        buf = buf.strip() or ("hero" if field == "char_name" else "slot2")
        self.typing = None
        if field == "char_name":
            if self.wiz is not None:
                self.wiz["name"] = buf
                self.wiz["stage"] = "race"
                self.race_idx = 0
            else:
                self.pending_name = buf
                self.race_idx = 0
        else:
            self.load_or_create("".join(c for c in buf if c.isalnum() or c in "-_") or "slot2")
            if not self.started:
                if self.just_created:
                    # fresh universe: forge its first hero before entering
                    self.roster = []
                    self.wiz = {"stage": "name"}
                    self.typing = ("char_name", "")
                    self.title_mode = "menu"
                else:
                    self.started, self.tab, self.title_mode = True, "MAP", "menu"

    # ----- drawing -----
    def _wiz_key(self, pg, k: int) -> None:
        """Title-screen hero forge: race -> calling -> attributes -> legend."""
        from .game import apply_class_package
        assert self.world and self.state
        wiz = self.wiz
        assert wiz is not None
        stage = wiz.get("stage", "race")
        if stage == "race":
            races = [r.name for r in self.world.races] or ["Human"]
            if k == pg.K_LEFT:
                self.race_idx = (self.race_idx - 1) % len(races)
            elif k == pg.K_RIGHT:
                self.race_idx = (self.race_idx + 1) % len(races)
            elif k == pg.K_RETURN:
                wiz["race"] = races[self.race_idx]
                if self.world.classes:
                    wiz["stage"] = "class"
                    self.class_idx = 0
                else:
                    wiz["stage"] = "attrs"
                    self.alloc, self.alloc_left, self.attr_idx = dict(ATTRS_BASE), 8, 0
            elif k == pg.K_ESCAPE:
                self.wiz, self.title_mode = None, "menu"
        elif stage == "class":
            classes = self.world.classes or []
            if not classes:
                wiz["stage"] = "attrs"
                self.alloc, self.alloc_left, self.attr_idx = dict(ATTRS_BASE), 8, 0
            elif k == pg.K_LEFT:
                self.class_idx = (self.class_idx - 1) % len(classes)
            elif k == pg.K_RIGHT:
                self.class_idx = (self.class_idx + 1) % len(classes)
            elif k == pg.K_RETURN:
                wiz["cls"] = classes[self.class_idx]
                wiz["stage"] = "attrs"
                self.alloc, self.alloc_left, self.attr_idx = dict(ATTRS_BASE), 8, 0
            elif k == pg.K_ESCAPE:
                wiz["stage"] = "race"
        elif stage == "attrs":
            if k == pg.K_UP:
                self.attr_idx = max(0, self.attr_idx - 1)
            elif k == pg.K_DOWN:
                self.attr_idx = min(len(ATTRS) - 1, self.attr_idx + 1)
            elif k == pg.K_LEFT:
                key = ATTRS[self.attr_idx]
                if self.alloc[key] > 1:
                    self.alloc[key] -= 1
                    self.alloc_left += 1
            elif k == pg.K_RIGHT:
                key = ATTRS[self.attr_idx]
                if self.alloc_left > 0:
                    self.alloc[key] += 1
                    self.alloc_left -= 1
            elif k == pg.K_RETURN:
                self.new_character(wiz.get("name", "hero"), wiz.get("race", "Human"),
                                   self.alloc, wiz.get("cls"))
                hero = self.roster[-1]
                if self.alloc_left:
                    hero.unspent += self.alloc_left
                self.state.player = hero
                self.active = len(self.roster) - 1
                self.alloc, self.alloc_left = None, 0
                self.pending_name, self.pending_race, self.pending_class = "", "", None
                self.wiz = None
                self.started, self.tab = True, "MAP"
                self.persist()
            elif k == pg.K_ESCAPE:
                wiz["stage"] = "class" if self.world.classes else "race"

    def _tracked(self):
        """Plot beat first, else selected rumor, else first active."""
        assert self.world
        from .plot import current_beat
        beat = current_beat(self.world)
        if beat is not None and any(q.id == beat["id"] for q in self.world.quests):
            if self.tracked_id is None:
                return next(q for q in self.world.quests if q.id == beat["id"])
        if self.tracked_id:
            hit = next((q for q in self.world.quests if q.id == self.tracked_id), None)
            if hit is not None:
                return hit
            self.tracked_id = None
        if beat is not None:
            hit = next((q for q in self.world.quests if q.id == beat["id"]), None)
            if hit is not None:
                return hit
        return self.world.quests[0] if self.world.quests else None

    def _cycle_tracked(self) -> None:
        assert self.world
        ids = [q.id for q in self.world.quests]
        if not ids:
            return
        cur = self._tracked()
        nxt = ids[(ids.index(cur.id) + 1) % len(ids)] if cur and cur.id in ids else ids[0]
        self.tracked_id = nxt
        hit = next(q for q in self.world.quests if q.id == nxt)
        self.msg = f"Tracking: {hit.title}"

    def _title_action(self, act: str) -> None:
        if act == "new":
            self.typing = ("save_name", "")
        elif act == "load":
            self.title_mode, self.sel = "load", 0
        elif act.startswith("slot:"):
            self.load_or_create(act[5:])
            self.started, self.tab, self.title_mode = True, "MAP", "menu"
        elif act == "back":
            self.title_mode = "menu"
        elif act == "quit":
            import pygame as _pg
            _pg.event.post(_pg.event.Event(_pg.QUIT))

    def _draw_title(self, screen, big, small, tiny, W, H, ACC, PANEL, BG) -> None:
        screen.fill((8, 8, 14))
        cx = W // 2
        logo = [
            " ___       _    _                           _   ___                _",
            "|_ _|_ __ | | _| |__   ___  _   _ _ __   __| | | _ \\___  __ _ _  _| |_ ___",
            " | || '_ \\| |/ / '_ \\ / _ \\| | | | '_ \\ / _` | |   / -_) _` | || |  _/ _ \\",
            "|___|_| |_|___/|_.__/ \\___/ \\__,_|_| |_|\\__,_| |_|_\\___\\__,_|\\_,_|\\__\\___/",
        ]
        y = H // 2 - 130
        for ln in logo:
            img = small.render(ln, True, ACC)
            screen.blit(img, (cx - img.get_width() // 2, y))
            y += 22
        sub = tiny.render("worlds are born from your books - every shelf is a universe",
                          True, (150, 150, 150))
        screen.blit(sub, (cx - sub.get_width() // 2, y + 8))
        y += 44
        import pygame as _pg
        self._title_rects = []
        if self.wiz is not None and self.wiz.get("stage") != "name":
            self._draw_wizard(screen, small, tiny, cx, y, ACC)
        elif self.title_mode == "load":
            saves = list_saves(self.root)
            head = small.render("LOAD GAME - pick a world (Esc: back)", True, (255, 255, 255))
            screen.blit(head, (cx - head.get_width() // 2, y))
            y += 32
            for i, sv in enumerate(saves[:8]):
                label = f"{sv['name']}  (seed {sv.get('seed')}, {sv.get('players', 0)} heroes)"
                img = small.render(label, True, ACC if i == self.sel else (200, 200, 200))
                r = _pg.Rect(cx - 260, y - 3, 520, 26)
                if i == self.sel:
                    _pg.draw.rect(screen, PANEL, r, border_radius=4)
                screen.blit(img, (cx - img.get_width() // 2, y))
                self._title_rects.append((r, f"slot:{sv['name']}"))
                y += 30
            back = tiny.render("< back >", True, (150, 150, 150))
            rb = _pg.Rect(cx - 60, y, 120, 24)
            screen.blit(back, (cx - back.get_width() // 2, y + 3))
            self._title_rects.append((rb, "back"))
        else:
            options = [("NEW GAME", "new", "birth a world from your books"),
                       ("LOAD GAME", "load", "return to a saved world"),
                       ("QUIT", "quit", "leave the realms")]
            for i, (label, act, sub_) in enumerate(options):
                img = small.render(label, True, ACC if i == self.title_sel else (200, 200, 200))
                r = _pg.Rect(cx - 200, y - 4, 400, 30)
                if i == self.title_sel:
                    _pg.draw.rect(screen, PANEL, r, border_radius=4)
                screen.blit(img, (cx - img.get_width() // 2, y))
                self._title_rects.append((r, act))
                y += 8
                s2 = tiny.render(sub_, True, (130, 130, 130))
                screen.blit(s2, (cx - s2.get_width() // 2, y))
                y += 30
        if self.typing:
            field, buf = self.typing
            box = _pg.Rect(cx - 180, H // 2 + 130, 360, 70)
            _pg.draw.rect(screen, (30, 34, 48), box, border_radius=6)
            _pg.draw.rect(screen, ACC, box, 2, border_radius=6)
            prompt = "Hero name" if self.wiz is not None else "World name"
            screen.blit(small.render(f"{prompt}: {buf}_", True, (255, 255, 255)),
                        (box.x + 16, box.y + 22))
        hint = tiny.render("Up/Down + Enter, or click - worlds are born from your books",
                           True, (130, 130, 130))
        screen.blit(hint, (cx - hint.get_width() // 2, H - 40))

    def _draw_wizard(self, screen, small, tiny, cx, y, ACC) -> None:
        from .game import ATTRS as _A
        wiz = self.wiz or {}
        stage = wiz.get("stage", "race")
        head = small.render(f"FORGE YOUR HERO - {wiz.get('name', 'nameless')} (Esc: back)",
                            True, (255, 255, 255))
        screen.blit(head, (cx - head.get_width() // 2, y))
        y += 32
        if stage == "race":
            races = [r for r in self.world.races] if self.world else []
            names = [r.name for r in races] or ["Human"]
            screen.blit(tiny.render("Choose your blood:", True, (150, 150, 150)),
                        (cx - 200, y))
            y += 22
            for i, r in enumerate(races or [None]):
                label = (r.name if r else "Human")
                mods = ""
                if r and getattr(r, "mods", None):
                    mods = "  (" + ", ".join(f"+{v} {k}" for k, v in r.mods.items()) + f" - {r.blurb})"
                c = ACC if i == self.race_idx % max(1, len(races) or 1) else (200, 200, 200)
                hl = i == self.race_idx % max(1, len(races) or 1)
                screen.blit(small.render(f"{'>' if hl else ' '} {label}{mods}"[:86],
                                         True, c), (cx - 200, y))
                y += 24
        elif stage == "class":
            classes = self.world.classes if self.world else []
            screen.blit(tiny.render(f"Choose your calling ({len(classes)} known):", True, (150, 150, 150)),
                        (cx - 200, y))
            y += 22
            lo = max(0, min(self.class_idx - 2, len(classes) - 5))
            for i in range(lo, min(len(classes), lo + 5)):
                c = classes[i]
                hl = i == self.class_idx
                screen.blit(small.render(f"{'>' if hl else ' '} {c['name']} - {c.get('desc', '')}",
                                         True, ACC if hl else (200, 200, 200)), (cx - 200, y))
                y += 24
        else:
            helps = {"STR": "damage", "CON": "health", "SPD": "escape/evade",
                     "CHA": "prices/favors", "WIS": "mana/learning", "LUK": "crits/loot"}
            screen.blit(tiny.render(f"Spend {self.alloc_left} points (Up/Down pick, Left/Right adjust, Enter begin):",
                                    True, (150, 150, 150)), (cx - 200, y))
            y += 22
            for i, key in enumerate(_A):
                c = ACC if i == self.attr_idx else (200, 200, 200)
                screen.blit(small.render(
                    f"{'>' if i == self.attr_idx else ' '} {key} {(self.alloc or {}).get(key, 4)}  ({helps[key]})",
                    True, c), (cx - 200, y))
                y += 24

    @staticmethod
    def _log_color(msg: str):
        if msg.startswith("+"):
            return (255, 215, 0)
        if msg.startswith("!"):
            return (255, 110, 110)
        if msg.startswith("x"):
            return (255, 70, 70)
        if msg.startswith("Lore:") or msg.startswith("Discovered"):
            return (140, 200, 255)
        return (215, 215, 215)

    def _draw_map(self, pg, screen, font, small, tiny, big, COLORS, VW, VH, top, TILE,
                  MW, SIDE, W, H, ACC, PANEL, BG) -> None:
        import time as _t
        assert self.state and self.world
        st, w = self.state, self.world
        p = st.player
        px, py = p.x, p.y
        inside = st.interior is not None
        shimmer = int(_t.time() * 2) % 2 == 0
        escorts = [] if inside else [q for q in w.quests if q.kind == "escort"][:1]
        _esc_ids = set() if inside else {
            q.id for q in w.quests if q.kind == "escort" and q.companion}
        comp_tiles = {(c["x"], c["y"]) for qid, c in (st.companions or {}).items()
                      if qid in _esc_ids}
        pg.draw.rect(screen, PANEL, (4, top - 4, MW + 4, VH * TILE + 8), 1, border_radius=6)
        banner = ""
        if inside:
            banner = f"-- {st.interior['site']} ({st.interior['kind']}) -- E on stairs (<) to leave"
        else:
            for c in w.cities:
                if abs(c.x - px) + abs(c.y - py) <= 1:
                    banner = f"-- {c.name} --" + (f"  est. {c.founded}" if c.founded else "")
            for s in w.sites:
                if s.x == px and s.y == py:
                    banner = f"-- {s.name} ({s.kind}) -- E to enter"
            if not banner:
                banner = region_at(w, px, py)
        if banner:
            img = small.render(banner, True, ACC)
            _bx = 8 + MW // 2 - img.get_width() // 2
            _chip = pg.Rect(_bx - 10, top - 2, img.get_width() + 20, 24)
            pg.draw.rect(screen, (18, 22, 32), _chip, border_radius=12)
            pg.draw.rect(screen, PANEL_LINE, _chip, 1, border_radius=12)
            screen.blit(img, (_bx, top + 2))
        ox, oy = px - VW // 2, py - VH // 2
        igrid, iW, iH = (st.interior["grid"], len(st.interior["grid"][0]), len(st.interior["grid"])) if inside else (None, w.width, w.height)
        for vy in range(VH):
            for vx in range(VW):
                wx, wy = ox + vx, oy + vy
                if 0 <= wx < iW and 0 <= wy < iH:
                    t = igrid[wy][wx] if inside else w.grid[wy][wx]
                    ch, col = t, COLORS.get(t, (200, 200, 200))
                    if t in ("~", ",") and shimmer:
                        col = (120, 180, 255) if t == "~" else (110, 170, 220)
                else:
                    t = " "
                    ch, col = " ", (0, 0, 0)
                kind = t
                if inside:
                    if t == "T":
                        kind = "TAB"
                else:
                    for c in w.cities:
                        if c.x == wx and c.y == wy:
                            kind = "O"
                    for s in w.sites:
                        if s.x == wx and s.y == wy:
                            kind = {"dungeon": "D", "ruin": "#", "shrine": "*"}.get(s.kind, "D")
                for e in st.enemies:
                    if e.alive and e.x == wx and e.y == wy:
                        kind = {"bandit": "E", "beast": "e", "undead": "U",
                                "soldier": "R", "spider": "a", "wraith": "g",
                                "golem": "M", "drake": "W"}.get(e.kind, "E")
                        if e.boss:
                            kind = "B"
                if inside:
                    for n in st.interior.get("npcs", []):
                        if n["x"] == wx and n["y"] == wy:
                            kind = "n"
                if wx == px and wy == py:
                    kind = "@"
                elif (wx, wy) in comp_tiles:
                    kind = "o"
                if self.settings.get("graphics", "icons") == "icons":
                    if kind == " ":
                        pg.draw.rect(screen, BG, (8 + vx * TILE, top + 4 + vy * TILE, TILE, TILE))
                    elif kind == "o":
                        _tile_icon(pg, screen, ".", 8 + vx * TILE, top + 4 + vy * TILE,
                                   TILE, wx, wy)
                        pg.draw.circle(screen, (140, 230, 255),
                                       (8 + vx * TILE + TILE // 2, top + 4 + vy * TILE + TILE // 2),
                                       max(2, TILE // 4), 1)
                    else:
                        _tile_icon(pg, screen, kind, 8 + vx * TILE, top + 4 + vy * TILE,
                                   TILE, wx, wy)
                else:
                    show = "T" if kind == "TAB" else kind
                    ch, col = show, COLORS.get(show, (200, 200, 200))
                    if kind == "o":
                        ch, col = "o", (140, 230, 255)
                    elif kind == "n":
                        ch, col = "n", (120, 200, 130)
                    elif kind == "e":
                        ch, col = "e", (230, 150, 60)
                    elif kind == "U":
                        ch, col = "U", (190, 200, 190)
                    elif kind == "R":
                        ch, col = "R", (120, 160, 220)
                    elif kind == "a":
                        ch, col = "a", (200, 130, 60)
                    elif kind == "g":
                        ch, col = "g", (150, 190, 220)
                    elif kind == "M":
                        ch, col = "M", (140, 140, 150)
                    elif kind == "W":
                        ch, col = "W", (240, 120, 50)
                    elif kind in ("<", "C"):
                        ch, col = show, ACC
                    elif kind in ("H", "I"):
                        ch, col = show, (190, 150, 90)
                    elif kind == "S":
                        ch, col = show, (120, 200, 220)
                    elif kind == "G":
                        ch, col = show, (150, 140, 110)
                    elif kind == "!":
                        ch, col = show, (220, 210, 140)
                    elif kind == "X":
                        ch, col = show, (255, 140, 80)
                    elif kind == "v":
                        ch, col = show, (140, 200, 120)
                    elif kind == "TAB":
                        ch, col = "T", (170, 158, 130)
                    elif kind in ("~", ",") and shimmer:
                        col = (120, 180, 255) if kind == "~" else (110, 170, 220)
                    elif kind == "E":
                        col = (255, 80, 80)
                    elif kind == "B":
                        col = (255, 60, 60)
                    elif kind == "@":
                        col = (255, 255, 255)
                    screen.blit(font.render(ch, True, col), (8 + vx * TILE, top + 4 + vy * TILE))
        # quest compass: ring on visible targets, gold arrow at the rim
        if not inside:
            from .game import quest_target_pos
            tracked = self._tracked()
            if tracked is not None:
                tgt = quest_target_pos(st, tracked)
                if tgt is not None:
                    tx, ty = tgt
                    vx, vy = tx - ox, ty - oy
                    if 0 <= vx < VW and 0 <= vy < VH:
                        pg.draw.circle(screen, ACC,
                                       (8 + vx * TILE + TILE // 2, top + 4 + vy * TILE + TILE // 2),
                                       TILE // 2 - 1, 2)
                    else:
                        import math as _m
                        ang = _m.atan2(ty - py, tx - px)
                        ex = ox + VW // 2 + int(_m.cos(ang) * (VW // 2 - 1))
                        ey = oy + VH // 2 + int(_m.sin(ang) * (VH // 2 - 1))
                        ex = max(ox, min(ox + VW - 1, ex))
                        ey = max(oy, min(oy + VH - 1, ey))
                        cxp, cyp = 8 + (ex - ox) * TILE + TILE // 2, top + 4 + (ey - oy) * TILE + TILE // 2
                        dxn, dyn = _m.cos(ang), _m.sin(ang)
                        pxn, pyn = -dyn, dxn
                        pg.draw.polygon(screen, ACC,
                                        [(cxp + dxn * 9, cyp + dyn * 9),
                                         (cxp + pxn * 6 - dxn * 5, cyp + pyn * 6 - dyn * 5),
                                         (cxp - pxn * 6 - dxn * 5, cyp - pyn * 6 - dyn * 5)])
                        dist = abs(tx - px) + abs(ty - py)
                        img = tiny.render(f"{tracked.title[:24]} {dist} leagues", True, ACC)
                        screen.blit(img, (min(max(8, cxp - img.get_width() // 2), MW - img.get_width()), top + VH * TILE - 16))
        # floating numbers + hit flashes decay here, one tick per frame
        for fl in list(st.floaters):
            wx, wy = fl["x"] - ox, fl["y"] - oy
            if 0 <= wx < VW and 0 <= wy < VH:
                img = small.render(fl["text"], True, fl["color"])
                screen.blit(img, (8 + wx * TILE + 4, top + 4 + wy * TILE - (26 - fl["ttl"])))
            fl["ttl"] -= 1
            if fl["ttl"] <= 0:
                st.floaters.remove(fl)
        for fl in list(st.flashes):
            wx, wy = fl["x"] - ox, fl["y"] - oy
            if 0 <= wx < VW and 0 <= wy < VH and fl["ttl"] > 4:
                s = pg.Surface((TILE, TILE))
                s.set_alpha(120)
                s.fill(fl["color"])
                screen.blit(s, (8 + wx * TILE, top + 4 + wy * TILE))
            fl["ttl"] -= 1
            if fl["ttl"] <= 0:
                st.flashes.remove(fl)
        sx = MW + 14
        sw = SIDE - 20
        y = top + 2
        _status_pills = []
        if p.shield:
            _status_pills.append((f"+{p.shield} ward", (120, 200, 220)))
        if getattr(p, "poison", 0):
            _status_pills.append((f"POISON {p.poison}", (110, 220, 130)))
        if getattr(p, "bleed", 0):
            _status_pills.append((f"BLEED {p.bleed}", (235, 120, 120)))
        if getattr(p, "guarding", False):
            _status_pills.append(("GUARD", (140, 170, 255)))
        if getattr(p, "winded", False):
            _status_pills.append(("WINDED", (240, 180, 90)))
        _card_h = 124 + (22 if _status_pills else 0) + (22 if getattr(p, "buffs", None) else 0)
        _panel(pg, screen, pg.Rect(sx - 6, y - 4, sw + 12, _card_h))
        screen.blit(small.render(f"{p.name}", True, (255, 255, 255)), (sx, y))
        y += 22
        calling = f" {p.class_name}" if getattr(p, "class_name", "") else ""
        screen.blit(tiny.render(f"{p.race}{calling}  ·  Lv {p.level}",
                                True, TEXT_DIM), (sx, y))
        y += 18
        screen.blit(tiny.render(f"{p.gold} gold  ·  ({px},{py})  ·  {clock_str(w.clock)}",
                                True, TEXT_DIM), (sx, y))
        y += 18
        from .worldgen import faction_name as _fname
        _oath = _fname(w, p.oath) if getattr(p, "oath", "") else "none"
        screen.blit(tiny.render(f"AGE {w.age}  ·  OATH [O] {_oath[:24]}", True, TEXT_DIM), (sx, y))
        y += 22
        _bar(pg, screen, sx, y, sw, 16, max(0, p.hp) / max(1, eff_max_hp(p)),
             (214, 72, 72), (58, 22, 26),
             f"{max(0,p.hp)} / {eff_max_hp(p)}", tiny)
        y += 20
        y += _pills(pg, screen, sx, y, _status_pills, tiny)
        _bar(pg, screen, sx, y, sw, 12, p.mana / max(1, p.max_mana),
             (120, 130, 245), (24, 28, 58),
             f"Mana {p.mana}/{p.max_mana}  ·  [C] {len(getattr(p, 'spells', []))}", tiny)
        y += 20
        if getattr(p, "buffs", None):
            y += _pills(pg, screen, sx, y,
                        [(f"{k} {v}", (150, 230, 150)) for k, v in p.buffs.items()],
                        tiny)
        tracked = self._tracked()
        if tracked is not None:
            screen.blit(tiny.render(f"TRACKED [T]  {tracked.title[:34]}",
                                    True, ACC), (sx, y))
            y += 18
        bow = f"  ·  bow {p.ammo}" if ((p.equipment or {}).get("weapon") or {}).get("ranged") else ""
        _bar(pg, screen, sx, y, sw, 12, p.xp / max(1, p.xp_needed),
             (90, 160, 255), (24, 30, 54),
             f"Lv {p.level}  ·  ATK {eff_atk(p)}{bow}  ·  {p.quests_done} tales", tiny)
        y += 24
        from .plot import current_beat
        plot = getattr(w, "plot", None) or {}
        tales: list = []
        if plot.get("beat_ids"):
            if plot.get("done"):
                tales.append((f"MAIN {plot.get('title', '')} — COMPLETE", ACC, small, 20))
            else:
                beat = current_beat(w)
                acts = plot.get("acts", [])
                act_name = acts[beat["act"] - 1] if beat and 1 <= beat.get("act", 0) <= len(acts) else ""
                tales.append((f"MAIN {plot.get('title', '')}", ACC, small, 20))
                if beat:
                    tgt = beat.get("target_city") or beat.get("target_site") or beat.get("target_enemy", "")
                    tales.append((f"> {beat.get('title', '')[:40]}", (255, 215, 120), tiny, 18))
                    tales.append((f"  {act_name} · {tgt[:34]}", TEXT_DIM, tiny, 18))
        tales.append((f"TALES {len(w.quests)} active · {len(w.completed_quests)} told  [J]",
                      ACC, small, 22))
        escorts = [q for q in w.quests if q.kind == "escort"][:2]
        for q in escorts:
            from .game import companion_line
            tales.append((companion_line(st, q)[:46], (140, 230, 255), tiny, 18))
        icons = {"deliver": ">", "bounty": "x", "explore": "?",
                 "escort": "=", "hunt": "+", "tribute": "$",
                 "relic": "%", "finale": "X", "pilgrimage": "P", "treasure": "T"}
        today = w.clock // 1440
        for q in w.quests[:3]:
            head = f"{icons.get(q.kind,'-')} {q.title[:38]}"
            if q.kind == "hunt":
                head += f" ({q.progress}/{q.amount})"
            if q.deadline_day:
                left = q.deadline_day - today
                head += f" ({left}d!)" if left > 1 else " (LAST DAY!)"
            tales.append((head, (255, 150, 150) if q.deadline_day else (220, 220, 220),
                          tiny, 18))
            tgt = q.target_city or q.target_site or q.target_enemy
            if q.kind == "treasure":
                tgt = f"the X at ({q.target_x},{q.target_y})"
            extra = ""
            if q.kind == "bounty" and q.target_site:
                extra = f" @ {q.target_site[:20]}"
            if q.kind == "pilgrimage":
                extra = f" ({q.progress}/{q.amount})"
            tales.append((f"  → {tgt[:36]}{extra}  +{q.reward_gold}g", TEXT_DIM, tiny, 18))
        if len(w.quests) > 3:
            tales.append((f"… +{len(w.quests) - 3} more in journal (J)", TEXT_DIM, tiny, 18))
        if w.dormant_quests:
            tales.append((f"… +{len(w.dormant_quests)} unheard — ask in towns (E)",
                           TEXT_DIM, tiny, 18))
        _panel(pg, screen, pg.Rect(sx - 6, y - 4, sw + 12,
                                   sum(h for _, _, _, h in tales) + 16))
        y += 4
        for text, color, font, h in tales:
            screen.blit(font.render(text, True, color), (sx, y))
            y += h
        y += 8
        mw, mh = sw, 110
        _panel(pg, screen, pg.Rect(sx - 6, y - 4, sw + 12, mh + 30))
        screen.blit(tiny.render("REALM", True, TEXT_DIM), (sx, y))
        y += 16
        mm_key = (w.seed, w.width, w.height, mw, mh)
        if self._mm_key != mm_key or self._mm_base is None:
            base = pg.Surface((mw, mh))
            base.fill((0, 0, 0))
            for yy in range(w.height):
                for xx in range(w.width):
                    t = w.grid[yy][xx]
                    if t in ("~", ","):
                        c = (40, 90, 200)
                    elif t == "r":
                        c = (90, 150, 220)
                    elif t == "s":
                        c = (150, 130, 95)
                    elif t == "T":
                        c = (40, 120, 60)
                    elif t == "^":
                        c = (120, 120, 130)
                    elif t == "O":
                        c = ACC
                    elif t in ("D", "#", "*"):
                        c = (190, 120, 255)
                    elif t == "!":
                        c = (220, 210, 140)
                    elif t == "X":
                        c = (255, 140, 80)
                    elif t == "v":
                        c = (140, 200, 120)
                    elif t == "=":
                        c = (150, 120, 70)
                    else:
                        continue
                    base.set_at((1 + int(xx / w.width * (mw - 2)),
                                 1 + int(yy / w.height * (mh - 2))), c)
            self._mm_base, self._mm_key = base, mm_key
        screen.blit(self._mm_base, (sx, y))
        y += mh + 8
        # viewport frame + player dot (underground: mark the hole instead)
        if inside:
            site = next((s for s in w.sites if s.name == st.interior["site"]), None)
            if site is not None:
                pg.draw.circle(screen, (255, 255, 255),
                               (sx + int(site.x / w.width * (mw - 2)) + 1,
                                y + int(site.y / w.height * (mh - 2)) + 1), 3)
                pg.draw.circle(screen, ACC,
                               (sx + int(site.x / w.width * (mw - 2)) + 1,
                                y + int(site.y / w.height * (mh - 2)) + 1), 3, 1)
        else:
            vx0 = max(0, min(mw - 3, int(ox / w.width * mw)))
            vy0 = max(0, min(mh - 3, int(oy / w.height * mh)))
            pg.draw.rect(screen, (200, 200, 200),
                         (sx + vx0, y + vy0,
                          max(3, int(VW / w.width * mw)), max(3, int(VH / w.height * mh))), 1)
            screen.set_at((sx + int(px / w.width * (mw - 2)) + 1,
                           y + int(py / w.height * (mh - 2)) + 1), (255, 255, 255))
            # rumor dots: gold for tracked, dim for the rest
            from .game import quest_target_pos as _qtp
            tracked = self._tracked()
            for q in w.quests[:14]:
                pos = _qtp(st, q)
                if pos is None:
                    continue
                col = ACC if tracked is not None and q.id == tracked.id else (120, 120, 130)
                screen.set_at((sx + int(pos[0] / w.width * (mw - 2)) + 1,
                               y + int(pos[1] / w.height * (mh - 2)) + 1), col)
        y += mh + 8
        _legend = []
        if inside:
            _legend.append("H house · I inn · S shop · G gate · n folk · @ you")
        elif not self.show_legend:
            _legend.append("L legend · J journal · T track quest")
        elif self.settings.get("graphics", "icons") == "icons":
            _legend.append("gold roof city · purple dungeon · columns ruin")
            _legend.append("diamond shrine · brown road · red blade, amber beast")
            _legend.append("spider, pale dead+wraith, gray golem, drake, steel soldier, boss")
        else:
            _legend.append("O city · D dungeon · # ruin · * shrine · = road · ! tower · X camp · v farm")
            _legend.append("E blade · e beast · a spider · U dead · g wraith · M golem · W drake · R soldier · B boss")
        _panel(pg, screen, pg.Rect(sx - 6, y - 4, sw + 12, 16 * len(_legend) + 12))
        for _line in _legend:
            screen.blit(tiny.render(_line, True, TEXT_DIM), (sx, y))
            y += 16
        base = top + VH * TILE + 8
        _panel(pg, screen, pg.Rect(4, base - 4, MW + 4, 134))
        if st.in_combat_with:
            e = st.in_combat_with
            warn = " -- HEAVY INCOMING! Defend (D)!" if e.windup else ""
            rage = " ENRAGED" if e.enraged else ""
            screen.blit(small.render(
                f"COMBAT {e.name[:40]} ({max(0,e.hp)}hp){rage}{warn}", True, (255, 110, 110)), (8, base))
            screen.blit(small.render(
                "A atk - H heavy - Q quick - D defend - R shoot - P B V U use - F flee - C spells",
                True, (170, 170, 170)), (8, base + 20))
            for i, m in enumerate(st.messages[-4:]):
                screen.blit(small.render(m[:86], True, self._log_color(m)), (8, base + 42 + i * 20))
        elif p.hp <= 0:
            screen.blit(small.render("YOU FELL -- press R to rise at the nearest city (half gold)",
                                     True, (255, 70, 70)), (8, base))
        else:
            hint = ("WASD/arrows move - E stairs/tablets - C spells - J journal"
                    if inside else
                    "WASD move - E talk/enter - R shoot (bow 2-4) - U quiver - O oath - H heal - Z rest - B shop - F caravan - C spells - T track - J journal")
            screen.blit(small.render(hint, True, (170, 170, 170)), (8, base))
        for i, m in enumerate(st.messages[-5:]):
            screen.blit(small.render(m[:86], True, self._log_color(m)), (8, base + 22 + i * 20))
        if self.journal:
            rows = max(1, min(8, len(w.quests)))
            plot = getattr(w, "plot", None) or {}
            extra = (46 + 18 * min(8, len(plot.get("beats", [])))) if plot.get("beat_ids") else 0
            box_h = min(560, 60 + 30 * rows + (20 if w.dormant_quests else 0) + extra)
            box = pg.Rect(MW // 2 - 260, top + 40, 520, box_h)
            _panel(pg, screen, box)
            pg.draw.rect(screen, ACC, box, 2, border_radius=8)
            screen.blit(small.render(f"JOURNAL -- {len(w.completed_quests)} tales told  (J to close)",
                                     True, ACC), (box.x + 16, box.y + 10))
            yy = box.y + 38
            plot = getattr(w, "plot", None) or {}
            if plot.get("beat_ids"):
                from .plot import current_beat
                cur = current_beat(w)
                screen.blit(small.render(f"MAIN: {plot.get('title', '')}"
                                         + (" - COMPLETE" if plot.get("done") else ""),
                                         True, ACC), (box.x + 16, yy))
                yy += 20
                for b in plot.get("beats", [])[:8]:
                    mark = "x" if b["id"] in w.completed_quests else (">" if cur and b["id"] == cur["id"] else "-")
                    screen.blit(tiny.render(f"  [{mark}] {b.get('title', '')[:56]}",
                                            True, (220, 220, 220) if mark != "-" else (130, 130, 140)),
                                (box.x + 16, yy))
                    yy += 18
                yy += 6
            for q in w.quests[:8]:
                urg = ""
                if q.deadline_day:
                    left = q.deadline_day - w.clock // 1440
                    urg = f" [{left}d]" if left > 1 else " [LAST DAY]"
                screen.blit(small.render(f"[{q.kind}]{urg} {q.title[:52]}", True, (255, 255, 255)),
                            (box.x + 16, yy))
                yy += 20
                screen.blit(tiny.render(f"   {q.flavor[:72]}", True, (170, 170, 170)), (box.x + 16, yy))
                yy += 20
            if w.dormant_quests:
                screen.blit(tiny.render(f"... {len(w.dormant_quests)} unheard rumors (talk (E) in towns)",
                                        True, (150, 150, 150)), (box.x + 16, yy))
        if self.shop_open is not None:
            self._draw_shop(pg, screen, small, tiny, MW, top, ACC)
        if self.caravan_open:
            self._draw_caravan(pg, screen, small, tiny, MW, top, ACC)
        if self.spellbook_open:
            self._draw_spells(pg, screen, small, tiny, MW, top, ACC)
        if self.oath_open:
            self._draw_oath(pg, screen, small, tiny, MW, top, ACC)
        if w.ending:
            box = pg.Rect(MW // 2 - 300, top + VH * TILE // 2 - 70, 600, 130)
            pg.draw.rect(screen, (20, 18, 10), box, border_radius=8)
            pg.draw.rect(screen, ACC, box, 2, border_radius=8)
            screen.blit(small.render("AN AGE ENDS — the realm goes on", True, ACC),
                        (box.x + 16, box.y + 12))
            screen.blit(small.render(w.ending[:86], True, (255, 255, 255)),
                        (box.x + 16, box.y + 40))
            screen.blit(tiny.render("The annals record it (see DATA). Play continues.",
                                    True, (170, 170, 170)), (box.x + 16, box.y + 70))
            screen.blit(tiny.render("(Enter to ride on)", True, (150, 150, 150)),
                        (box.x + 16, box.y + 94))
        if p.hp <= 0:
            shade = pg.Surface((MW, VH * TILE))
            shade.set_alpha(150)
            shade.fill((40, 0, 0))
            screen.blit(shade, (8, top))
            t1 = big.render("YOU FELL", True, (255, 80, 80))
            screen.blit(t1, (8 + MW // 2 - t1.get_width() // 2, top + VH * TILE // 2 - 50))
            t2 = small.render("Press R to rise at the nearest city", True, (255, 255, 255))
            screen.blit(t2, (8 + MW // 2 - t2.get_width() // 2, top + VH * TILE // 2 + 10))

    def _draw_chars(self, pg, screen, small, tiny, top, H, ACC, PANEL) -> None:
        from .game import ATTRS as _A
        y = top + 10
        screen.blit(small.render(f"CHARACTERS of {self.save_name} - Enter switch, N new, D delete, Tab attributes", True, (255, 255, 255)), (12, y))
        y += 26
        if self.roster:
            from .perks import drafts_pending as _pend
            pend = max((_pend(h) for h in self.roster), default=0)
            if pend:
                screen.blit(small.render(f"+ {pend} PERK DRAFT WAITS (P to open)",
                                         True, ACC), (12, y))
                y += 26
        y += 30
        if self.alloc is not None:
            screen.blit(small.render(
                f"{self.pending_name} ({self.pending_race}) - spend {self.alloc_left} points: Up/Down pick, Left/Right adjust, Enter done",
                True, ACC), (12, y))
            y += 28
            helps = {"STR": "damage", "CON": "health", "SPD": "escape/evade",
                     "CHA": "prices/favors", "WIS": "faster learning", "LUK": "crits/loot"}
            for i, key in enumerate(_A):
                c = ACC if i == self.attr_idx else (200, 200, 200)
                screen.blit(small.render(
                    f"{'>' if i == self.attr_idx else ' '} {key} {self.alloc.get(key, 4)}  ({helps[key]})",
                    True, c), (24, y))
                y += 24
            return
        if self.pending_class is False:
            classes = self.world.classes if self.world else []
            screen.blit(small.render(f"{self.pending_name} ({self.pending_race}) - choose a calling ({len(classes)} known): Left/Right, Enter, Esc back",
                                     True, ACC), (12, y))
            y += 26
            lo = max(0, min(self.class_idx - 2, len(classes) - 5))
            for i in range(lo, min(len(classes), lo + 5)):
                c = classes[i]
                hl = i == self.class_idx
                screen.blit(small.render(
                    f"{'>' if hl else ' '} {c['name']} - {c.get('desc', '')}",
                    True, ACC if hl else (200, 200, 200)), (24, y))
                y += 24
            return
        if self.pending_name and self.pending_class is None:  # race-pick mode
            races = [r.name for r in self.world.races] or ["Human"]
            screen.blit(small.render(f"Name: {self.pending_name} - Left/Right blood, Enter confirm, Esc cancel", True, ACC), (12, y))
            y += 26
            for i, r in enumerate(races):
                c = ACC if i == self.race_idx % len(races) else (200, 200, 200)
                blood = next((x for x in self.world.races if x.name == r), None)
                mods = ""
                if blood is not None and getattr(blood, "mods", None):
                    mods = "  (" + ", ".join(f"+{v} {k}" for k, v in blood.mods.items()) + ")"
                screen.blit(small.render(f"{'>' if i == self.race_idx % len(races) else ' '} {r}{mods}"[:86],
                                         True, c), (24, y))
                y += 24
            return
        for i, p in enumerate(self.roster):
            bg = PANEL if i != self.sel else (40, 46, 64)
            r = pg.Rect(12, y, 700, 26)
            pg.draw.rect(screen, bg, r, border_radius=4)
            mark = "*" if i == self.active else " "
            pts = f" +{p.unspent}pts" if p.unspent else ""
            cls = f" {p.class_name}" if getattr(p, "class_name", "") else ""
            screen.blit(small.render(
                f"{mark} {p.name} | {p.race}{cls} Lv{p.level} | HP {p.hp}/{p.max_hp} ATK {p.atk} Gold {p.gold} Q{p.quests_done}{pts}",
                True, ACC if i == self.active else (220, 220, 220)), (20, y + 4))
            y += 30
        # detail panel for the selected hero
        if 0 <= self.sel < len(self.roster):
            p = self.roster[self.sel]
            y += 6
            title = "ATTRIBUTES (Tab: roster/attrs, Right: spend point)" if self.attr_focus else "ATTRIBUTES (Tab to spend level points)"
            screen.blit(small.render(title, True, ACC if self.attr_focus else (255, 255, 255)), (12, y))
            y += 24
            helps = {"STR": "damage", "CON": "health", "SPD": "escape/evade",
                     "CHA": "prices/favors", "WIS": "faster learning", "LUK": "crits/loot"}
            for i, key in enumerate(_A):
                hl = self.attr_focus and i == self.attr_idx
                screen.blit(small.render(
                    f"{'>' if hl else ' '} {key} {p.attr(key)}  ({helps[key]})",
                    True, ACC if hl else (200, 200, 200)), (24, y))
                y += 22
            y += 4
            screen.blit(small.render("SKILLS (improve with use, gear adds levels)", True, (255, 255, 255)), (12, y))
            y += 24
            from .items import eff_skill
            shelps = {"blades": "damage (fight)", "speech": "rewards (talk/quests)",
                      "survival": "rest/camp (rest)", "lore": "learning (explore)",
                      "sneak": "unseen (night/prowl)", "salvage": "richer drops (loot)",
                      "medicine": "stronger healing", "arcana": "cheaper spells"}
            for key in ("blades", "speech", "survival", "lore", "sneak", "salvage",
                        "medicine", "arcana"):
                lv, base = eff_skill(p, key), p.skill_level(key)
                tag = f" {lv} (+{lv - base} gear)" if lv > base else f" {lv}"
                screen.blit(small.render(
                    f"  {key.capitalize()}{tag}  [{p.skills.get(key, 0)}xp]  ({shelps[key]})",
                    True, (200, 200, 200)), (24, y))
                y += 22
            y += 4
            from .perks import _ranks as _perk_ranks
            held = _perk_ranks(getattr(p, "perks", []))
            screen.blit(small.render(
                "PERKS - a draft every 5th level (P to open)",
                True, (255, 255, 255)), (12, y))
            y += 24
            if held:
                for base, rank in sorted(held.items()):
                    screen.blit(small.render(
                        f"  {base} rank {rank}",
                        True, (200, 200, 200)), (24, y))
                    y += 22
            else:
                screen.blit(small.render("  (none yet - the 5th level deals first)",
                                         True, (150, 150, 150)), (24, y))
                y += 22
        if self.draft_open and 0 <= self.sel < len(self.roster):
            self._draw_draft(pg, screen, small, tiny, ACC)
        screen.blit(tiny.render("Each save keeps its own roster. Switching swaps the @ on the map.", True, (150, 150, 150)), (12, H - 44))

    def _draw_draft(self, pg, screen, small, tiny, ACC) -> None:
        from .perks import draft_offer
        assert self.state
        hero = self.roster[self.sel]
        rows = draft_offer(self.state, hero)
        box = pg.Rect(60, 120, 680, min(460, 130 + 40 * max(1, len(rows))))
        _panel(pg, screen, box)
        pg.draw.rect(screen, ACC, box, 2, border_radius=8)
        screen.blit(small.render(
            f"DRAFT for {hero.name} (take ONE - the rest dissolve)  (1-4 take, P close)",
            True, ACC), (box.x + 16, box.y + 10))
        screen.blit(tiny.render("Three speak your calling; the last is wild.",
                                True, (150, 150, 150)), (box.x + 16, box.y + 34))
        yy = box.y + 58
        for i, e in enumerate(rows[:4]):
            tag = "WILD" if e["tag"] == "wild" else e["tag"].upper()
            held = f" (held rank {e['held']} -> {e['held'] + 1})" if e["held"] else ""
            screen.blit(small.render(
                f"[{i + 1}] {e['name']} [{tag}]{held} - {e['flavor']}",
                True, (255, 255, 255)), (box.x + 16, yy))
            yy += 40
        if not rows:
            screen.blit(small.render("  (the pool is drunk dry - every frame mastered)",
                                     True, (170, 170, 170)), (box.x + 16, yy))

    def _draw_spells(self, pg, screen, small, tiny, MW, top, ACC) -> None:
        assert self.state and self.world
        st = self.state
        known = self._known_spells()
        box = pg.Rect(MW // 2 - 260, top + 30, 520, min(520, 100 + 40 * max(1, len(known))))
        pg.draw.rect(screen, (14, 16, 32), box, border_radius=8)
        pg.draw.rect(screen, (120, 120, 255), box, 2, border_radius=8)
        screen.blit(small.render(f"SPELLBOOK - {st.player.mana}/{st.player.max_mana} mana  (1-9 cast, C close)",
                                 True, (150, 150, 255)), (box.x + 16, box.y + 10))
        screen.blit(tiny.render("Shrines (*) teach the spells you lack. Arcana cheapens every casting.",
                                True, (150, 150, 150)), (box.x + 16, box.y + 34))
        yy = box.y + 58
        for i, s in enumerate(known[:9]):
            if s["id"] == "bloodprice":
                cost_txt, ok = "half blood", st.player.hp > 10
            else:
                cost_txt = f"{s['cost']} mana"
                ok = st.player.mana >= max(1, s["cost"] - st.player.skills.get("arcana", 0) // 25 // 3)
            screen.blit(small.render(f"[{i + 1}] {s['name']} ({cost_txt}) - {s['desc'][:52]}",
                                      True, (255, 255, 255) if ok else (110, 110, 130)),
                        (box.x + 16, yy))
            yy += 40
        if not known:
            screen.blit(small.render("  (empty - seek a shrine)", True, (170, 170, 170)), (box.x + 16, yy))

    def _draw_caravan(self, pg, screen, small, tiny, MW, top, ACC) -> None:
        assert self.state
        dests = self._caravan_dests()
        box = pg.Rect(MW // 2 - 260, top + 60, 520, min(420, 110 + 26 * max(1, min(10, len(dests)))))
        _panel(pg, screen, box)
        pg.draw.rect(screen, ACC, box, 2, border_radius=8)
        screen.blit(small.render(f"CARAVANS - {self.state.player.gold}g  (Enter ride, F close)",
                                 True, ACC), (box.x + 16, box.y + 10))
        screen.blit(tiny.render("The roads are faster than boots. Mostly safer, too.",
                                True, (150, 150, 150)), (box.x + 16, box.y + 34))
        yy = box.y + 58
        for i, (name, fare) in enumerate(dests[:10]):
            hl = i == self.caravan_sel
            screen.blit(small.render(f"{'>' if hl else ' '} {name}  ({fare}g)",
                                     True, ACC if hl else (255, 255, 255)), (box.x + 16, yy))
            yy += 26
        if not dests:
            screen.blit(small.render("  (no road-songs yet - walk to new cities first)",
                                     True, (170, 170, 170)), (box.x + 16, yy))

    def _draw_oath(self, pg, screen, small, tiny, MW, top, ACC) -> None:
        from .game import faction_rows
        assert self.state and self.world
        rows = faction_rows(self.state)
        box = pg.Rect(MW // 2 - 280, top + 50, 560, min(460, 120 + 26 * max(1, len(rows))))
        _panel(pg, screen, box)
        pg.draw.rect(screen, ACC, box, 2, border_radius=8)
        screen.blit(small.render(f"OATHS - age {self.world.age}  (Enter swear/forswear, O close)",
                                 True, ACC), (box.x + 16, box.y + 10))
        screen.blit(tiny.render("Sworn blades know you; rivals watch for you. "
                                "Bleed a side's foes to end its war.",
                                True, (150, 150, 150)), (box.x + 16, box.y + 34))
        yy = box.y + 58
        for i, r in enumerate(rows):
            hl = i == self.oath_sel
            mark = "*" if r["oath"] else " "
            war = f" vs {', '.join(r['foes'][:2])}" if r["foes"] else " at peace"
            tide = self.world.war_tide.get(r["id"], 0)
            screen.blit(small.render(
                f"{'>' if hl else ' '}{mark} {r['name'][:30]} ({r['cities']} towns, "
                f"standing {r['standing']}){war[:34]} [tide {tide}]",
                True, ACC if hl else (255, 255, 255)), (box.x + 16, yy))
            yy += 26
        if not rows:
            screen.blit(small.render("  (no powers hold towns)", True, (170, 170, 170)),
                        (box.x + 16, yy))

    def _draw_shop(self, pg, screen, small, tiny, MW, top, ACC) -> None:
        from .game import shop_rows, reforge_rows
        from .items import reforge_cost, REFORGE_MAX
        assert self.state and self.shop_open is not None
        st = self.state
        if self.shop_mode == "buy":
            rows = [(k2, it) for k2, it in (self.shop_rows_cache or shop_rows(st))]
        else:
            rows = [(-1, it) for it in st.player.inventory]
        if self.shop_mode == "reforge":
            from .items import SLOTS
            bench: list[tuple[str, dict]] = []
            for slot in SLOTS:
                worn = (st.player.equipment or {}).get(slot)
                if worn:
                    bench.append((f"worn {slot}", worn))
            for it in st.player.inventory:
                bench.append(("pack", it))
            rows = [(-1, it) for _tag, it in bench]
            tags = [tag for tag, _it in bench]
        else:
            tags = []
        box = pg.Rect(MW // 2 - 280, top + 50, 560, min(460, 110 + 24 * max(1, min(12, len(rows)))))
        _panel(pg, screen, box)
        pg.draw.rect(screen, ACC, box, 2, border_radius=8)
        if self.shop_mode == "buy":
            tab = "BUY"
        elif self.shop_mode == "reforge":
            tab = f"REFORGE (raise a tier, cap {REFORGE_MAX})"
        else:
            tab = "SELL (half price)"
        screen.blit(small.render(f"{self.shop_open} MARKET - {tab} - {st.player.gold}g  (Left/Right flip, Enter deal, B close)",
                                 True, ACC), (box.x + 16, box.y + 10))
        yy = box.y + 38
        for i, (_ri, item) in enumerate(rows[:12]):
            hl = i == self.shop_sel
            if self.shop_mode == "buy":
                price = item.get("value", 0)
                note = f"{price}g"
            elif self.shop_mode == "reforge":
                if (item.get("kind") or "") == "consumable" or not item.get("slot"):
                    note = "no hammer"
                elif int(item.get("tier", 1)) >= REFORGE_MAX:
                    note = "MAX"
                else:
                    note = f"{reforge_cost(item)}g -> tier {int(item.get('tier', 1)) + 1}"
            else:
                note = f"{max(1, int(item.get('value', 0)) // 2)}g"
            label = f"{tags[i]}: {item_line(item)}" if self.shop_mode == "reforge" else item_line(item)
            screen.blit(small.render(f"{'>' if hl else ' '} {label}"[:86],
                                     True, ACC if hl else (255, 255, 255)), (box.x + 16, yy))
            yy += 20
            screen.blit(tiny.render(f"     {note}", True, (170, 170, 170)), (box.x + 16, yy))
            yy += 4
        if not rows:
            empty = {"buy": "  (empty)", "sell": "  (pack empty - unequip worn gear first)",
                     "reforge": "  (no steel to hammer - buy or loot first)"}[self.shop_mode]
            screen.blit(small.render(empty, True, (170, 170, 170)), (box.x + 16, yy))

    def _draw_inventory(self, pg, screen, small, tiny, top, H, ACC, PANEL) -> None:
        assert self.state
        p = self.state.player
        y = top + 10
        screen.blit(small.render(
            f"INVENTORY of {p.name} - {p.gold}g - eff ATK {eff_atk(p)} / HP {eff_max_hp(p)}",
            True, (255, 255, 255)), (12, y))
        y += 26
        screen.blit(small.render("WORN (Enter: take off)", True, ACC), (12, y))
        y += 22
        for i, slot in enumerate(SLOTS):
            worn = (p.equipment or {}).get(slot)
            hl = i == self.inv_sel
            bg = (40, 46, 64) if hl else PANEL
            r = pg.Rect(12, y, 760, 24)
            pg.draw.rect(screen, bg, r, border_radius=4)
            screen.blit(small.render(
                f"{'>' if hl else ' '} {slot:6} : {item_line(worn) if worn else '-- bare --'}",
                True, ACC if hl else (220, 220, 220)), (20, y + 3))
            y += 27
        y += 6
        screen.blit(small.render(f"PACK ({len(p.inventory)}/40 - Enter: wear/use, D: destroy, B in town: trade)",
                                 True, ACC), (12, y))
        y += 22
        for j, item in enumerate(p.inventory[:24]):
            hl = len(SLOTS) + j == self.inv_sel
            c = ACC if hl else (200, 200, 200)
            screen.blit(small.render(f"{'>' if hl else ' '} {item_line(item)}", True, c), (24, y))
            y += 22
        if len(p.inventory) > 24:
            screen.blit(tiny.render(f"... and {len(p.inventory) - 24} more", True, (150, 150, 150)), (24, y))
        screen.blit(tiny.render("Sell pack goods at city shops (B on the map). Worn gear must come off first.",
                                True, (150, 150, 150)), (12, H - 44))

    def _draw_data(self, screen, small, tiny, top, H, ACC, PANEL) -> None:
        from .worldgen import provenance_rows
        assert self.world
        rows = provenance_rows(self.world)
        born = sum(1 for _, o, _ in rows if o)
        y = top + 10
        st = self.world.stats or {}
        screen.blit(small.render(
            f"SAGA - {st.get('sessions', 0)} sessions, {st.get('minutes', 0)} min played | "
            f"{st.get('kills', 0)} kills, {st.get('deaths', 0)} deaths, "
            f"{st.get('quests', 0)} quests, {st.get('levels', 0)} levels",
            True, ACC), (12, y))
        y += 26
        screen.blit(small.render(
            f"DATA - book-born {born}/{len(rows)} shown - Up/Down scrolls - gold = from your books, dim = winds-invented",
            True, (255, 255, 255)), (12, y))
        y += 28
        per_page = max(1, (H - top - 120) // 22)
        self.sel = max(0, min(max(0, len(rows) - per_page), self.sel))
        last_sec = ""
        for i in range(self.sel, min(len(rows), self.sel + per_page)):
            sec, orig, became = rows[i]
            if sec != last_sec:
                screen.blit(small.render(sec, True, ACC), (12, y))
                y += 22
                last_sec = sec
            if orig:
                screen.blit(small.render(f"  {orig}  ->  {became}"[:100], True, (255, 215, 120)), (12, y))
            else:
                screen.blit(small.render(f"  ~ winds ~  ->  {became}"[:100], True, (130, 130, 140)), (12, y))
            y += 22
        screen.blit(tiny.render(f"{self.sel + 1}-{min(len(rows), self.sel + per_page)} of {len(rows)}",
                                True, (150, 150, 150)), (12, H - 44))

    def _draw_books(self, screen, small, tiny, top, H, ACC) -> None:
        y = top + 10
        screen.blit(small.render(f"BOOKS ({len(self.book_files)}) - R regenerate world, O open folder", True, (255, 255, 255)), (12, y))
        y += 30
        for f in self.book_files[:18]:
            try:
                sz = f.stat().st_size // 1024
            except Exception:
                sz = 0
            screen.blit(small.render(f"{f.suffix.upper()[1:]:4}  {f.name}  ({sz}kb)", True, (220, 220, 220)), (24, y))
            y += 24
        if self.world:
            screen.blit(tiny.render(
                f"World {self.world.width}x{self.world.height} seed {self.world.seed}: "
                f"{len(self.world.cities)} cities, {len(self.world.sites)} sites, "
                f"{len(self.world.regions)} regions, {len(self.world.quests)} active / "
                f"{len(self.world.dormant_quests)} unheard / {len(self.world.completed_quests)} done",
                True, (150, 150, 150)), (12, H - 44))

    def _draw_saves(self, screen, small, tiny, top, H, ACC) -> None:
        y = top + 10
        screen.blit(small.render("SAVES - Enter load, N new, D delete (infinite worlds: one save per seed/books combo)", True, (255, 255, 255)), (12, y))
        y += 30
        saves = list_saves(self.root)
        for i, s in enumerate(saves):
            mark = "*" if s["name"] == self.save_name else " "
            screen.blit(small.render(
                f"{mark} {s['name']}  seed {s.get('seed')}  {s.get('players',0)} chars  {s.get('cities','?')} cities",
                True, ACC if i == self.sel else (220, 220, 220)), (24, y))
            y += 26
        screen.blit(tiny.render("New save = fresh infinite world. Old saves stay intact.", True, (150, 150, 150)), (12, H - 44))

    def _draw_settings(self, screen, small, tiny, top, H, ACC) -> None:
        y = top + 10
        screen.blit(small.render("SETTINGS - Up/Down select, Left/Right change, S save", True, (255, 255, 255)), (12, y))
        y += 30
        opts = [("graphics", f"Graphics: {self.settings.get('graphics', 'icons')} (icons = sprites, ascii = letters, live)"),
                ("sound", f"Sound: {'on' if self.settings.get('sound', True) else 'off'} (retro blips)"),
                ("tile", f"Tile size: {self.settings.get('tile')} (restart to apply)"),
                ("difficulty", f"Difficulty: {self.settings.get('difficulty')} (applies to new spawns)"),
                ("color", f"Color: {'on' if self.settings.get('color') else 'off'} (restart to apply)")]
        keys = ["graphics", "sound", "tile", "difficulty", "color"]
        for i, (k, label) in enumerate(opts):
            screen.blit(small.render(f"{'>' if i == self.sel else ' '} {label}", True,
                                     ACC if i == self.sel else (220, 220, 220)), (24, y))
            y += 28


def run_app(root: str | Path = ".", books: str = "books",
            seed: int | None = None) -> None:
    App(root=root, books=books, seed=seed).run()
