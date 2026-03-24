# JoJo's Bizarre Adventure Discord RPG

A Pokémon-inspired Discord RPG set in the JoJo universe. Turn-based battles, area exploration, stand collection, evolution, D'Arby blackjack, and persistent data via Supabase.

---

## Setup

### 1. Prerequisites
- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- A Supabase project ([supabase.com](https://supabase.com))

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env and fill in your values:
#   DISCORD_TOKEN=...
#   SUPABASE_URL=...
#   SUPABASE_KEY=...
```

### 4. Set up the database
1. Open your Supabase project → SQL Editor
2. Paste and run the entire contents of `schema.sql`
3. That's it — all tables, indexes, and the Cairo auto-unlock trigger are created

### 5. Run the bot
```bash
python bot.py
```

---

## Commands

### 🎲 Rolls
| Command | Description |
|---------|-------------|
| `Sroll` | Roll a random stand from your current area |
| `Spity` | Check your Legendary and Mythical pity counters |

### 🎴 Inventory
| Command | Description |
|---------|-------------|
| `Sinv` | View all your stands |
| `Sinfo <stand>` | Detailed stats and moves for a stand |
| `Sequip <stand>` | Set your primary (battle) stand |
| `Smerge <stand>` | Merge 5 same-star copies into a higher star |
| `Suse <item> [stand]` | Use an item (XP Potion, Act Stone, Requiem Arrow, Corpse Part) |

### ⚔️ Battle
| Command | Description |
|---------|-------------|
| `Sbattle` | Fight a PvE enemy in your current area |
| `Sbattle @user` | Challenge another player to PvP |
| `Schallenges` | View pending PvP challenges against you |
| `Saccept <id>` | Accept a queued challenge |
| `Sdecline <id>` | Decline a queued challenge |
| `Sleaderboard wins` | Top players by win count |
| `Sleaderboard power` | Top players by stand power score |

### 🗺️ Exploration
| Command | Description |
|---------|-------------|
| `Stravel <area>` | Travel to an unlocked area (costs 50 🪙) |
| `Sarea` | View the world map and unlock status |
| `Squests daily` | View daily quests |
| `Squests weekly` | View weekly quests |
| `Squests story` | View story quest progress |

### 👤 Profile
| Command | Description |
|---------|-------------|
| `Sprofile` | View your profile |
| `Sprofile @user` | View another player's profile |
| `Sbio <text>` | Set your profile bio (max 150 chars) |

### 💰 Economy
| Command | Description |
|---------|-------------|
| `Sbalance` | Check your coins and diamonds |
| `Sdaily` | Claim your daily reward |
| `Sshop daily` | View today's daily shop |
| `Sshop weekly` | View this week's weekly shop |
| `Sbuy <item_id>` | Buy an item from the shop |
| `Sdarby <bet>` | Play Blackjack against D'Arby (requires Osiris for PvP) |

### 🔧 Admin (Administrator permission required)
| Command | Description |
|---------|-------------|
| `Sgivecoins @user <amount>` | Give coins to a user |
| `Sgivediamonds @user <amount>` | Give diamonds to a user |
| `Sgiveitem @user <item_id> [qty]` | Give an item to a user |
| `Sgivestand @user <stand>` | Give a stand to a user |
| `Sunlockarea @user <area>` | Force-unlock an area for a user |
| `Sresetcd @user <command>` | Clear a cooldown for a user |
| `Swipeuser @user` | Reset all data for a user |

---

## Areas & Progression

All areas are locked except Cairo. Unlock by meeting the level requirement **and** completing the area's story quest.

| # | Area | Unlock Requirement | Notable Stands |
|---|------|--------------------|----------------|
| 1 | Cairo | Starting area | Star Platinum, The World, Osiris, Cream |
| 2 | Morioh Town | Level 10 + Cairo story | Crazy Diamond, Killer Queen, Bites the Dust |
| 3 | Italy | Level 20 + Morioh story | Gold Experience, King Crimson, Sticky Fingers |
| 4 | Philadelphia | Level 30 + Italy story | Tusk ACT1–4 (via Corpse Parts), D4C |
| 5 | Morioh SBR | Level 40 + Philly story | Soft & Wet, Saint's Corpse Parts |

---

## Saint's Corpse Parts (Morioh SBR)

Defeat bosses in Morioh SBR to find Corpse Parts. Each part permanently unlocks a stand in your roll pool.

- **Left Arm** → Unlocks **Tusk ACT1** (guaranteed drop)
- **Heart** → Unlocks **D4C** (guaranteed drop)
- Other 7 parts: random drops (15% each per boss kill)

Use a part with `Suse <part_id>` (e.g. `Suse left_arm`).

---

## Evolution

### Act Evolutions (requires Act Stone item)
| Stand | Level Required | Evolves To |
|-------|---------------|------------|
| Echoes ACT1 | 15 | Echoes ACT2 |
| Echoes ACT2 | 25 | Echoes ACT3 |
| Tusk ACT1   | 10 | Tusk ACT2 |
| Tusk ACT2   | 20 | Tusk ACT3 |
| Tusk ACT3   | 35   | Tusk ACT4 |

### Requiem Evolutions (requires Requiem Arrow item, stand must be Lv.40+)
| Stand | Evolves To |
|-------|------------|
| Gold Experience | Gold Experience Requiem |
| Silver Chariot | Silver Chariot Requiem |

If your stand is under the required level when you use the item, it enters a **pending** state and automatically evolves when the level threshold is reached.

---

## Star System (Merging)

Use `Smerge <stand>` to combine 5 copies of the same stand **at the same star level** into one copy at the next star level. Stars affect all stats via a multiplier:

| Stars | Multiplier |
|-------|-----------|
| ★1 | 1.0× |
| ★2 | 1.1× |
| ★3 | 1.25× |
| ★4 | 1.45× |
| ★5 | 1.70× |

Shiny stands (1% roll chance) add an additional **+5%** to all stats.

---

## Meta-Passives

The stand in your **Primary Slot** (`Sequip`) provides a passive effect:

| Stand | Passive |
|-------|---------|
| Harvest | +25% Coin gain from battles |
| Star Platinum | −60s off `Sroll` cooldown |
| Osiris | +10% D'Arby win chance (+ enables PvP D'Arby) |
| Crazy Diamond | Healing items restore 25% more HP |
| Gold Experience | 5% chance to double XP after a battle |

---

## File Structure

```
jojo-rpg/
├── bot.py                      # Entry point
├── schema.sql                  # Full Supabase schema
├── requirements.txt
├── .env.example
└── src/
    ├── cogs/
    │   ├── rolls.py            # Sroll, Spity
    │   ├── inventory.py        # Sinv, Sinfo, Sequip, Smerge, Suse
    │   ├── battle.py           # Sbattle, Sleaderboard, Schallenges
    │   ├── exploration.py      # Stravel, Sarea, Squests
    │   ├── profile.py          # Sprofile, Sbio
    │   ├── economy.py          # Sdaily, Sbalance, Sshop, Sbuy, Sdarby
    │   └── admin.py            # Admin commands
    ├── db/
    │   └── client.py           # All Supabase queries
    ├── battle/
    │   ├── engine.py           # BattleSession, BattleView
    │   ├── stand.py            # Stand dataclass, stat calc
    │   ├── stand_stats.py      # All stand base stats + moves
    │   ├── ai.py               # PvE AI
    │   └── gimmicks.py         # Gimmick handlers
    └── utils/
        ├── constants.py        # All game constants + formulas
        ├── passives.py         # Meta-passive resolution
        └── embeds.py           # Shared embed builders
```

---

## Adding New Stands

1. Open `src/battle/stand_stats.py`
2. Add an entry to `STAND_CATALOG` following the existing format
3. Add it to the appropriate area pool in `src/utils/constants.py` under `STAND_POOLS`
4. That's it — the roll system, battle engine, and leaderboard pick it up automatically

---

## Notes

- The `Saccept` command's full PvP battle instantiation is marked `TODO` in `battle.py` — it mirrors the `sbattle` PvP branch exactly and is straightforward to complete
- Boss stands like `Wonder of U` in Morioh SBR are listed as PvE enemies but don't have catalog entries yet — add them to `STAND_CATALOG` when you design their movesets
- D'Arby PvP (challenging another player to blackjack) requires Osiris equipped and is a natural extension of the `Sdarby` command — add a `target: discord.Member` parameter and a `DarbyChallengeView` similar to `ChallengeView` in `battle.py`
