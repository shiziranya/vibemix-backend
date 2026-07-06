-- Migration 006: 新增微信小程序登录支持
--
-- 变更内容：
--   1. users 表新增 openid 列（微信用户唯一标识）
--   2. users 表 phone、password_hash 改为可选（微信用户不需要手机号/密码）
--
-- psql -d tipsy_inspirations -f 006_add_wechat_login.sql

BEGIN;

-- 新增 openid 列，后续通过 UPDATE 填充旧用户（旧用户为 NULL）
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS openid VARCHAR(64);

-- openid 唯一索引（跳过 NULL 值）
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_openid
    ON users (openid)
    WHERE openid IS NOT NULL;

-- phone 和 password_hash 改为可选（微信登录用户不需要这两个字段）
ALTER TABLE users
    ALTER COLUMN phone       DROP NOT NULL,
    ALTER COLUMN password_hash DROP NOT NULL;

COMMIT;
