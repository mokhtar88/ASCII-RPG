"""Bounty board: posted bounties per city, refreshed daily.

Every town visit gets a reason: 2-3 takable postings (bounty/hunt) that
pay gold/xp and complete through the normal kill machinery, so war hunts
move the tide via soldier kills. Deterministic per seed+city+day.
"""
from __future__ import annotations

import random


def today(world) -> int:
    try:
        return int(world.clock // 1440)
    except Exception:
        return 0


def ensure_fields(world) -> None:
    if not hasattr(world, "bounty_board") or not isinstance(world.bounty_board, dict):
        world.bounty_board = {}
    if not hasattr(world, "board_day"):
        world.board_day = -1


def _city_war_foes(world, city_name: str) -> list[str]:
    try:
        city = next((c for c in world.cities if c.name == city_name), None)
        if city is None or not getattr(city, "faction", ""):
            return []
        me = next((f for f in world.factions if f.id == city.faction), None)
        return list(me.at_war) if me is not None else []
    except Exception:
        return []


def postings_for(world, city_name: str) -> list[dict]:
    """Postings for a city, rebuilding when the day turns."""
    ensure_fields(world)
    day = today(world)
    slot = world.bounty_board.get(city_name)
    if isinstance(slot, dict) and slot.get("day") == day and isinstance(slot.get("posts"), list):
        return slot["posts"]
    rng = random.Random(hash((world.seed, city_name, day)) & 0xFFFFFFFF)
    bandits = [c.name for c in world.characters if c.role == "bandit"]
    posts: list[dict] = []
    # 1-2 named bounties off the bandit roster
    if bandits:
        picks = rng.sample(bandits, min(len(bandits), 2))
        for i, b in enumerate(picks):
            posts.append({
                "id": f"board-{city_name}-{day}-{i}-{abs(hash(b)) % 9999}",
                "kind": "bounty",
                "title": f"Bounty: {b}",
                "target_enemy": b,
                "amount": 0,
                "reward_gold": rng.randint(18, 30),
                "reward_xp": rng.randint(35, 55),
                "flavor": f"The board of {city_name} wants {b} stopped. (Day {day + 1})",
            })
    # 1 hunt: war soldiers when the city is at war, else beasts
    foes = _city_war_foes(world, city_name)
    if foes:
        foe = rng.choice(foes)
        need = rng.randint(2, 4)
        posts.append({
            "id": f"board-{city_name}-{day}-war",
            "kind": "hunt",
            "title": f"Cull {need} {foe} raiders",
            "target_enemy": foe,
            "amount": need,
            "reward_gold": rng.randint(16, 26),
            "reward_xp": rng.randint(30, 50),
            "flavor": f"For the war effort: bleed {foe} ({need}).",
        })
    else:
        need = rng.randint(3, 5)
        posts.append({
            "id": f"board-{city_name}-{day}-hunt",
            "kind": "hunt",
            "title": f"Cull {need} beasts",
            "target_enemy": "beasts",
            "amount": need,
            "reward_gold": rng.randint(14, 22),
            "reward_xp": rng.randint(30, 45),
            "flavor": f"The board of {city_name} pays for {need} beast pelts.",
        })
    world.bounty_board[city_name] = {"day": day, "posts": posts[:3]}
    return world.bounty_board[city_name]["posts"]


def accept(state, city_name: str, posting_id: str) -> bool:
    """Take a posting: it becomes an active quest, removed from the board."""
    from .quests import Quest
    w = state.world
    posts = postings_for(w, city_name)
    post = next((x for x in posts if x.get("id") == posting_id), None)
    if post is None:
        return False
    if post["id"] in {q.id for q in w.quests} or post["id"] in (w.completed_quests or []):
        return False
    giver = f"Board of {city_name}"
    if post["kind"] == "bounty":
        q = Quest(id=post["id"], kind="bounty", title=post["title"],
                  giver=giver, target_enemy=post.get("target_enemy", ""),
                  flavor=post.get("flavor", ""),
                  reward_gold=int(post.get("reward_gold", 20)),
                  reward_xp=int(post.get("reward_xp", 40)))
    else:
        q = Quest(id=post["id"], kind="hunt", title=post["title"],
                  giver=giver, target_enemy=post.get("target_enemy", ""),
                  amount=int(post.get("amount", 3)),
                  flavor=post.get("flavor", ""),
                  reward_gold=int(post.get("reward_gold", 18)),
                  reward_xp=int(post.get("reward_xp", 35)))
    # hunts count any foe kill; board hunts for "beasts" stay generic
    w.quests.append(q)
    slot = w.bounty_board.get(city_name)
    try:
        slot["posts"] = [x for x in slot["posts"] if x.get("id") != posting_id]
    except Exception:
        pass
    state.log(f"Taken: {q.title} (see journal).")
    return True
