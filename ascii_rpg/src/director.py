"""Event director: tension tiers, context deck, foreshadow, memory, chains.

Travel raises tension; at 100 a card fires as world.director_active with
2-3 choices. Calm tiers deal atmosphere when blood is cool, set pieces when
it runs hot. Draws are weighted by context (ruins at night, war borders,
escorts). Foreshadow rumors seed hits 2-4 days out; choices write memory
NPCs quote back; cards chain (branching) and 2% mythic spikes reshape the
map with a new camp. No repeats within an age.
"""
from __future__ import annotations

import random

TENSION_PER_STRIDE = 2.0
TENSION_NIGHT_BONUS = 0.8
TENSION_WAR_BONUS = 0.5
TENSION_FAR_BONUS = 0.5
MYTHIC_CHANCE = 0.02

# 10 systemic mains (tier calm/setpiece) + tails (chain-only).
TEMPLATES = [
    {"id": "ambush", "tier": "setpiece",
     "title": "Blades on the road!",
     "text": "Ragged blades step from the treeline, steel out.",
     "fore": "Wolves gather near the treeline, travelers say.",
     "choices": [
         {"id": "fight", "label": "Stand and fight", "hint": "a blade bars the way"},
         {"id": "pay", "label": "Pay 15g to pass", "hint": "lose 15g, no blood"},
         {"id": "slip", "label": "Slip away", "hint": "SPD decides"}],
     "chain": {"fight": "ambush_tail", "slip": "ambush_tail"}},
    {"id": "ambush_tail", "tier": "calm",
     "title": "The road remembers",
     "text": "One of the blades you met lingers, watching.",
     "fore": "",
     "choices": [
         {"id": "stare", "label": "Meet their stare", "hint": "+xp, maybe a foe"},
         {"id": "move", "label": "Walk on", "hint": "safe"}],
     "chain": {}},
    {"id": "stranger", "tier": "calm",
     "title": "A wounded traveler",
     "text": "A dusty traveler slumps by a milestone, clutching their side.",
     "fore": "A limping traveler was seen on the milestone road.",
     "choices": [
         {"id": "aid", "label": "Share bread and bandage (+10g cost)", "hint": "+xp, remembered"},
         {"id": "rob", "label": "Rob them", "hint": "+gold, remembered ill"},
         {"id": "leave", "label": "Leave them", "hint": "nothing happens"}],
     "chain": {"aid": "stranger_tail", "rob": "ambush_tail"}},
    {"id": "stranger_tail", "tier": "calm",
     "title": "Word travels",
     "text": "Someone on the road has heard what you did.",
     "fore": "",
     "choices": [
         {"id": "face", "label": "Face it", "hint": "+xp or +gold"},
         {"id": "move", "label": "Walk on", "hint": "safe"}],
     "chain": {}},
    {"id": "cache", "tier": "calm",
     "title": "A cairn of old stones",
     "text": "Mossy stones mark some forgotten cache.",
     "fore": "Old stones north of here hide something, they say.",
     "choices": [
         {"id": "search", "label": "Search it", "hint": "Lore decides: gold or teeth"},
         {"id": "mark", "label": "Mark it for others", "hint": "+xp, a rumor stirs"},
         {"id": "leave", "label": "Leave it", "hint": "safe"}],
     "chain": {}},
    {"id": "omen", "tier": "calm",
     "title": "An omen on the wind",
     "text": "The wind carries a smell of smoke and old iron.",
     "fore": "The wind smells wrong tonight, the elders mutter.",
     "choices": [
         {"id": "pray", "label": "Say a prayer", "hint": "heal a little, time passes"},
         {"id": "study", "label": "Read the signs", "hint": "+lore, +xp"},
         {"id": "march", "label": "March on", "hint": "+tension shed"}],
     "chain": {}},
    {"id": "merchant", "tier": "calm",
     "title": "A lone peddler",
     "text": "A peddler with a mule offers wares from under a patched awning.",
     "fore": "A peddler works the road with strange bundles.",
     "choices": [
         {"id": "buy", "label": "Buy a field good (20g)", "hint": "a draught or bomb"},
         {"id": "hear", "label": "Pay 5g for news", "hint": "a rumor surfaces"},
         {"id": "leave", "label": "Walk on", "hint": "safe"}],
     "chain": {}},
    {"id": "storm", "tier": "calm",
     "title": "Black weather rolling in",
     "text": "Clouds stack like siege towers. The road will be mud.",
     "fore": "Shepherds warn of black weather coming down.",
     "choices": [
         {"id": "shelter", "label": "Shelter an hour", "hint": "time passes, tension shed"},
         {"id": "push", "label": "Push through", "hint": "fast, maybe a chill"},
         {"id": "study", "label": "Read the sky", "hint": "+lore, +xp"}],
     "chain": {}},
    {"id": "warpatrol", "tier": "setpiece", "war_only": True,
     "title": "War blades block the road",
     "text": "Soldiers of the warring powers shake down travelers.",
     "fore": "War blades are shaking down the border road.",
     "choices": [
         {"id": "side", "label": "Name your oath", "hint": "standing decides"},
         {"id": "bribe", "label": "Bribe 12g", "hint": "lose gold, pass"},
         {"id": "evade", "label": "Give them a wide berth", "hint": "SPD decides"}],
     "chain": {}},
    {"id": "border", "tier": "setpiece", "war_only": True,
     "title": "Border warband",
     "text": "A warband of a warring power demands the road-toll in blood or coin.",
     "fore": "A warband bleeds the border villages, runners say.",
     "choices": [
         {"id": "toll", "label": "Pay the toll 12g", "hint": "lose gold, +standing"},
         {"id": "defy", "label": "Defy them", "hint": "soldiers come"},
         {"id": "sneak", "label": "Circle through the fields", "hint": "SPD decides"}],
     "chain": {"defy": "ambush_tail"}},
    {"id": "haunt", "tier": "setpiece",
     "title": "Cold from the old stones",
     "text": "Blue fire crawls on a nearby ruin. The dead do not rest here.",
     "fore": "Blue fire was seen on the old stones after dark.",
     "choices": [
         {"id": "turn", "label": "Turn them with prayer", "hint": "WIS decides"},
         {"id": "loot", "label": "Loot the ruin edge", "hint": "+gold, dead rise"},
         {"id": "flee", "label": "Give it the road", "hint": "safe"}],
     "chain": {"turn": "haunt_tail", "loot": "haunt_tail"}},
    {"id": "haunt_tail", "tier": "calm",
     "title": "It follows in dreams",
     "text": "Something you woke will not lie back down.",
     "fore": "",
     "choices": [
         {"id": "face", "label": "Face it", "hint": "+xp, dead come"},
         {"id": "move", "label": "Walk on fast", "hint": "safe"}],
     "chain": {}},
    {"id": "pack", "tier": "setpiece",
     "title": "Howls answer howls",
     "text": "Beasts circle the road, testing your nerve — and your charges.",
     "fore": "Beasts gather and howl beyond the farms.",
     "choices": [
         {"id": "stand", "label": "Stand your ground", "hint": "beasts come"},
         {"id": "fire", "label": "Wave fire (5g oil)", "hint": "scatter them"},
         {"id": "flee", "label": "Run for it", "hint": "SPD decides"}],
     "chain": {"stand": "pack_tail"}},
    {"id": "pack_tail", "tier": "calm",
     "title": "The pack remembers",
     "text": "A lame beast you bloodied trails you, whining.",
     "fore": "",
     "choices": [
         {"id": "face", "label": "End it kindly", "hint": "+xp, maybe +gold"},
         {"id": "move", "label": "Walk on", "hint": "safe"}],
     "chain": {}},
]

