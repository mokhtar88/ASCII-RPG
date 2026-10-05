# Inkbound Realms — book-driven ASCII RPG

Adventure RPG with procedurally generated world where **cities, characters,
races and quests are extracted from books you upload**, then renamed/mutated
so the world feels unique.

- Graphics: drawn-sprite tiles in a `pygame` window by default (house/tree/mountain/wave icons), pure-ASCII toggle in Settings
- Books: drop `.txt` / `.pdf` / `.epub` files into `books/` — the game reads them on world generation
- Gameplay: explore, talk (E), turn-based combat (A attack / F flee), heal in cities (H), journal (J), unique deliver/bounty/explore quests, XP levels

## Quick start

```bash
cd ascii_rpg
pip install -r requirements.txt
python main.py                        # title menu: NEW GAME / LOAD GAME, then 7 tabs
python main.py --save slot1 --seed 42 --regen --ascii-preview   # terminal map test, no pygame
```

Or skip the terminal: double-click **`run.bat`** (Windows) or run `./run.sh` (macOS/Linux).
It installs missing libraries on first run, then launches the game.

## Updating your play copy

I build here, you play on E:. After I announce updates, double-click **`update.bat`**
in this folder — it copies the new code to `E:\ascii_rpg`, backs up your saves to
`E:\ascii_rpg_saves_backup` first, and never touches your `saves/`, `books/`,
`config.json` or `run.log`. To retarget it, edit `TARGET=` at the top of the file.

## Tabs (keys 1-7, or click)

- `1 MAP` — overworld with sidebar (HP/XP/mana bars, quest tracker, live minimap, clock).
  Move WASD/arrows, E talk/enter/delve, H heal, Z rest (inn 3g / free camp), B shop in town,
  F caravan in city, C spells, T track quest, J journal, R rise if fallen. `O` city, `D` dungeon, `#` ruin, `*` shrine,
  `=` road, `!` watchtower, `X` bandit camp, `v` farm.
- `2 CHARACTERS` — roster **per save**. Enter switches the `@`, N creates (name → race →
  calling → attributes), D deletes, Tab spends level-up points.
- `3 BOOKS` — shows `books/` docs. Drop in `.txt/.pdf/.epub`, press R to rebirth the world from them.
- `4 SAVES` — infinite worlds: N new save (= new seed), Enter load, D delete. Stored in `saves/<name>/`.
- `5 SETTINGS` — graphics (icons/ascii), tile size, difficulty, color. S saves.
- `6 INVENTORY` — worn gear + pack. Enter wears/takes off (or uses a consumable),
  D destroys. Potion/bomb/smoke are lootable, buyable, and usable here or mid-fight.
- `7 DATA` — provenance ledger: every soul, place, folk, calling and motif with the
  book name it came from (gold) or marked winds-invented (dim). Up/Down scrolls.

## Rules of the realm

- Worlds are 300x170 (and grow forever at the edges) with ~50 cities, ~120 souls,
  ~48 wild sites and ~57 rumors. Density scales with area, so bigger stays full.
- DF-style generation: elevation/moisture noise → oceans, lakes, rivers, deserts,
  forests, mountain ranges; 6 named regions; cities get founding years + founders.

## Elements & specialties

- Every shelf has elemental weather (ember/frost/storm/umbral, counted from the
  books): foes attune to it, loot rolls it, and natives resist what's common —
  so the clever answer changes with every library.
- Names that make sense: a noun-only relic pool (real book entities —
  "Ring of Aldor", "Thornwall Bow", "Amulet of Seaborn") feeds blades, foes, and
  spells. Every quest verb speaks in several voices; townsfolk have six barks.
- Typed damage with weaknesses (+50%, WEAK!) and resistances (halved, resisted):
  wraiths/golems shrug steel, drakes breathe ember and fear frost, the dead fear fire.
  Weapons come element-tongued, armor comes warded; drakes and wraiths hit back typed.
