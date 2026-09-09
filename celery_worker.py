"""
Celery worker entry point.
Run with: celery -A celery_worker.celery worker --loglevel=info --concurrency=4
"""
from app import create_app
from app.extensions import celery, init_celery

app = create_app()
init_celery(app)

# Import tasks to register them
import app.tasks.card_tasks  # noqa: F401, E402
import app.tasks.cleanup_tasks  # noqa: F401, E402