BOOK_CHOICES = [
    {"id": "honor", "label": "Honor the tale", "hint": "+xp, knit a little"},
    {"id": "seek", "label": "Seek its names", "hint": "a rumor stirs"},
    {"id": "take", "label": "Take what remains", "hint": "+gold, risk teeth"},
]

BOOK_SETPIECE = {"battle", "siege", "betrayal"}


def _at_war(world) -> bool:
    try:
        return any(getattr(f, "at_war", []) for f in world.factions)
    except Exception:
        return False


def ensure_fields(world) -> None:
    if not hasattr(world, "tension") or not isinstance(world.tension, (int, float)):
        world.tension = 0.0
    for k, v in (("director_deck", []), ("director_seen", []),
                 ("director_memory", []), ("director_pending", []),
                 ("director_foreshadow", [])):
        if not hasattr(world, k) or not isinstance(getattr(world, k), list):
            setattr(world, k, list(v))
    if not hasattr(world, "director_active"):
        world.director_active = None
    if not hasattr(world, "book_events"):
        world.book_events = []
    if not hasattr(world, "recent_blood"):
        world.recent_blood = 0


def build_deck(world, rng: random.Random) -> list[dict]:
    """Materialize a no-repeat deck: 10 systemic + up to 12 book-echoes."""
    ensure_fields(world)
    cards: list[dict] = []
    n = 0
    for t in TEMPLATES:
        if t["id"].endswith("_tail"):
            continue
        cards.append({"uid": f"d{world.age}-{n}-{t['id']}", "template": t["id"]})
        n += 1
    for b in list(getattr(world, "book_events", []) or [])[:12]:
        cards.append({"uid": f"d{world.age}-{n}-book-{b.get('kind', '')}",
                      "template": "book_echo",
                      "book": {"kind": b.get("kind", ""),
                               "names": list(b.get("names", [])[:3]),
                               "snippet": str(b.get("snippet", ""))[:220]}})
        n += 1
    rng.shuffle(cards)
    world.director_deck = cards
    world.director_seen = []
    return cards


