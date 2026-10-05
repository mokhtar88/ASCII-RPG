"""Story plotter: one main tale per world, woven from its own annals.

A plot is 6 beats across 3 acts. Beats are ordinary quests (deliver, explore,
hunt, relic, finale) with one rule that makes them a STORY: only the current
beat is active, so each completion turns the page. Victory ends the tale, not
the game.
"""
from __future__ import annotations

import random


def _pick_villain(world) -> str:
    deaths = [e for e in world.history if e.get("kind") == "death" and e.get("people")]
    if deaths:
        d = max(deaths, key=lambda e: e.get("year", 0))
        return f"Heir of {d['people'][0]}"
    if world.history:
        return "The Hollow King"
    return "The Hollow King"


def weave_plot(world, rng: random.Random | None = None) -> dict:
    """Cast the realm's main tale. Idempotent-ish: call once per world."""
    from .quests import Quest
    rng = rng or random.Random(world.seed + 4242)
    villain = _pick_villain(world)
    fh = (world.factions or [None])[0]
    capital = fh.cities[0] if fh and fh.cities else (world.cities[0].name if world.cities else "")
    ruins = [s for s in world.sites if s.kind == "ruin"]
    dens = [s for s in world.sites if s.kind == "dungeon"]
    cx, cy = world.width // 2, world.height // 2
    finale_site = max(dens, key=lambda s: abs(s.x - cx) + abs(s.y - cy)).name if dens else ""
    foe_faction = ""
    if fh and fh.at_war and world.factions:
        foe = next((f for f in world.factions if f.id in fh.at_war), None)
        foe_faction = foe.name if foe else ""
    relics = [a for a in world.artifacts if not a.get("claimed")][:2]

    beats: list[Quest] = []
    title = f"{villain}'s Return"
    beats.append(Quest(
        id="plot-0-warning", kind="deliver", act=1,
        title=f"Warn {capital}" if capital else "Whispers on the Wind",
        giver="The Annals", target_city=capital,
        flavor=f"Old hate stirs: {villain} gathers blades. Carry the warning to {capital}.",
        reward_gold=15, reward_xp=30))
    if ruins:
        rsite = rng.choice(ruins).name
        beats.append(Quest(
            id="plot-1-ashes", kind="explore", act=1,
            title=f"Walk the Ashes of {rsite}",
            giver="The Annals", target_site=rsite,
            flavor=f"{villain} was forged in that old fall. Stand where it burned; learn.",
            reward_gold=12, reward_xp=35))
    else:
        beats.append(Quest(
            id="plot-1-ashes", kind="explore", act=1,
            title="Read the Border Wilds",
            giver="The Annals", target_site=(dens[0].name if dens else ""),
            flavor=f"{villain} moves in the wilds. Find where.",
            reward_gold=12, reward_xp=35))
    beats.append(Quest(
        id="plot-2-cull", kind="hunt", act=2,
        title=f"Bleed the {foe_faction or 'Usurper'} Raiders",
        giver="The Annals", target_enemy=foe_faction or "raiders", amount=4,
        flavor=f"{villain}'s vanguard raids in {foe_faction or 'stolen'} colors. Cull 4.",
        reward_gold=20, reward_xp=45))
    if relics:
        a = relics[0]
        beats.append(Quest(
            id="plot-3-heirloom", kind="relic", act=2,
            title=f"Reclaim {a['name']}",
            giver="The Annals", target_site=a.get("dungeon", ""),
            flavor=f"The old {a['name']} sleeps in {a.get('dungeon', 'the dark')}. Wake it.",
            reward_gold=10, reward_xp=50))
    else:
        beats.append(Quest(
            id="plot-3-heirloom", kind="explore", act=2,
            title="Plunder the Old Vaults",
            giver="The Annals", target_site=(dens[0].name if dens else ""),
            flavor="Power sleeps below. Take what the dead no longer need.",
            reward_gold=10, reward_xp=50))
    if len(relics) > 1:
        a = relics[1]
        beats.append(Quest(
            id="plot-4-crown", kind="relic", act=3,
            title=f"Reclaim {a['name']}",
            giver="The Annals", target_site=a.get("dungeon", ""),
            flavor=f"One relic is a trinket; two are a claim. Take {a['name']}.",
            reward_gold=10, reward_xp=60))
    else:
        beats.append(Quest(
            id="plot-4-crown", kind="hunt", act=3,
            title="Thin the Vanguard",
            giver="The Annals", target_enemy=foe_faction or "raiders", amount=5,
            flavor=f"{villain}'s host masses. Bleed it before it marches.",
            reward_gold=20, reward_xp=60))
    beats.append(Quest(
        id="plot-5-tyrant", kind="finale", act=3,
        title=f"End {villain}",
        giver="The Annals", target_enemy=villain, target_site=finale_site,
        flavor=(f"It ends where power sleeps: {finale_site}. Go down, and end it."
                if finale_site else f"Find {villain} in the wilds, and end it."),
        reward_gold=100, reward_xp=300))
    return {"title": title, "villain": villain, "finale_site": finale_site,
            "beat_ids": [q.id for q in beats], "beats": [q.to_dict() for q in beats],
            "current": 0, "done": False, "acts": ["Echoes of War", "Debts and Heirlooms", "The Return"]}


def ensure_plot(world, rng: random.Random | None = None) -> dict:
    """Legacy saves (and fresh worlds that skipped it) get their tale."""
    plot = getattr(world, "plot", None) or {}
    if plot.get("beat_ids"):
        return plot
    plot = weave_plot(world, rng)
    world.plot = plot
    # unlock the opening beat immediately
    first = plot["beats"][0]
    from .quests import Quest
    if first["id"] not in {q.id for q in world.quests} | set(world.completed_quests):
        world.quests.append(Quest.from_dict(first))
    return plot


def current_beat(world) -> dict | None:
    plot = getattr(world, "plot", None) or {}
    if plot.get("done"):
        return None
    idx = plot.get("current", 0)
    beats = plot.get("beats", [])
    if 0 <= idx < len(beats):
        return beats[idx]
    return None


def advance_plot(state, completed_id: str) -> bool:
    """A finished beat turns the page. Returns True on advancement."""
    from .quests import Quest
    w = state.world
    plot = getattr(w, "plot", None) or {}
    if plot.get("done"):
        return False
    beats = plot.get("beats", [])
    idx = plot.get("current", 0)
    if not (0 <= idx < len(beats)) or beats[idx]["id"] != completed_id:
        return False
    if idx + 1 < len(beats):
        plot["current"] = idx + 1
        nxt = Quest.from_dict(beats[idx + 1])
        if nxt.id not in {q.id for q in w.quests} and nxt.id not in w.completed_quests:
            w.quests.append(nxt)
        state.log(f"+ The tale turns: {nxt.title} (Act {nxt.act}/3).")
    else:
        plot["done"] = True
        state.log(f"+ COMPLETE: {plot.get('title', 'the tale')}! The realm breathes free.")
        state.log("+ Victory is yours — and the wilds go on. Wander as you please.")
        state.player.gold += 100
    w.plot = plot
    return True
