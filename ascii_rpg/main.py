"""Inkbound Realms - book-driven ASCII RPG launcher (tabbed edition)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ingest import collect_book_files, load_corpus  # noqa: E402
from src.worldgen import generate_world  # noqa: E402
from src.saves import write_save, read_save, list_saves  # noqa: E402
from src.ui import run_app  # noqa: E402
from src.worldgen import World  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Inkbound Realms - ASCII RPG from your books")
    ap.add_argument("--books", default="books", help="Book directory")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--save", default="slot1", help="Save slot name")
    ap.add_argument("--regen", action="store_true")
    ap.add_argument("--ascii-preview", action="store_true")
    args = ap.parse_args()

    root = Path(".")
    if args.ascii_preview:
        files = collect_book_files(root / args.books)
        corpus = load_corpus(files) if files else ""
        try:
            wd, _, _, _ = read_save(root, args.save)
            world = World.from_dict(wd)
            if args.regen or (args.seed is not None and args.seed != world.seed):
                raise FileNotFoundError
            print(f"Loaded save '{args.save}' seed {world.seed}.")
        except FileNotFoundError:
            from random import randrange
            seed = args.seed if args.seed is not None else randrange(1_000_000)
            print(f"Reading {len(files)} book(s). Corpus: {len(corpus)} chars.")
            world = generate_world(corpus, seed=seed)
            try:
                _, roster_d, active_d, enemies_d = read_save(root, args.save)
            except FileNotFoundError:
                roster_d, active_d, enemies_d = [], 0, []
            write_save(root, args.save, world.to_dict(), roster_d, active_d, enemies_d)
            print(f"Generated seed {world.seed} into save '{args.save}'.")
        for row in world.grid:
            print(row)
        import random as _r
        from src.plot import ensure_plot
        if not world.plot:
            ensure_plot(world, _r.Random(world.seed + 4242))
            try:
                _, roster_d, active_d, enemies_d = read_save(root, args.save)
            except FileNotFoundError:
                roster_d, active_d, enemies_d = [], 0, []
            write_save(root, args.save, world.to_dict(), roster_d, active_d, enemies_d)
        print(f"\n[{world.width}x{world.height}] Cities:",
              ", ".join(f"{c.name} ({c.x},{c.y})" for c in world.cities))
        print("Sites:", ", ".join(f"{s.name} [{s.kind}] ({s.x},{s.y})" for s in world.sites))
        print("Regions:", ", ".join(r.name for r in world.regions))
        if world.classes:
            print("Callings:", ", ".join(f"{c['name']} ({c['template']})" for c in world.classes))
        if world.history:
            wars = sum(1 for e in world.history if e.get("kind") == "war")
            print(f"Annals: {len(world.history)} events, {wars} wars (see DATA tab).")
        if world.plot and world.plot.get("beat_ids"):
            print(f"MAIN: {world.plot.get('title')} - {len(world.plot['beat_ids'])} beats"
                  + (" - COMPLETE" if world.plot.get("done") else ""))
        if world.factions:
            from src.worldgen import faction_name as _fn
            for f in world.factions:
                wars = f", at war with {', '.join(_fn(world, x) for x in f.at_war)}" if f.at_war else ""
                print(f"Faction: {f.name} holds {len(f.cities)} cities{wars}")
        print("Races:", ", ".join(r.name for r in world.races))
        print(f"Quests ({len(world.quests)} active, {len(world.dormant_quests)} unheard, "
              f"{len(world.completed_quests)} done):")
        for q in world.quests:
            print(f" - [{q.kind}] {q.title}: {q.flavor}")
        if world.dormant_quests:
            print(f"... and {len(world.dormant_quests)} unheard rumors (talk in towns).")
        return

    if args.seed is not None and args.regen:
        # force a fresh world into the requested slot before opening UI (keep roster)
        files = collect_book_files(root / args.books)
        corpus = load_corpus(files) if files else ""
        world = generate_world(corpus, seed=args.seed)
        try:
            _, roster_d, active_d, enemies_d = read_save(root, args.save)
        except FileNotFoundError:
            roster_d, active_d, enemies_d = [], 0, []
        write_save(root, args.save, world.to_dict(), roster_d, active_d, enemies_d)
        print(f"Seeded save '{args.save}' with world {args.seed}.")
    elif not list_saves(root) and (root / "world.json").exists():
        print("Migrating legacy world.json into saves/slot1/ ...")

    run_app(root=root, books=args.books,
            seed=args.seed if args.regen and args.seed is not None else None)


if __name__ == "__main__":
    main()