def reset_for_age(world) -> None:
    ensure_fields(world)
    world.director_deck = []
    world.director_seen = []
    world.director_pending = []
    world.director_foreshadow = []
    world.director_active = None
    world.tension = 0.0
    world.recent_blood = 0


def _materialize(world, card: dict) -> dict:
    tid = card.get("template", "omen")
    if tid == "book_echo":
        b = card.get("book", {}) or {}
        names = b.get("names", []) or []
        kind = b.get("kind", "tale")
        who = names[0] if names else "the old tale"
        title = f"Echo of {who} ({kind})"
        text = b.get("snippet", "The books remember blood and promises.")[:220]
        return {"uid": card.get("uid", tid), "template": tid,
                "title": title, "text": text,
                "choices": [dict(c) for c in BOOK_CHOICES],
                "mythic": False, "book": b,
                "chain": {"take": "echo_tail"}, "chain_to": "echo_tail"}
    if tid == "echo_tail":
        return {"uid": card.get("uid", tid), "template": tid,
                "title": "The tale follows you",
                "text": "Someone on the road has heard the same old story.",
                "choices": [
                    {"id": "share", "label": "Share what you know", "hint": "+xp, remembered"},
                    {"id": "move", "label": "Walk on", "hint": "safe"}],
                "mythic": False, "book": card.get("book"),
                "chain": {}, "chain_to": ""}
    t = next((x for x in TEMPLATES if x["id"] == tid),
             next(x for x in TEMPLATES if x["id"] == "omen"))
    texts = dict(t)
    texts["uid"] = card.get("uid", t["id"])
    texts["template"] = t["id"]
    texts["choices"] = [dict(c) for c in t["choices"]]
    texts["mythic"] = False
    texts["book"] = card.get("book")
    texts["chain"] = dict(t.get("chain", {}))
    texts["chain_to"] = t.get("chain_to", "")
    return texts


def _mythic_event(world, rng: random.Random) -> dict:
    terms = list(getattr(world, "relic_words", []) or getattr(world, "lore_terms", [])) or ["ember"]
    term = rng.choice(terms).capitalize()
    arts = [a.get("name", "") for a in (getattr(world, "artifacts", []) or []) if a.get("name")]
    prize = rng.choice(arts) if arts else f"The {term} Crown"
    return {"uid": f"mythic-{world.age}-{rng.randrange(1_000_000)}",
            "template": "mythic",
            "title": f"MYTHIC: {prize} glints",
            "text": f"Once in an age the road offers {prize}. Seize it and the map changes.",
            "choices": [
                {"id": "seize", "label": "Seize it", "hint": "rich, a camp rises"},
                {"id": "refuse", "label": "Let it pass", "hint": "+xp, safe"}],
            "mythic": True, "book": None, "chain": {}, "chain_to": ""}


def tension_gain(state, rng: random.Random | None = None) -> float:
    from .game import clock_phase
    g = TENSION_PER_STRIDE
    try:
        if clock_phase(state.world.clock) == "night":
            g += TENSION_NIGHT_BONUS
    except Exception:
        pass
    if _at_war(state.world):
        g += TENSION_WAR_BONUS
    try:
        px, py = state.player.x, state.player.y
        near = min([abs(c.x - px) + abs(c.y - py) for c in state.world.cities] or [0])
        if near > 20:
            g += TENSION_FAR_BONUS
    except Exception:
        pass
    return g


def _near_site_kind(world, x: int, y: int, kinds: tuple, radius: int) -> bool:
    try:
        return any(getattr(s, "kind", "") in kinds
                   and abs(s.x - x) + abs(s.y - y) <= radius for s in world.sites)
    except Exception:
        return False


