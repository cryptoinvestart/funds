# In tasks.py
from celery import shared_task
from django.utils import timezone
from investment_app.management.commands.add_daily_earnings import Command as DailyEarningsCommand

@shared_task
def add_daily_earnings_task():
    command = DailyEarningsCommand()
    command.handle()