- Ember sets foes burning (kills count for bounties). Boss triumph (+3 ATK) and farm
  feast (regen) are real buffs ticking in the sidebar.

## Heroes, magic, dungeons
- New Game forges a hero: name → race (the books' own peoples, each with SRD-harvest
  bloodline boosts) → calling (the books' own words — Mage *and* Necromancer,
  Captain *and* Guard… — each derivative with its own desc, stat twists, styled
  starting blade, and sometimes its own spell; rangers draw bows, clerics carry
  turn) → 8 attribute points. Callings grant starting gear, skills,
  and spells (Sorcerer and Paladin join the classic six), plus one art worked
  with P on the wilds: battle-cry, overchannel, double volley (1 arrow), vanish, consecrate,
  inspire (+5g a tale, cheaper caravans, longer charms), wild surge, lay hands — each on its own clock, shown on
  the roster with readiness. Paladins shield their charges (-1 companion nicks);
  Assassins crit the slowed from the shadows; Thieves lay +1 traps.
- Mana (WIS-based, +1/step) and an 18-spell lore-named book: bolt, spark, smite, mend,
  blink, ward (damage shield), charm (turn a blade), sight — five road-signs
  (igni AoE, aard push, yrden slow, fury frenzy, frostbite) — and five canon signs:
  summon (spectral wolf ally, 25 steps), turn (route the dead), blizzard (4-tile storm),
  invis (unseen 12 steps), mark (set a hearth, cast again to return). C opens the book
  (Left/Right flips pages), 1-9 casts — even mid-fight. Shrines (`*`) teach what you lack and
  fuse known spells with elements (N); Arcana cheapens every casting. Each shrine
  teaches one spell ever — seek new stones for new words.
- Dungeons and ruins are enterable (E on the tile): 1, 3, or 5 seeded floors
  (E on (>) climbs down, (<) climbs out or up); each floor is seed-built
  rooms/corridors with wandering foes, loot chests, ruin tablets (+Lore, whisper rumors),
  and the boss waiting on the last floor — usually your bunkered bounty target.
  Layouts are free (seed-derived); only boss/chest/tablet memory is saved.
- Cities are walkable towns (E on the tile): bigger streets for bigger tiers,
  houses, an inn (Z sleeps), 1-3 shop doors with split stock (B nearby), and
  wandering locals with jobs: merchants report stock, healers mend 10hp free daily,
  scouts mark the nearest wild site, elders teach history, guards brief wars.
  Talk (E) for gossip, per-giver rumors, and turn-ins; gates (G) lead out.
- Steadings dot the wilds: watchtowers (`!`, survey the horizon), bandit camps
  (`X`, clear the guards, loot the cache once), farms (`v`, one hot meal a day).

## Deep history

- Every world simulates ~800 years before you arrive: foundings, faction wars and
  battles, sacked-and-rebuilt cities, fallen ruins, born and slain heroes, and 2-4
  named artifacts forged, lost, and waiting in specific dungeon chests.
- The past surfaces in play: ruins tell how they fell, bosses arrive with legends
  ("below waits X, who broke at ..."), towns remember tidbits, and the DATA tab
  ends with the full chronological ANNALS. Frontier foundings join the record.
- **Game feel:** synthesized retro SFX (no files, mutable in Settings), floating damage
  numbers, hit flashes, a quest compass (gold arrow/ring + T to re-track, minimap dots),
  and caravans (F in visited cities: gold fare, clock passes, 15% road ambush).
- **Infinite frontier**: walk to any map edge and the world grows (new land, towns,
  wild sites, regions, rumors, foes) — seamlessly, forever. Every save keeps growing.
- Quests are unique across 10 verbs: deliver (`>`), bounty (`x`), explore (`?`),
  escort (`=`, a companion follows your `@` to the target), hunt (`+`, slay N foes),
  tribute (`$`, pay gold at the city), pilgrimage (`P`, pray at N shrines),
  treasure (`T`, stand on the buried X), relic (`%`), finale (`X`). Completed ids are
  remembered — never a rerun.