def _near_war_city(world, x: int, y: int, radius: int) -> bool:
    try:
        war = {f.id for f in world.factions if f.at_war}
        return any(c.faction in war and abs(c.x - x) + abs(c.y - y) <= radius
                   for c in world.cities)
    except Exception:
        return False


def _escorting(state) -> bool:
    try:
        return any(q.kind == "escort" for q in state.world.quests)
    except Exception:
        return False


def _is_night(world) -> bool:
    try:
        from .game import clock_phase
        return clock_phase(world.clock) == "night"
    except Exception:
        return False


def _tier_hot(state) -> bool:
    """Set-piece tier when blood runs hot, bloodied, or war-dark."""
    try:
        if float(getattr(state.world, "recent_blood", 0) or 0) > 35:
            return True
        p = state.player
        if getattr(p, "hp", 1) < (getattr(p, "max_hp", 1) or 1) * 0.5:
            return True
        if _at_war(state.world) and _is_night(state.world):
            return True
    except Exception:
        pass
    return False


def _card_tier(world, card: dict) -> str:
    tid = card.get("template", "")
    if tid == "book_echo":
        try:
            kind = (card.get("book", {}) or {}).get("kind", "")
            return "setpiece" if kind in BOOK_SETPIECE else "calm"
        except Exception:
            return "calm"
    t = next((x for x in TEMPLATES if x["id"] == tid), None)
    return (t or {}).get("tier", "calm")


def _card_war_only(card: dict) -> bool:
    t = next((x for x in TEMPLATES if x["id"] == card.get("template", "")), None)
    return bool((t or {}).get("war_only"))


