-- 007_add_preparation_steps.sql
-- 为 cocktails 表增加结构化调制步骤列（JSONB）
-- 格式: [{"order": 1, "text": "...", "duration_hint": "..."}, ...]

ALTER TABLE cocktails
    ADD COLUMN IF NOT EXISTS preparation_steps JSONB;

COMMENT ON COLUMN cocktails.preparation_steps IS
    '结构化调制步骤，由 LLM 生成。格式：[{"order":int,"text":str,"duration_hint":str|null}]';
