from celery import Celery
from celery.schedules import crontab


celery_app = Celery(
    "hotel",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=['app.tasks']  
)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

celery_app.conf.timezone = "UTC"

celery_app.conf.beat_schedule = {
    "update-room-status-every-day": {
        "task": "app.tasks.update_room_statuses",
        "schedule": crontab(hour=0, minute=0),
    },
}