# HANDOFF — Inkbound Realms (book-driven ASCII RPG)

Paste into a fresh session along with: "Continue from HANDOFF.md in this folder."

## Where things live
- Origin (build here): `C:\Users\LENOVO\OneDrive\Documents\Default Project\ascii_rpg\`
- Play copy (user plays here): `E:\ascii_rpg\` — sync with `update.bat` (double-click in origin).
  It mirrors code, backs up saves to `E:\ascii_rpg_saves_backup`, and NEVER touches
  `saves/ books/ config.json run.log world.json`. Updater exits 0 + `[OK]` on success.
- Stack: Python 3.12, pygame 2.6, numpy, pypdf. Launch: `run.bat` or `python main.py`.

## Module map (`ascii_rpg/src/`)
- `ingest.py` — .txt/.pdf/.epub → plain text (stdlib-only epub parsing).
- `extract.py` — proper-noun lore (people/places/groups), terms, flavor lines, relic_words (noun-only pool).
- `names.py` — mutates book names so the world feels unique, not copied.
- `worldgen.py` — noise continents (numpy fBm, global coords), cities/factions/regions/sites,
  infinite `grow()` + `settle_frontier()`, save compat via tolerant `from_dict`.
- `quests.py` — 10 verbs (deliver/bounty/explore/escort/hunt/tribute/pilgrimage/treasure/relic/finale),
  unique ids, round-robin mix, urgent deadlines, chain follow-ups in game.py.
- `plot.py` — 6-beat main tale from the annals (weave/ensure/advance); victory ends tale, not game.
- `history.py` — 800-year sim (wars/battles/sacks/heroes/artifacts); ruin lore, boss legends.
- `dungeon.py` — seed-derived dungeon/ruin interiors + town layouts (rooms/corridors or streets).
- `magic.py` — 8-spell lore-named book (pure fn of terms; bolt/spark/smite/mend/blink/ward/charm/sight).
- `items.py` — gear w/ atk/hp/attrs/skills/element/resist; eff_* stat helpers; climate-weighted gen.
- `game.py` — all rules: movement, AI (wander/chase/undead-slow/spider-lunge/nocturnal wraiths),
  combat, XP/skills/attrs, rest/clock, shops, interiors, frontier, captains, caravans, buffs/burn.
- `ui.py` — pygame tabs (MAP/CHARACTERS/BOOKS/SAVES/SETTINGS/INVENTORY/DATA, keys 1-7),
  title menu + hero forge, icons-or-ascii, sidebar/minimap/journal/overlays (shop/spell/caravan).
- `saves.py` — `saves/<name>/{world,players,meta}.json` + `config.json` (tile/color/difficulty/graphics/sound).
- `sfx.py` — synthesized blips; `play()` never raises; toggle via settings.
- `main.py` — launcher + `--ascii-preview` (terminal map test, no pygame).

## Iron conventions (do not break)
1. **Legacy saves always load.** Every `from_dict` tolerates missing keys with sane defaults.
2. **Headless test every drop**, then DELETE the selftest file. Pattern: `cd ascii_rpg; python selftestN.py`
   (build worlds from `books/sample.txt`, fixed seeds, assert mechanics, save/load roundtrip).
3. **UI changes get a dummy-driver render smoke test** (`SDL_VIDEODRIVER=dummy`, real `App`, call draw fns).
4. **Edge cases that bit before:** map-edge tiles (`t` unbound), death overlay missing `big` font,
   town resume (gates, not stairs), frontier growth must shift cities/sites/regions, not just grid.
5. **Windows batch pitfalls:** `)` inside a parenthesized block closes it early (the update.bat saga);
   prefer `echo(` over `echo.`; PowerShell has no `head/grep/printf`, no `< NUL` redirect,
   and `Select-Object -First N` truncates pipes (verify via files, not pipes).
6. Keep code ASCII-only in identifiers; mutations deterministic under seed.

## Feature state (what's in)
Infinite growing worlds (150→300x170 default? now 300x170), factions + wars, history + annals + heirlooms,
main plot + victory, classes (uncapped to 12) + 8 races w/ bloodlines, hero forge, mana + 8 spells + shrines,
town/dungeon interiors (+themes/tiers), gear/shops/loot, 8 skills (uncapped) + 6 attrs, bestiary (8 kinds),
elemental climate + typed damage/resists/burn/buffs, SAGA telemetry, DATA provenance ledger, compass +
minimap dots + floaters + caravans + SFX. Urgent quests, chains, escort ambushes, captains, level scaling.
Event director + book mining + bounty boards (Oct 2026 arc) + book sagas (3-part gated chains) + deep delves & living towns + trade, spellcraft, housing + war-magic (morale, styles, chanters, 5 signs) + canon signs (summon, turn, blizzard, invis, mark) + callings (derivatives + arts) + traps & tuning.

## Queued next (in order)
1. **Combat slice one** (DONE Oct 2026): Heavy (H, 1.7x/75%) / Quick (Q, 0.6x + soft counter +
   60% windup spoil) / Defend (D, quarters next counter), telegraphed foe heavies (1.8x),
   poison ticks (2hp, mend/heal/rest cure), consumables (potion/bomb/smoke) via shops +
   drops + INVENTORY Enter + combat P/B/V. Headless selftest + dummy render smoke passed.
2. Ranged weapons drop (DONE Oct 2026): bows as a real flag (~1/3 of steel, every
   market racks one, loot/quest flow automatic), R to loose 2-4 down Bresenham-clear
   lanes (~90% weight, half-drawn up close), 1-in-4 bandits/soldiers are archers that
   hold range / back off / loose 80% replies (guard+wards answer). Kills at range pay
   XP/loot/bounties. Headless selftest + dummy render smoke passed.
3. Companion/enemy-brain drop (DONE Oct 2026): escort companions trail/fight/nip
   (hurt on quest, down-but-never-slain, map + sidebar status), struck beasts howl
   in packmates (35%, cap 5 near), bosses enrage at a third (1.5x ATK, +windup
   hunger, charm snapped, ENRAGED tag). Also fixed latent frontier crash
   (settle_frontier used name_pool unimported). Headless selftest + dummy smoke passed.
4. Full-kit combat balance + depth (DONE Oct 2026): heavies wind (+50% next reply,
   shed on kill/disengage) ending Heavy spam; strikes reach adjacent tiles
   (grapple-free) + adjacent flee; ammo economy (20 quivered, 1/shot, quiver
   goods + U key); bleed status (Savage/beasts, draught/heal/rest cure, mend won't);
   foe draughts under half (costs turn); drake ember breath + wraith umbral wail
   at 2-3 down lanes; boss warcry guards at two-thirds (once, cap 8). Headless
   selftest + dummy render smoke passed.
5. PyInstaller exe + clean-machine test + player-facing docs.
7. Faction ages (DONE Oct 2026): O panel to swear/forswear (betrayal remembered),
   soldier kills move tide + standing (oathbreaking punished), sworn blades give
   free passage + cheap heal/caravan while rivals gain reach, 14 dead ends a war
   (towns kneel, annals turn, age+1, +150g, Enter-dismissed overlay, play goes on),
   new wars kindle after 3 days peace. Headless selftest + dummy smoke passed.
6. Loot scaling + rarity (DONE Oct 2026): keen/runed/mythic ladder (name + stats +
   1.5x/2.2x/3.5x price, tier-weighted rolls), danger tiers (delves + far wilds +1,
   cap 6), boss floors (keen+, Dread runed+). Reforge gold sink (DONE Oct 2026):
   third shop panel raises worn/packed gear a tier (cap 5, cost scales tier x
   rarity, rarity never downgrades, no stacked prefixes). Next: faction endings
   as the true end goal.
8. Uncapped attributes + harder scaling + living spawns (DONE Oct 2026): no 10/12
   ceilings anywhere (floors hold: aggro 3, flee 90%, healing 1g), trail is half
   level, delve/boss/tyrant/captain curves up, ecology trickle (12%/stride under
   cap = density + level, 10-16 leagues, hearth-safe) + stray culling (40 leagues,
   quest/boss/charmed immune). Headless selftest + dummy smoke passed.
9. Perk system (DONE Oct 2026): world-rolled ~34-perk pool from 19 frames
   (pure fn of seed, zero save space), draft every 5th level of 3 class-weighted
   + 1 wild, pick-one-burn-three, repeats rank to III, loud picks level-gated.
   Hooks: thorns/executioner/steady/windrunner/bulwark/keeneye/fleetfoot/fletcher,
   mendpower/emberwake/manafont, scavenger/ruinlord/beastfriend/warprofiteer/
   bloodprice (9th spell key)/hoarder/slip/windfall + pack cap + flee curve.
   Headless selftest + dummy smoke passed.
10. UI revamp (DONE Oct 2026): rendering rewritten around one theme table +
   layout engine (measured truncation makes overflow impossible, one card/
   bar/pill system, subtractive sidebar: tracked tale + counts, collapsed
   legend, two-line combat bar). Old files: ui_legacy/. Backup: ui_legacy/ui_backup.py.
11. Display freedom (DONE Oct 2026): resizable window (maximize usable — the map
    viewport grows to fill it), fullscreen toggle in Settings + F11 live, HUD hint
    split so no key is ever truncated away. Headless event-loop smoke passed.
12. Alchemy (DONE Oct 2026): 5 material kinds (herbs gathered G on forests, fangs/
    venom/dust/scales salvaged by foe kind), 15 kettle recipes (scrolling K overlay,
    all-or-nothing stock) brewing 9 more goods — swift/iron/focus/secondwind/love/
    glitter/berserk/ghost/greed/firebelch with full combat hooks (incl. foe blind
    flag, cheat-death sites, wild aim, pass-through). One picker for every field
    good (X in and out of combat; P/B/V/U/T kept as quick keys). Headless selftest
    + dummy smoke passed.
13. Event director core (DONE Oct 2026): tension meter pacing travel, road deck with
    2-3 real choices per event, memory ledger NPCs quote back, two-link chains,
    2% mythic spikes, no-repeat deck per age. Reuses ambush/rumor machinery.
    Movement blocks while active (Y). Headless selftest + dummy smoke passed.
14. Book-event mining (DONE Oct 2026, sagas Oct 2026): verb-frame extraction (slew/siege/fled/wed/betrayed/
    storm/plague/voyage) into {kind, names, snippet} events feeding quest seeds,
    history seeds, and the director deck. Frequency voting + diversity. Tested on
    GoT + Way of Kings (3.4M chars, all 8 kinds). Top 3 happenings now unfold as
    3-part gated sagas (saga tag, vaulted II/III, mined names as giver/target).
    Elevated: top-20 pool -> 8 sagas (24 quests) + 12 single echoes; per-world
    sampling so seeds differ. Director now has tension tiers (calm/setpiece via
    recent blood), context weights (ruin-night, war borders, escorts), foreshadow
    2-4 days out, branching chains, mythic map reshape (new camp + guards +
    history + quest). 10 systemic mains + book-echoes in deck.
15. Bounty board (DONE Oct 2026): posted bounties per city (V in towns, refresh daily),
    giving every town visit a reason; war hunts move the tide via centralised _slay.
16. Trading (DONE Oct 2026): inter-city price spreads on pack goods via the caravan
    network (deterministic per seed+city+good, 3-day rolls; goods ride the spread,
    gear flat). Shops/caravan/merchant-NPCs surface it. Headless selftest passed.
20. Deep delves + living towns (DONE Oct 2026): dungeon/ruin depth 1/3/5 per seeded
    site (down-stairs (>) per floor, boss + scaled foes on the last floor, per-floor
    loot memory, legacy chest ids honored); bigger town tiers (to 58x34, up to 20
    souls: roster locals + filler townsfolk) with working roles — merchant stock
    reports, healer 10hp daily mend, scout bearings, elder history+lore, guard war
    briefs. Headless selftest + dummy icon smoke passed.
17. Spellcrafting (DONE Oct 2026): shrine fusion of known bolt/spark/smite/mend/ward
    x ember/frost/storm/umbral for a 2-mat fee (typed bolts, deeper mend/ward, +2 mana).
    N overlay on shrines, cast via book. Headless selftest passed.
18. Housing (DONE Oct 2026): buyable city room (200g) with gear stash, rested sleep
    (+15% xp, 120 steps), settable rise point (death brings you home). M overlay in
    cities. Headless selftest passed.
21. War-magic bundle (DONE Oct 2026): morale (bloodied blades surrender tribute +
    stand down, beasts rout and melt; bosses/mindless immune), flanking with
    companions (1.5x), weapon styles (swift/heavy-cleave/spear-reach), chanter foes
    (j: storm volleys, wards, pack mends, delve + ruin haunts), five new shrine-taught
    signs (igni AoE, aard push, yrden slow, fury frenzy, frostbite), paged spellbook,
    shrine rate up (site cycle now deals shrines twice as often). Selftest + smoke passed.
23. Callings with teeth (DONE Oct 2026): 29 derivatives differentiated (own desc,
    stat/skill twists, styled starting blades, swapped spells — rangers draw bows,
    clerics carry turn) + one art per template on stride cooldowns (cry, channel,
    volley, vanish, consecrate, inspire +5g, surge, lay hands), P key on the wilds,
    readiness on the roster. Tuned Oct 2026: bard songs cheapen caravans + lengthen
    charms, paladin aura softens companion nicks, volley costs 1 arrow. Headless
    selftest + smoke passed.
24. Rogue traps (DONE Oct 2026): 4 kettle recipes (snare/dart/ember/oil) nested in K,
    laid from the X picker (no new menu/key; I stays free), foe + hero trigger hooks,
    Thief +1 damage, Assassin shadow-crits on the slowed, camps pre-lay foe-traps.
    Headless selftest + kettle/picker smoke passed. Monk left untouched.
22. Canon signs (DONE Oct 2026): five more shrine-taught spells from the forum canon —
    summon (spectral wolf ally w/ own turns, expiry, full ally targeting rules),
    turn (routes undead/wraith), blizzard (4-tile frost + slow), invis (ghost walk),
    mark/recall (per-hero hearthmark, frontier-safe, save-kept). Book now 18 + fusions.
    Headless selftest + smoke passed.
19. PyInstaller exe + clean-machine test + player-facing docs (FINAL).

## Session recipe
1. Read this file + `ascii_rpg/README.md`.
2. Implement ONE queued item. 3. Headless test it (new selftest, fixed seeds). 4. Render-smoke UI changes.
5. Update README rules. 6. `update.bat` to sync E:. 7. Update THIS file's "Feature state".

## Footnotes (noted Oct 2026, NOT queued — do not implement yet)
- Class forge transparency: the calling-pick screen should brief each class
  (desc + attrs/skills/gear/spells/art it grants) before confirming.
- Shrine spell leveling: a shrine may offer an already-known spell; instead of
  "already learnt", it raises that spell's level (+damage for combat spells).
