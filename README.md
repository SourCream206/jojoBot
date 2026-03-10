# Stand Arena v2.0 — JoJo's Bizarre Adventure Discord Bot

A full-featured collectible RPG Discord bot based on the design document.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and set your DISCORD_TOKEN
   ```

3. **Configure channel IDs** in the relevant cog files:
   - `bot/cogs/social.py` → Set `SUGGESTION_CHANNEL_ID`
   - `bot/cogs/admin.py` → Set `ANNOUNCE_CHANNELS`

4. **Run the bot:**
   ```bash
   python main.py
   ```

5. **Migrate old JSON data** (first run only):
   ```
   Smigratejson
   ```

---

## Architecture

```
standarena/
├── main.py                   # Bot entry point, cog loader
├── requirements.txt
├── bot/
│   ├── config.py             # All constants, weights, cooldowns
│   ├── cogs/
│   │   ├── acquisition.py    # Roll, daily, craft, use, dismantle
│   │   ├── combat.py         # Duel, D'Arby, rank, leaderboard
│   │   ├── progression.py    # Stands, profile, train, quests
│   │   ├── economy.py        # Balance, shop, pay, richlist
│   │   ├── exploration.py    # Explore, dungeon, map, search
│   │   ├── social.py         # Gangs, slime, kiss, suggest
│   │   ├── events.py         # Pucci quest, meteor, raids
│   │   └── admin.py          # Bless, announce, migrate, help
│   ├── utils/
│   │   └── helpers.py        # Stand loading, normalization, embeds
│   └── data/
│       └── stands.json       # Stand roster (your existing file)
└── db/
    ├── manager.py            # SQLite abstraction (aiosqlite)
    └── standarena.db         # Created automatically on first run
```

---

## Command Reference

| Category    | Commands |
|-------------|----------|
| Rolling     | `Sroll`, `Sdaily`, `Srollrare`, `Srollepic`, `Scd` |
| Stands      | `Sstands`, `Sprofile`, `Sequip`, `Sstat`, `Smerge`, `Sdismantle` |
| Crafting    | `Scraft`, `Suse` |
| Combat      | `Sduel @user`, `Sspar @user`, `Srank`, `Sleaderboard` |
| Exploration | `Sexplore`, `Sdungeon`, `Smap`, `Ssearch` |
| Economy     | `Sbalance`, `Sshop`, `Sbuy`, `Spay`, `Srichlist` |
| Progression | `Strain`, `Sstandby`, `Squests`, `Sachievements`, `Scompendium` |
| Social      | `Sgang`, `Sslime`, `Skiss`, `Ssuggest` |
| Events      | `Spucci`, `Sdarby` (needs ★2 Osiris) |
| Admin       | `Sbless`, `Sgivestand`, `Sgivecurrency`, `Sannounce`, `Sdm`, `Smigratejson` |

---

## Key Design Changes from v1

| Old | New |
|-----|-----|
| `user_inventories.json` | SQLite via `aiosqlite` |
| 4,000-line monolith | 8 focused cogs |
| No currency | Hamon / Stand Dust / SOS Shards |
| 5-copy merge only | Dismantle for Dust + fuse for star-up |
| Static rolls | Pity counter (guaranteed Legendary at 50) |
| Random channel spawns | Player-triggered exploration |
| No PvP system | Full turn-based duel with ELO ranking |
| No gang system | Full gang creation, treasury, wars |
| No quest system | Daily + weekly quests |
