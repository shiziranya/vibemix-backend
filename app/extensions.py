from __future__ import annotations
import redis
from celery import Celery
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
celery = Celery()

_redis_client = None


def get_redis(app=None):
    global _redis_client
    if _redis_client is None:
        from flask import current_app

        cfg = app or current_app
        _redis_client = redis.from_url(
            cfg.config["REDIS_URL"], decode_responses=True
        )
    return _redis_client


def init_celery(app):
    # 导入 beat schedule 配置
    from celerybeat_schedule import beat_schedule
    
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_time_limit=60,
        worker_concurrency=4,
        beat_schedule=beat_schedule,  # 添加定时任务配置
        timezone='Asia/Shanghai',  # 设置时区
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
