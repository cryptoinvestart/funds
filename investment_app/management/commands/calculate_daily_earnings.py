# investment_app/management/commands/calculate_daily_earnings.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from investment_app.models import Investment, Transaction, DailyEarning, UserProfile
from django.db import transaction

class Command(BaseCommand):
    help = 'Calculate daily earnings for all active investments'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        active_investments = Investment.objects.filter(status='active')
        
        total_earnings = Decimal('0.00')
        processed_users = set()
        
        with transaction.atomic():
            for investment in active_investments:
                # Skip if we've already processed this user today
                if investment.user.id in processed_users:
                    continue
                    
                daily_return = investment.calculate_daily_return()
                
                if daily_return > 0:
                    # Check if daily earning already exists for this user today
                    daily_earning, created = DailyEarning.objects.get_or_create(
                        user=investment.user,
                        date=today,
                        defaults={
                            'amount': daily_return,
                            'investment': investment
                        }
                    )
                    
                    if not created:
                        # Update existing record
                        daily_earning.amount += daily_return
                        daily_earning.save()
                    
                    # Create transaction for daily return
                    Transaction.objects.create(
                        user=investment.user,
                        transaction_type='return',
                        amount=daily_return,
                        status='completed',
                        investment=investment
                    )
                    
                    # Update user's total earnings and wallet balance
                    profile = UserProfile.objects.get(user=investment.user)
                    profile.total_earnings += daily_return
                    profile.wallet_balance += daily_return
                    profile.save()
                    
                    total_earnings += daily_return
                    processed_users.add(investment.user.id)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully calculated daily earnings for {len(processed_users)} users. '
                f'Total earnings: ${total_earnings}'
            )
        )