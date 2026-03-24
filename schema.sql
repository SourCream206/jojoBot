-- ============================================================
-- JoJo Discord RPG — Supabase Schema
-- Run this entire file in the Supabase SQL editor
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- USERS
-- ────────────────────────────────────────────────────────────
CREATE TABLE users (
    id                      TEXT PRIMARY KEY,           -- Discord user ID
    username                TEXT NOT NULL,
    coins                   INTEGER DEFAULT 0,
    diamonds                INTEGER DEFAULT 0,
    current_area            TEXT DEFAULT 'Cairo',
    level                   INTEGER DEFAULT 1,
    exp                     INTEGER DEFAULT 0,
    pity_counter            INTEGER DEFAULT 0,          -- Rolls since last Legendary
    mythical_pity_counter   INTEGER DEFAULT 0,          -- Rolls since last Mythical
    win_count               INTEGER DEFAULT 0,
    loss_count              INTEGER DEFAULT 0,
    daily_streak            INTEGER DEFAULT 0,
    last_daily              TIMESTAMPTZ,
    bio                     TEXT DEFAULT '',
    profile_image_url       TEXT DEFAULT '',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
-- USER STANDS
-- ────────────────────────────────────────────────────────────
CREATE TABLE user_stands (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    stand_name  TEXT NOT NULL,
    level       INTEGER DEFAULT 1,
    exp         INTEGER DEFAULT 0,
    stars       INTEGER DEFAULT 1,
    merge_count INTEGER DEFAULT 0,                      -- Times this stand has been merged
    is_shiny    BOOLEAN DEFAULT FALSE,
    nickname    TEXT DEFAULT '',
    is_primary  BOOLEAN DEFAULT FALSE,
    obtained_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enforce only one primary stand per user at the DB level
CREATE UNIQUE INDEX one_primary_per_user
    ON user_stands (user_id)
    WHERE is_primary = TRUE;


-- ────────────────────────────────────────────────────────────
-- ITEMS
-- ────────────────────────────────────────────────────────────
CREATE TABLE items (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    item_id     TEXT NOT NULL,                          -- e.g. 'xpPotion', 'actStone', 'requiemArrow'
    quantity    INTEGER DEFAULT 0,
    UNIQUE(user_id, item_id)
);


-- ────────────────────────────────────────────────────────────
-- USER QUESTS
-- ────────────────────────────────────────────────────────────
CREATE TABLE user_quests (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    quest_id        TEXT NOT NULL,
    progress        INTEGER DEFAULT 0,
    completed       BOOLEAN DEFAULT FALSE,
    completed_at    TIMESTAMPTZ,
    refreshes_at    TIMESTAMPTZ,                        -- NULL for one-time story quests
    UNIQUE(user_id, quest_id)
);


-- ────────────────────────────────────────────────────────────
-- BATTLE LOG
-- ────────────────────────────────────────────────────────────
CREATE TABLE battle_log (
    id              SERIAL PRIMARY KEY,
    attacker_id     TEXT REFERENCES users(id),
    defender_id     TEXT,                               -- NULL for PvE
    winner_id       TEXT,
    stand_used      TEXT,
    xp_gained       INTEGER,
    coins_gained    INTEGER,
    is_pvp          BOOLEAN DEFAULT FALSE,
    fought_at       TIMESTAMPTZ DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
-- ACTIVE BATTLES  (snapshot for timeout/restart resolution)
-- ────────────────────────────────────────────────────────────
CREATE TABLE active_battles (
    id              SERIAL PRIMARY KEY,
    attacker_id     TEXT REFERENCES users(id),
    defender_id     TEXT,                               -- NULL for PvE
    attacker_hp     INTEGER NOT NULL,
    defender_hp     INTEGER NOT NULL,
    turn            TEXT NOT NULL,                      -- 'attacker' | 'defender'
    state           JSONB,                              -- full BattleSession snapshot
    is_pvp          BOOLEAN DEFAULT FALSE,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL
);


-- ────────────────────────────────────────────────────────────
-- BATTLE QUEUE  (PvP challenge queue)
-- ────────────────────────────────────────────────────────────
CREATE TABLE battle_queue (
    id              SERIAL PRIMARY KEY,
    challenger_id   TEXT REFERENCES users(id) ON DELETE CASCADE,
    target_id       TEXT REFERENCES users(id) ON DELETE CASCADE,
    queued_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,               -- queued_at + 10 minutes
    status          TEXT DEFAULT 'pending'              -- 'pending' | 'accepted' | 'declined' | 'expired'
);


-- ────────────────────────────────────────────────────────────
-- PENDING EVOLUTIONS  (Act Stone held until level threshold)
-- ────────────────────────────────────────────────────────────
CREATE TABLE pending_evolutions (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT REFERENCES users(id) ON DELETE CASCADE,
    stand_id        INTEGER REFERENCES user_stands(id) ON DELETE CASCADE,
    item_id         TEXT NOT NULL,                      -- 'actStone' | 'requiemArrow'
    required_level  INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
-- COOLDOWNS
-- ────────────────────────────────────────────────────────────
CREATE TABLE cooldowns (
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    command     TEXT NOT NULL,                          -- e.g. 'sroll', 'sdaily', 'sdarby'
    expires_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, command)
);


-- ────────────────────────────────────────────────────────────
-- PLAYER UNLOCKED STANDS
-- (Corpse Parts + any future special unlock mechanism)
-- ────────────────────────────────────────────────────────────
CREATE TABLE player_unlocked_stands (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    stand_name  TEXT NOT NULL,
    unlock_type TEXT NOT NULL,                          -- 'corpse_part' | 'event' | 'quest'
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, stand_name)
);


-- ────────────────────────────────────────────────────────────
-- AREA UNLOCKS  (tracks which areas a user has unlocked)
-- ────────────────────────────────────────────────────────────
CREATE TABLE area_unlocks (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
    area_name   TEXT NOT NULL,
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, area_name)
);

-- Cairo is always unlocked — seed it on user creation via a trigger
CREATE OR REPLACE FUNCTION unlock_cairo_on_register()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO area_unlocks (user_id, area_name)
    VALUES (NEW.id, 'Cairo');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_unlock_cairo
    AFTER INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION unlock_cairo_on_register();