def _card_weight(state, card: dict) -> float:
    """Context weight: ruins at night, war borders, escorts."""
    w = state.world
    tid = card.get("template", "")
    if tid in ("warpatrol", "border") and not _at_war(w):
        return 0.0
    sc = 10.0
    try:
        px, py = state.player.x, state.player.y
        if tid == "haunt":
            if _near_site_kind(w, px, py, ("ruin", "dungeon"), 6):
                sc += 15.0
            if _is_night(w):
                sc += 8.0
        elif tid in ("warpatrol", "border"):
            if _near_war_city(w, px, py, 12):
                sc += 15.0
        elif tid == "pack":
            if _escorting(state):
                sc += 10.0
            if _near_site_kind(w, px, py, ("farm", "camp"), 8):
                sc += 6.0
        elif tid == "ambush":
            far = min([abs(c.x - px) + abs(c.y - py) for c in w.cities] or [0]) > 20
            if far:
                sc += 6.0
            if _escorting(state):
                sc += 4.0
        elif tid == "book_echo":
            kind = (card.get("book", {}) or {}).get("kind", "")
            if kind in ("battle", "siege") and _near_site_kind(w, px, py, ("ruin", "dungeon"), 6):
                sc += 6.0
            if kind in ("exodus", "voyage") and \
                    min([abs(c.x - px) + abs(c.y - py) for c in w.cities] or [0]) > 20:
                sc += 4.0
        # foreshadowed cards call louder near their day
        try:
            today = int(w.clock // 1440)
            for f in (getattr(w, "director_foreshadow", []) or []):
                if f.get("template") == tid or (tid == "book_echo" and f.get("template") == "book_echo"):
                    if today >= int(f.get("day", 0)) - 1:
                        sc += 10.0
        except Exception:
            pass
    except Exception:
        pass
    return max(0.0, sc)


def _pick_card(state, rng: random.Random) -> dict | None:
    w = state.world
    if not w.director_deck:
        build_deck(w, rng)
    if not w.director_deck:
        return None
    # war-gated cards never leave the deck while at peace
    avail = [c for c in w.director_deck
             if not (_card_war_only(c) and not _at_war(w))]
    if not avail:
        return None
    hot = _tier_hot(state)
    pool = [c for c in avail
            if (_card_tier(w, c) == ("setpiece" if hot else "calm"))]
    if not pool:
        pool = list(avail)
    weights = [_card_weight(state, c) for c in pool]
    live = [(c, wt) for c, wt in zip(pool, weights) if wt > 0]
    if live:
        pool = [c for c, _ in live]
        weights = [wt for _, wt in live]
    else:
        weights = [10.0 for _ in pool]
    tot = sum(weights)
    r = rng.random() * tot
    acc = 0.0
    for c, wt in zip(pool, weights):
        acc += wt
        if r <= acc:
            w.director_deck.remove(c)
            return c
    c = pool[-1]
    w.director_deck.remove(c)
    return c


def _fore_text(world, card: dict) -> str:
    tid = card.get("template", "")
    if tid == "book_echo":
        b = card.get("book", {}) or {}
        names = b.get("names", []) or []
        who = names[0] if names else "the old tale"
        return f"Travelers whisper the echo of {who} walks again."
    t = next((x for x in TEMPLATES if x["id"] == tid), None)
    return (t or {}).get("fore", "")


def _plant_foreshadow(state, rng: random.Random) -> None:
    w = state.world
    ensure_fields(w)
    if len(w.director_foreshadow) >= 2 or not w.director_deck:
        return
    if rng.random() > 0.02:
        return
    card = rng.choice(w.director_deck)
    text = _fore_text(w, card)
    if not text:
        return
    try:
        today = int(w.clock // 1440)
    except Exception:
        today = 0
    w.director_foreshadow.append({"template": card.get("template", ""),
                                  "uid": card.get("uid", ""),
                                  "text": text[:160],
                                  "day": today + rng.randint(2, 4)})
    del w.director_foreshadow[:-4]


def foreshadow_line(world, rng: random.Random) -> str:
    try:
        fs = list(getattr(world, "director_foreshadow", []) or [])
        if not fs:
            return ""
        f = rng.choice(fs)
        return f"Rumor: {f.get('text', '')[:120]}"
    except Exception:
        return ""


def tick_travel(state, rng: random.Random) -> bool:
    """Per-stride director tick. Returns True if an event fired."""
    w = state.world
    ensure_fields(w)
    try:
        w.recent_blood = max(0.0, float(w.recent_blood or 0.0) - 3.0)
    except Exception:
        w.recent_blood = 0
    for p in list(w.director_pending):
        try:
            p["steps"] = int(p.get("steps", 0)) - 1
        except Exception:
            p["steps"] = -1
        if p["steps"] <= 0:
            w.director_pending.remove(p)
            card = {"uid": f"chain-{w.age}-{rng.randrange(1_000_000)}",
                    "template": p.get("template", "omen"),
                    "book": p.get("book")}
            w.director_active = _materialize(w, card)
            w.tension = 20.0
            state.log(f"! The road turns: {w.director_active['title']}")
            return True
    if getattr(w, "director_active", None):
        return False
    if getattr(state, "interior", None) is not None or getattr(state, "in_combat_with", None):
        return False
    _plant_foreshadow(state, rng)
    w.tension = float(getattr(w, "tension", 0.0) or 0.0) + tension_gain(state, rng)
    if w.tension < 100.0:
        return False
    if rng.random() < MYTHIC_CHANCE:
        w.director_active = _mythic_event(w, rng)
    else:
        card = _pick_card(state, rng)
        if card is None:
            w.tension = 60.0
            return False
        w.director_seen.append(card.get("uid", ""))
        w.director_active = _materialize(w, card)
        # foreshadow fulfilled: as whispered, small bonus
        try:
            hit = [f for f in (w.director_foreshadow or [])
                   if f.get("uid") == card.get("uid") or f.get("template") == card.get("template")]
            if hit:
                w.director_foreshadow = [f for f in w.director_foreshadow if f not in hit]
                state.log(f"As whispered on the road: {w.director_active['title']}")
                from .game import gain_xp, xp_gain
                xp = xp_gain(state.player, 10)
                gain_xp(state, xp)
        except Exception:
            pass
    w.tension = 20.0 + rng.random() * 20.0
    try:
        state.log(f"! The road offers: {w.director_active['title']} (see event)")
    except Exception:
        pass
    return True


def _remember(state, text: str) -> None:
    w = state.world
    ensure_fields(w)
    try:
        day = int(w.clock // 1440) + 1
    except Exception:
        day = 1
    w.director_memory.append({"text": str(text)[:160], "day": day})
    del w.director_memory[:-20]


def _mythic_reshape(state, rng: random.Random) -> None:
    """A seized mythic hour raises a new camp on the map with guards + a tale."""
    from .worldgen import Site, CAMP_TILE, WALKABLE
    w = state.world
    p = state.player
    terms = list(getattr(w, "relic_words", []) or getattr(w, "lore_terms", [])) or ["ember"]
    term = rng.choice(terms).capitalize()
    name = f"{term} Pretender Camp"
    for _ in range(60):
        ax = max(0, min(w.width - 1, p.x + rng.randint(-10, 10)))
        ay = max(0, min(w.height - 1, p.y + rng.randint(-10, 10)))
        if w.grid[ay][ax] not in WALKABLE:
            continue
        if any(abs(c.x - ax) + abs(c.y - ay) < 4 for c in w.cities):
            continue
        if any(abs(s.x - ax) + abs(s.y - ay) < 3 for s in w.sites):
            continue
        rows = [list(r) for r in w.grid]
        rows[ay][ax] = CAMP_TILE
        w.grid = ["".join(r) for r in rows]
        w.sites.append(Site(name=name, x=ax, y=ay, kind="camp", origin_name=term,
                            lore=f"Raised in a mythic hour by a pretender; the annals will note it."))
        try:
            last = max([e.get("year", 0) for e in w.history] + [800])
            w.history.append({"year": last + 1, "kind": "mythic",
                              "text": f"{name} rises where the road offered much.",
                              "place": name, "people": []})
        except Exception:
            pass
        from .quests import Quest
        qid = f"mythic-{abs(hash(name)) % 1_000_000}"
        if qid not in {q.id for q in w.quests} and qid not in (w.completed_quests or []):
            w.dormant_quests.append(Quest(
                id=qid, kind="explore", title=f"Walk {name}",
                giver="The Road", target_site=name,
                flavor=f"A mythic hour raised {name}. Stand in it.",
                reward_gold=25, reward_xp=60))
        from .game import _play_grid, _play_walk, spawn_foe
        try:
            grid, WW, HH = _play_grid(state)
            walk = _play_walk(state)
            pool = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
            for _ in range(2):
                foe = spawn_foe(w, ax, ay, rng, pool, force="bandit")
                if foe is not None:
                    foe.x = max(0, min(WW - 1, ax + rng.randint(-2, 2)))
                    foe.y = max(0, min(HH - 1, ay + rng.randint(-2, 2)))
                    state.enemies.append(foe)
        except Exception:
            pass
        state.log(f"! The map changes: {name} rises nearby (X).")
        return
    state.log("The hour passes; the land holds its shape this time.")


def resolve_choice(state, choice_id: str, rng: random.Random | None = None) -> bool:
    """Apply a director choice. Returns True on success."""
    w = state.world
    ensure_fields(w)
    ev = getattr(w, "director_active", None)
    if not ev:
        return False
    rng = rng or random.Random()
    p = state.player
    title = ev.get("title", "road event")
    picks = {c.get("id"): c for c in ev.get("choices", [])}
    if choice_id not in picks:
        return False
    label = picks[choice_id].get("label", choice_id)

    def spawn_near(kind: str = "", n: int = 1) -> None:
        from .game import _play_grid, _play_walk, spawn_foe
        try:
            grid, WW, HH = _play_grid(state)
            walk = _play_walk(state)
            pool = [c for c in w.characters if c.role == "bandit"] or w.characters[:4]
            for _ in range(n):
                for _t in range(40):
                    ax = max(0, min(WW - 1, p.x + rng.randint(-2, 2)))
                    ay = max(0, min(HH - 1, p.y + rng.randint(-2, 2)))
                    if grid[ay][ax] in walk and not any(
                            e.alive and e.x == ax and e.y == ay for e in state.enemies):
                        foe = spawn_foe(w, ax, ay, rng, pool, force=kind or "")
                        if foe is not None:
                            state.enemies.append(foe)
                        break
        except Exception:
            pass

    def gain_quest_from_names() -> None:
        from .quests import Quest
        names = []
        try:
            b = ev.get("book") or {}
            names = [x for x in b.get("names", []) if x]
        except Exception:
            pass
        giver = names[0] if names else "The Road"
        others = [c.name for c in w.cities]
        tgt = rng.choice(others) if others else ""
        qid = f"road-{abs(hash(ev.get('uid', title))) % 1_000_000}-{choice_id}"
        if qid in {q.id for q in w.quests} or qid in (w.completed_quests or []):
            return
        if tgt:
            w.dormant_quests.append(Quest(
                id=qid, kind="deliver", title=f"Word of {title[:24]} for {tgt}",
                giver=giver if any(c.name == giver for c in w.characters) else (
                    rng.choice([c.name for c in w.characters]) if w.characters else "The Road"),
                target_city=tgt,
                flavor=f"The road remembers: {ev.get('text', '')[:120]}",
                reward_gold=12, reward_xp=30))
            state.log("Word spreads from this deed... (a new rumor stirs).")

    tid = ev.get("template", "")
    if tid == "ambush":
        if choice_id == "fight":
            spawn_near("", 1)
            state.log("Steel out! They come at you.")
        elif choice_id == "pay":
            if p.gold >= 15:
                p.gold -= 15
                state.log("You pay to pass. The blades grin.")
            else:
                spawn_near("", 1)
                state.log("Empty purse. They take offense instead.")
        else:
            from .items import eff_attr
            if rng.random() * 20 < eff_attr(p, "SPD") + 6:
                state.log("You melt into the ditch and pass unseen.")
            else:
                spawn_near("", 1)
                state.log("A hand closes on your cloak — fight!")
    elif tid == "stranger":
        if choice_id == "aid":
            if p.gold >= 10:
                p.gold -= 10
                from .game import gain_xp, xp_gain
                xp = xp_gain(p, 25)
                gain_xp(state, xp)
                state.log(f"You share bread. They bless your name. +{xp}xp.")
            else:
                state.log("Empty purse; kind words will have to do.")
        elif choice_id == "rob":
            got = rng.randint(10, 25)
            p.gold += got
            p.standing = dict(getattr(p, "standing", {}) or {})
            state.log(f"You rob the fallen. +{got}g. The road will remember this ill.")
        else:
            state.log("You walk on.")
    elif tid == "cache":
        if choice_id == "search":
            from .game import add_skill
            from .items import eff_skill
            if rng.random() * 20 < eff_skill(p, "lore") + 8:
                got = rng.randint(15, 40)
                p.gold += got
                state.log(f"Old coins, dry and cold. +{got}g.")
            else:
                spawn_near("beast", 1)
                state.log("Teeth in the dark! Something laired here.")
            add_skill(state, "lore", 1)
        elif choice_id == "mark":
            from .game import gain_xp, xp_gain
            xp = xp_gain(p, 20)
            gain_xp(state, xp)
            gain_quest_from_names()
            state.log(f"You mark the cairn. +{xp}xp.")
        else:
            state.log("You leave the stones to their sleep.")
    elif tid == "omen":
        if choice_id == "pray":
            from .game import advance
            p.hp = min(getattr(p, "max_hp", p.hp) or p.hp, p.hp + 10)
            advance(state, 30)
            state.log("You pray. Your breath steadies (+10hp).")
        elif choice_id == "study":
            from .game import gain_xp, xp_gain, add_skill
            add_skill(state, "lore", 2)
            xp = xp_gain(p, 20)
            gain_xp(state, xp)
            state.log(f"You read the wind. +{xp}xp.")
        else:
            w.tension = 0.0
            state.log("You march on, shedding the dread.")
    elif tid == "storm":
        if choice_id == "shelter":
            from .game import advance
            advance(state, 60)
            w.tension = 0.0
            state.log("You wait out the worst under an eave.")
        elif choice_id == "push":
            p.hp = max(1, p.hp - 5)
            state.log("You push through, soaked and shivering (-5hp).")
        else:
            from .game import gain_xp, xp_gain, add_skill
            add_skill(state, "lore", 1)
            xp = xp_gain(p, 20)
            gain_xp(state, xp)
            state.log(f"You read the storm's hem. +{xp}xp.")
    elif tid == "merchant":
        if choice_id == "buy":
            from .game import give_item
            from .items import gen_consumable
            if p.gold >= 20:
                p.gold -= 20
                item = gen_consumable(rng.choice(["potion", "bomb", "smoke"]),
                                      ["road"], rng)
                if item:
                    give_item(state, item, "Bought")
            else:
                state.log("Empty purse; the peddler shrugs.")
        elif choice_id == "hear":
            if p.gold >= 5:
                p.gold -= 5
                gain_quest_from_names()
                state.log("News for coin: a rumor stirs.")
            else:
                state.log("No coin, no news.")
        else:
            state.log("You walk on.")
    elif tid == "warpatrol":
        if choice_id == "side":
            if getattr(p, "oath", ""):
                p.standing[p.oath] = int(p.standing.get(p.oath, 0)) + 1
                state.log("They see your colors and wave you through.")
            else:
                spawn_near("soldier", 1)
                state.log("No colors? Then you answer with steel.")
        elif choice_id == "bribe":
            if p.gold >= 12:
                p.gold -= 12
                state.log("Coin opens the road.")
            else:
                spawn_near("soldier", 1)
                state.log("No coin. They take offense.")
        else:
            from .items import eff_attr
            if rng.random() * 20 < eff_attr(p, "SPD") + 6:
                state.log("You circle wide through the fields.")
            else:
                spawn_near("soldier", 1)
                state.log("Spotted! They run you down.")
    elif tid == "border":
        if choice_id == "toll":
            if p.gold >= 12:
                p.gold -= 12
                if getattr(p, "oath", ""):
                    p.standing[p.oath] = int(p.standing.get(p.oath, 0)) + 1
                state.log("You pay the war-toll and walk through.")
            else:
                spawn_near("soldier", 1)
                state.log("No coin. They take it in blood.")
        elif choice_id == "defy":
            spawn_near("soldier", 2)
            state.log("You defy them — steel answers!")
        else:
            from .items import eff_attr
            if rng.random() * 20 < eff_attr(p, "SPD") + 6:
                state.log("You circle wide through the fields.")
            else:
                spawn_near("soldier", 1)
                state.log("Spotted! They run you down.")
    elif tid == "haunt":
        if choice_id == "turn":
            from .items import eff_attr
            if rng.random() * 20 < eff_attr(p, "WIS") + 6:
                from .game import gain_xp, xp_gain
                xp = xp_gain(p, 30)
                gain_xp(state, xp)
                state.log(f"Your prayer holds. +{xp}xp.")
            else:
                spawn_near("undead", 2)
                state.log("Prayer falters — they rise!")
        elif choice_id == "loot":
            got = rng.randint(15, 35)
            p.gold += got
            spawn_near("undead", 1)
            state.log(f"You pocket cold coin (+{got}g). Something rises!")
        else:
            state.log("You give the stones the road.")
    elif tid == "pack":
        if choice_id == "stand":
            spawn_near("beast", 2)
            state.log("You plant your feet — they come!")
        elif choice_id == "fire":
            if p.gold >= 5:
                p.gold -= 5
                state.log("Oil and flame scatter the pack.")
            else:
                spawn_near("beast", 1)
                state.log("No oil. Teeth close in!")
        else:
            from .items import eff_attr
            bonus = 4 if _escorting(state) else 0
            if rng.random() * 20 < eff_attr(p, "SPD") + 6 + bonus:
                state.log("You outrun the howls.")
            else:
                spawn_near("beast", 1)
                state.log("A fang finds your heel!")
    elif tid == "book_echo":
        if choice_id == "honor":
            from .game import gain_xp, xp_gain
            xp = xp_gain(p, 30)
            gain_xp(state, xp)
            p.hp = min(getattr(p, "max_hp", p.hp) or p.hp, p.hp + 5)
            state.log(f"You honor the old tale. +{xp}xp.")
        elif choice_id == "seek":
            gain_quest_from_names()
            state.log("You ask after its names on the road.")
        else:
            got = rng.randint(10, 30)
            p.gold += got
            state.log(f"You pocket what the tale left. +{got}g.")
            if rng.random() < 0.35:
                spawn_near("", 1)
                state.log("Something objects to your looting!")
    elif tid == "mythic":
        if choice_id == "seize":
            got = rng.randint(60, 120)
            p.gold += got
            from .game import gain_xp, xp_gain
            xp = xp_gain(p, 80)
            gain_xp(state, xp)
            spawn_near("", 1)
            _mythic_reshape(state, rng)
            state.log(f"You seize the mythic hour! +{got}g +{xp}xp — but it is guarded.")
        else:
            from .game import gain_xp, xp_gain
            xp = xp_gain(p, 40)
            gain_xp(state, xp)
            state.log(f"You let it pass, wiser. +{xp}xp.")
    else:  # tails and unknowns
        from .game import gain_xp, xp_gain
        if choice_id in ("stare", "face", "share"):
            xp = xp_gain(p, 20)
            gain_xp(state, xp)
            if choice_id == "face" and tid in ("haunt_tail",):
                spawn_near("undead", 1)
            elif rng.random() < 0.3:
                spawn_near("", 1)
            state.log(f"You face it down. +{xp}xp.")
        else:
            state.log("You walk on.")

    _remember(state, f"{title} — {label}")
    # branching chains: choice decides the follow-up tail
    chain = ev.get("chain", {}) or {}
    nxt = chain.get(choice_id, ev.get("chain_to", ""))
    if nxt and rng.random() < 0.25:
        w.director_pending.append({"template": nxt,
                                   "steps": rng.randint(12, 20),
                                   "book": ev.get("book")})
    w.director_active = None
    return True


def memory_line(world, rng: random.Random) -> str:
    mem = list(getattr(world, "director_memory", []) or [])
    if not mem:
        return ""
    m = rng.choice(mem)
    return f"They say you remember: {m.get('text', '')[:120]}"
