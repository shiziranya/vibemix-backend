-- ============================================================
-- Migration 002: Add LLM output columns to recommendation_history
-- ============================================================
-- ai_steps      : LLM-generated step-by-step instructions
-- ai_ingredients: LLM-generated ingredient list with precise measures

ALTER TABLE recommendation_history
    ADD COLUMN IF NOT EXISTS ai_steps       JSONB,
    ADD COLUMN IF NOT EXISTS ai_ingredients JSONB;

-- Optional: back-fill existing rows with empty arrays
-- (safe to skip; NULL is handled gracefully by the application)
-- UPDATE recommendation_history SET ai_steps = '[]'::jsonb WHERE ai_steps IS NULL;
-- UPDATE recommendation_history SET ai_ingredients = '[]'::jsonb WHERE ai_ingredients IS NULL;