- Rumors are progressive: most start unheard and are revealed by talking (E) in the
  giver's city. Kills and discoveries can complete unheard bounties/explores directly.
  One in four bounties/hunts/escorts is urgent (4 days, red countdown, then gone).
  Every third completed tale births a linked follow-up; escorts risk midnight ambushes.

## Main tale (story plotter)

- Every world weaves one 6-beat plot from its own annals: a villain heir of a
  historical death, heirloom artifacts as mid-act MacGuffins, a far finale dungeon.
- Only the current beat is active — each completion turns the page (sidebar MAIN +
  journal checklist, gold-tracked, Acts I-III). Finale: slay the Tyrant (150+ HP).
- Victory pays out and sets the realm free: the tale ends COMPLETE, the wilds go on.
- Factions: 2-4 powers hold territory (shown in towns, with wars). Swear to one (O):
  its blades know you (free passage, cheap healing and caravans in its towns),
  its rivals watch for you. Bleed a side's soldiers to turn the tide — at 14 dead
  the war ends: the winner takes the loser's towns, the annals turn a page (new
  age, +150g peace pay), and after three days of peace old grudges kindle a new
  war. Endings close ages, never the game. Borderlands near
  warring cities crawl with extra blades. Content density scales with map area.
- Kills and quests grant XP: level-ups raise max HP and ATK. Death costs half your gold (R to rise).
- Steel has styles: swift blades quicken, great weapons cleave crowds, long spears reach two tiles.
  Bloodied thinking foes break — blades beg mercy (tribute), beasts run. Flank foes your
  companion holds (1.5x). Chanters (j) stalk old stones: they ward, mend their pack, and hurl storm.
