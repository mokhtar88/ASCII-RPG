"""Multi-save persistence: saves/<name>/{meta,world,players}.json + global config."""
from __future__ import annotations

import json
import time
from pathlib import Path

SAVES_DIR_NAME = "saves"
CONFIG_NAME = "config.json"

DEFAULT_SETTINGS = {
    "tile": 22,
    "color": True,
    "difficulty": "normal",  # easy | normal | hard
    "graphics": "icons",  # icons | ascii
    "sound": True,
    "fullscreen": False,
}


def saves_dir(root: str | Path) -> Path:
    d = Path(root) / SAVES_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path(root: str | Path) -> Path:
    return Path(root) / CONFIG_NAME


def load_settings(root: str | Path) -> dict:
    p = config_path(root)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(root: str | Path, settings: dict) -> None:
    config_path(root).write_text(json.dumps(settings, indent=2), encoding="utf-8")


def list_saves(root: str | Path) -> list[dict]:
    d = saves_dir(root)
    out = []
    for sub in sorted(d.iterdir()):
        if not sub.is_dir():
            continue
        meta = {"name": sub.name, "seed": None, "players": 0, "modified": 0}
        try:
            mp = sub / "meta.json"
            if mp.exists():
                meta.update(json.loads(mp.read_text(encoding="utf-8")))
            pp = sub / "players.json"
            if pp.exists():
                pdata = json.loads(pp.read_text(encoding="utf-8"))
                meta["players"] = len(pdata.get("roster", []))
            meta["modified"] = sub.stat().st_mtime
        except Exception:
            pass
        out.append(meta)
    return sorted(out, key=lambda m: m["name"])


def save_dir(root: str | Path, name: str) -> Path:
    d = saves_dir(root) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_save(root: str | Path, name: str, world_dict: dict,
               roster: list[dict], active: int, enemies: list[dict] | None = None) -> None:
    d = save_dir(root, name)
    seed = world_dict.get("seed")
    (d / "world.json").write_text(json.dumps(world_dict, indent=2), encoding="utf-8")
    (d / "players.json").write_text(
        json.dumps({"roster": roster, "active": active,
                    "enemies": enemies or []}, indent=2), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(
        {"name": name, "seed": seed, "updated": time.time(),
         "cities": len(world_dict.get("cities", []))}, indent=2), encoding="utf-8")


def read_save(root: str | Path, name: str) -> tuple[dict, list[dict], int, list[dict]]:
    """Returns (world_dict, roster, active, enemies). Raises FileNotFoundError."""
    d = saves_dir(root) / name
    world_dict = json.loads((d / "world.json").read_text(encoding="utf-8"))
    roster, active, enemies = [], 0, []
    pp = d / "players.json"
    if pp.exists():
        pdata = json.loads(pp.read_text(encoding="utf-8"))
        roster = pdata.get("roster", [])
        active = pdata.get("active", 0)
        enemies = pdata.get("enemies", [])
    return world_dict, roster, active, enemies


def delete_save(root: str | Path, name: str) -> bool:
    import shutil
    d = saves_dir(root) / name
    if not d.exists():
        return False
    shutil.rmtree(d)
    return True


def migrate_legacy_world(root: str | Path, legacy: str = "world.json",
                         dest: str = "slot1") -> str | None:
    """Move old single world.json into saves/<dest>/ so old users keep progress."""
    root = Path(root)
    lp = root / legacy
    d = root / SAVES_DIR_NAME / dest / "world.json"
    if lp.exists() and not d.exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(lp.read_bytes())
        (d.parent / "players.json").write_text(
            json.dumps({"roster": [], "active": 0, "enemies": []}), encoding="utf-8")
        (d.parent / "meta.json").write_text(
            json.dumps({"name": dest, "seed": None, "updated": time.time()}), encoding="utf-8")
        return dest
    return None
