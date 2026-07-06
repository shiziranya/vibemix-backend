from __future__ import annotations
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-change-in-prod")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 7200))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", 2592000))
    )

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SUPABASE_DATABASE_URL",
        "postgresql://postgres:postgres123@localhost:5432/tipsy_inspirations",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Celery
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
    )

    # LLM provider selector: "doubao" | "deepseek"
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "doubao")

    # Doubao LLM
    ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
    DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL = os.environ.get("DOUBAO_MODEL", "doubao-seed-1-8-251228")
    # HTTP 总超时（秒）；豆包首 token 较慢，默认 60，可用 DOUBAO_LLM_TIMEOUT 覆盖
    DOUBAO_LLM_TIMEOUT = float(os.environ.get("DOUBAO_LLM_TIMEOUT", "60"))
    # 最大输出 token 数；典型输出约 600-900 tokens，1200 已有充足余量
    DOUBAO_MAX_TOKENS = int(os.environ.get("DOUBAO_MAX_TOKENS", "1200"))
    # 思考强度：minimal=不思考（默认）| low | medium | high
    DOUBAO_REASONING_EFFORT = os.environ.get("DOUBAO_REASONING_EFFORT", "minimal")

    # DeepSeek LLM
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    # 可选模型：deepseek-chat / deepseek-reasoner / deepseek-v4-pro 等
    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_LLM_TIMEOUT = float(os.environ.get("DEEPSEEK_LLM_TIMEOUT", "60"))
    DEEPSEEK_MAX_TOKENS = int(os.environ.get("DEEPSEEK_MAX_TOKENS", "1200"))
    # 思考强度：留空=不启用 thinking，"low"|"medium"|"high" 启用（仅 reasoning 模型支持）
    DEEPSEEK_REASONING_EFFORT = os.environ.get("DEEPSEEK_REASONING_EFFORT", "")

    # Supabase Storage
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
    SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "vibemix")

    # Public base URL for constructing absolute asset URLs (no trailing slash)
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5005")

    # WeChat Mini Program
    WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # Upload limits (card submit allows up to 20 MB for frontend-rendered images)
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ECHO = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
