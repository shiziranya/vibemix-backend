-- ============================================================
-- Migration 001: Add recommendation tag fields to cocktails
-- ============================================================

-- New tag columns for AI recommendation filtering
ALTER TABLE cocktails
    ADD COLUMN IF NOT EXISTS mood_tags    TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS flavor_tags  TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS abv_level    VARCHAR(10) DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS difficulty   SMALLINT DEFAULT 2;

-- GIN indexes for array overlap queries (&&)
CREATE INDEX IF NOT EXISTS idx_cocktails_mood_tags
    ON cocktails USING GIN(mood_tags);

CREATE INDEX IF NOT EXISTS idx_cocktails_flavor_tags
    ON cocktails USING GIN(flavor_tags);

CREATE INDEX IF NOT EXISTS idx_cocktails_abv_level
    ON cocktails(abv_level);

-- ============================================================
-- Migration 002: Create business tables
-- ============================================================

-- Users
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone         VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    nickname      VARCHAR(50),
    avatar_url    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);


-- User cabinet
CREATE TABLE IF NOT EXISTS user_cabinet (
    id            SERIAL PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ingredient_id INT  NOT NULL REFERENCES ingredients(id),
    added_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_cabinet_user_id       ON user_cabinet(user_id);
CREATE INDEX IF NOT EXISTS idx_cabinet_ingredient_id ON user_cabinet(ingredient_id);


-- Recommendation history
CREATE TABLE IF NOT EXISTS recommendation_history (
    id            SERIAL PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id    VARCHAR(64) NOT NULL,
    cocktail_id   INT  REFERENCES cocktails(id),
    mood_tags     TEXT[],
    abv_pref      VARCHAR(10),
    flavor_tags   TEXT[],
    recipe_type   VARCHAR(20),
    free_text     TEXT,
    ai_reason     TEXT,
    ai_poetic     TEXT,
    ai_tweaks     JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rh_user_id    ON recommendation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_rh_session_id ON recommendation_history(session_id);


-- Share cards
CREATE TABLE IF NOT EXISTS share_cards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cocktail_id   INT  REFERENCES cocktails(id),
    session_id    VARCHAR(64),
    layout        VARCHAR(20) NOT NULL,
    user_photo_url TEXT,
    image_url     TEXT,
    mood_caption  TEXT,
    status        VARCHAR(20) DEFAULT 'pending',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cards_user_id ON share_cards(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_status  ON share_cards(status);
