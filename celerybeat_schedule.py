"""
Celery Beat 定时任务配置
"""
from celery.schedules import crontab

# Celery Beat 定时任务配置
beat_schedule = {
    # 每小时执行一次清理未收藏的过期卡片（24 小时前）
    'cleanup-unfavorited-cards': {
        'task': 'cleanup_unfavorited_cards',
        'schedule': crontab(minute=0),  # 每小时的第 0 分钟执行
        'options': {
            'expires': 3600,  # 任务过期时间（秒）
        }
    },
}

# 如果需要更频繁的清理（用于测试），可以改为：
# 'schedule': crontab(minute='*/10'),  # 每 10 分钟执行一次
