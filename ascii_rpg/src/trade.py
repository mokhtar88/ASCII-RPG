"""Inter-city trade: pack-goods price spreads via the caravan network.

Every city craves different goods (deterministic per seed+city+good, rolling
every 3 days). Loot or gather where goods are cheap, ride the caravan where
they pay double. Gear is untouched (flat half-price resale); only consumable
and material pack goods ride the winds.
"""
from __future__ import annotations

import random

# sell multiplier ladder (applied over the flat half-price resale)
SELL_LADDER = [0.6, 0.8, 1.0, 1.4, 2.0]
# buy multiplier ladder (applied over list price)
BUY_LADDER = [0.7, 0.85, 1.0, 1.15]

GOOD_KINDS = ("consumable", "material")


def cycle(world) -> int:
    try:
        return int(world.clock // 4320)
    except Exception:
        return 0


def _roll(seed: int, city: str, sub: str, cyc: int, ladder: list) -> float:
    rng = random.Random(hash((seed, city, sub, cyc)) & 0xFFFFFFFF)
    return rng.choice(ladder)


def _good_sub(item: dict) -> str:
    if (item.get("kind") or "") not in GOOD_KINDS:
        return ""
    return str(item.get("sub") or "")


def sell_price(world, city_name: str, item: dict) -> int:
    base = max(1, int(item.get("value", 0)) // 2)
    sub = _good_sub(item)
    if not sub or not city_name:
        return base
    m = _roll(world.seed, city_name, sub, cycle(world), SELL_LADDER)
    return max(1, round(base * m))


def buy_price(world, city_name: str, item: dict) -> int:
    base = max(1, int(item.get("value", 0)))
    sub = _good_sub(item)
    if not sub or not city_name:
        return base
    m = _roll(world.seed, city_name, sub, cycle(world), BUY_LADDER)
    return max(1, round(base * m))


def top_demand(world, city_name: str) -> tuple[str, float]:
    """The good this city craves most right now (sub label, sell mult)."""
    best, bm = "", 0.0
    subs = ["potion", "bomb", "smoke", "quiver", "tonic",
            "herb", "fang", "venom", "dust", "scale"]
    for sub in subs:
        m = _roll(world.seed, city_name, sub, cycle(world), SELL_LADDER)
        if m > bm:
            best, bm = sub, m
    return best, bm


def tip(world, player) -> str:
    """One caravan-tip line for the player's fattest pack good."""
    try:
        from collections import Counter as _C
        subs = [str(i.get("sub") or "") for i in (player.inventory or [])
                if (i.get("kind") or "") in GOOD_KINDS and i.get("sub")]
        if not subs:
            return ""
        sub = _C(subs).most_common(1)[0][0]
        best_c, best_m = "", 0.0
        for c in (world.cities or []):
            m = _roll(world.seed, c.name, sub, cycle(world), SELL_LADDER)
            if m > best_m:
                best_c, best_m = c.name, m
        if best_c and best_m >= 1.4:
            return f"Traders whisper: {best_c} pays double for {sub}."
    except Exception:
        pass
    return ""
