# In celery.py
from celery import Celery
from celery.schedules import crontab

app = Celery('your_project')
app.conf.beat_schedule = {
    'add-daily-earnings': {
        'task': 'your_app.tasks.add_daily_earnings_task',
        'schedule': crontab(hour=0, minute=0),  # Run daily at midnight
    },
}