- Blades stay up: foes telegraph heavies (HEAVY INCOMING — Defend (D) quarters it,
  Quick (Q) can spoil it). Heavy (H) hits ~1.7x at 75% accuracy but leaves you
  winded (+50% on the next reply — disengage to shed it); Quick is ~0.6x
  with a softer counter, Defend halves the next reply. Steel reaches one tile:
  neighbours can be struck without grappling. Filth (spiders most of all)
  poisons: 2hp a turn till mend/heal/rest cures it. Savages and beasts open veins:
  1hp a turn till a draught, heal, or rest staunches it (mend won't).
- Field goods: draughts (+25hp), firebombs (25 + splash burn), smokepowder (sure flee),
  quivers (+8 arrows), stoneward tonics (+15 ward) — plus nine kettle brews: swiftfoot
  (+escape), ironhide (−2/reply), focusing tea (next crits), second wind (cheat death),
  love philtre (charms), glitterbomb (blinds volleys), berserk (+6 wild aim), ghost
  (walk through), greed (richer drops), dragonbreath (strikes burn) — plus four rogue
  traps: snare (slows 6), dart (12), ember cache (burn + 8), oil slick (steals steps,
  burns double if lit). One picker (X) for all, in and out of combat (traps lay at
  your feet; foes tread, you don't — camps sow their own for heroes). Brew your own (K): wildherbs gathered in forests (G), fangs
  from beasts, venom from spiders, gravedust from the dead, scales from drakes —
  the slain keep stranger stock, and mats sell at half price like any goods.
- Bows shoot 2–4 tiles down a clear lane (R to loose; every market racks one, kills
  drop them) and drink an arrow a shot — quivers (+8, U to fletch) loot and stock
  everywhere. Up close the draw is awkward (half damage), past 4 it falls short,
  and ridges break the lane. One blade in four keeps a bowstring: archers hold range,
  back off when crowded, and loose 80% shots — close the gap or answer in kind.
  Drakes breathe ember and wraiths wail umbral at 2–3 down a lane; human steel
  quaffs one draught under half health (costs its turn); bosses roar guards in at
  two-thirds and ENRAGE at one-third.
- The road fights with you: escort companions (o on the map) trail the @, strike
  adjacent foes, and take nicks in return — beaten down, never slain (safe roads
  raise them at half health; temples restore them whole). Struck beasts howl and
  the pack answers (up to 5 near). Bosses ENRAGE at a third health: harder blows,
  hungrier heavies, charm snapped.
- Foes wander the wilds and chase within 6 tiles — same speed as you, so flight works.
  The wilds are alive: strays beyond 40 leagues move on (quest blades, bosses, and
  the charmed stay), and while the count sits under cap the dark thickens with
  newcomers at 10–16 leagues, scaled to half your level. Delves, bosses, and
  captains scale harder still.
  The bestiary: blades (E), beasts (e, keen-nosed), spiders (a, lunging), dead (U, shambling),
  wraiths (g, night-hunting), golems (M, patient stone), drakes (W, elite), soldiers (R,
  war-tough, richer). Bosses come titled (Savage/Towering/Cursed/Dread),
  scale with your level, and pay tier-4 hoard loot. Every 8th kill, a new captain
  rises with a posted bounty.
- Dungeons come themed (sunken/overgrown/scorched); towns come sized (hamlet/town/city).
  Races number 5-8 from the books; callings up to 8 (Mage *and* Necromancer can coexist).
- Eight skills: Blades, Speech, Survival, Lore, Sneak (aggro down, trained by prowling),
  Salvage (richer drops, trained by looting), Medicine (stronger healing), Arcana
  (cheaper spells). No ceilings — mastery climbs freely,
  as do levels. The wilds scale gently with your level; the deep, frontier, bosses
  and captains scale fully.
- Perk drafts every 5th level (P in CHARACTERS): 3 speak your calling, the 4th is
  wild — take ONE, the rest dissolve back into that world's own ~34-perk pool and
  may surface again. Repeats stack to rank III. Wild picks run strange: ruin
  barons, beast-calming scents, tide-turning profiteers, and Bloodprice itself
  (half your blood for ruin, cast from the book).
- Balance telemetry: DATA tab opens with your SAGA — sessions, minutes, kills,
  deaths, quests, levels per world. Play normally; your sessions become tuning data.

## Survival, attributes, skills

- A realm clock ticks as you travel (Day N, hh:mm, dawn/day/dusk/night). Darkness hides
  you: foes notice you later at night.
- Z rests: city inns (3g, sleep till dawn) or free wild camps (+8h) with ambush risk
  lowered by Survival.
- Six attributes, all load-bearing and all uncapped: STR damage, CON health,
  SPD escape/evasion, CHA prices/favors, WIS learning speed, LUK crits/loot.
  Point-buy on creation, +1 per level spent in CHARACTERS (Tab) — no ceiling,
  but floors hold (foes always notice at 3 leagues, healing never free).
- Four skills improve with use: Blades (fighting), Speech (talk/quests), Survival
  (resting/camp), Lore (exploring → faster XP).

## Gear, shops, loot

- Four slots: weapon, armor, ring, amulet. Gear adds ATK/HP/attributes into every
  formula (damage, healing cap, prices, notice radius).
- Every city market stocks lore-named gear (B on the map in town: buy, sell pack
  goods at half price, Left/Right flips panels — the third panel is the smith's
  REFORGE bench: pay gold to raise worn or packed steel a tier, cap 5, rarity
  never downgrades). Frontier towns stock better tiers.
- Kills drop loot (LUK helps), quests pay gear 35% of the time. Auto-equips into
  empty slots. INVENTORY tab (6): Enter wears/takes off, D destroys.
- Gear with a past: jewels (and odd steel) grant skill levels — a ring that makes
  your speech silver, a blade that teaches. Heirlooms carry extra craft.
- Steel scales with danger: delves and ground far from every hearth drop higher
  tiers (bosses never pay common, Dread hoards runed+), and every piece rolls
  rarity — keen, runed, mythic — with the name, stats, and price to match.

## Controls

Arrows / WASD move · E talk/interact · G gather · K brew · H heal in city (Heavy in combat) · Z rest · A attack · H heavy / Q quick / D defend · R shoot (bow 2-4) · U quiver · T tonic · O oath · P drink · B bomb · V smoke (board in towns) / V bounty board in city · Y road event when the road calls · N shrine fusion · M home room in city · F flee (caravan in city) · C spells · Q quit · F11 fullscreen (window resizes to the tile grid; Settings has the toggle too)

## The living road (director + board + book mining)

- Books are mined for happenings (slew/siege/fled/wed/betrayed/storm/plague/voyage) into `{kind, names, snippet}` with frequency voting + diversity. Top pool of 20 -> 8 three-part gated sagas (I dormant; II/III vaulted) + 12 single echoes, all with mined names as givers/targets; they seed annals entries and road cards too.
- Travel raises tension (slow base; night/war/far roads faster; cities/rest shed it) and blood (kills heat it, strides cool it). Cool blood deals calm atmosphere, hot blood deals set pieces — roughly one road card per ~40 strides, faster when bloody. At full, the road deals a context-weighted card — ruins at night, war borders, escorts — no repeats within an age, 2% mythic spikes that raise a real camp (new site + guards + history + quest), chained follow-ups 6-12 strides later with branching per choice. Movement waits until you answer (Y).
- Foreshadow: the deck whispers 2-4 days out; townsfolk quote warnings, and fulfilled whispers pay bonus xp.
- Every card offers 2-3 real choices (gold/blood/standing/time). Outcomes are remembered (20-entry ledger); townsfolk quote them back.
- Bounty boards (V in cities, refresh daily): 2-3 posted bounties/hunts per town. War hunts bleed soldiers, moving the tide. Taken postings become journal quests.

## Coin, craft, and home (economy)

- Trade winds: every city craves different pack goods (rolls every 3 days, deterministic per seed). Consumables/materials buy and sell on local spreads (gear stays flat) — loot where cheap, caravan where they pay double. Shops show the spread; merchants name the craving; caravans whisper the best market for your fattest good.
- Spellcrafting (N on a shrine): fuse a known bolt/spark/smite/mend/ward with ember/frost/storm/umbral for 2 matching mats (scales/venom/dust/fangs). Fused bolts bite typed, fused mends/wards run deeper, all cost +2 mana. Mage progression past the 8 fixed spells.
- Housing (M in a city): 200g buys a room — gear stash (flip stash/store, Enter moves), rested sleep at home (+15% learning, 120 steps), settable rise point (R toggles; death brings you home).

## How the "book → world" mechanic works

1. `src/ingest.py` extracts plain text from txt/pdf/epub.
2. `src/extract.py` finds capitalized names, ranks by frequency, classifies into
   people/places/groups via context keywords (`city of X`, `King Y`, `said`, ...).
   It also mines verb-frame happenings into `{kind, names, snippet}` (frequency-voted, diverse).
3. `src/names.py` mutates every name (vowel shifts, syllable tweaks, suffixes) so
   `Thornwall` → `Thornwick`, `Aldor` → `Eldor`, etc. Originals are kept in
   `origin_name` for debugging but never shown as-is.
4. `src/worldgen.py` builds terrain + places mutated cities/races/characters/quests.
   No books? Falls back to classic fantasy stems so the game still runs.
5. `src/director.py` paces road events from tension + the mined deck; `src/board.py`
   posts per-city daily bounties that complete through normal kills.

## Files

- `main.py` — launcher / CLI
- `src/ingest.py`, `src/extract.py`, `src/names.py`, `src/worldgen.py`, `src/game.py`
- `books/sample.txt` — demo lore to try instantly
- `world.json` — generated on first run (gitignored ideally)
