# In your_app/management/commands/add_daily_earnings.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from investment_app.models import Investment, UserProfile, DailyEarning

class Command(BaseCommand):
    help = 'Adds daily earnings from investments to user total earnings'
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Check if we've already processed earnings for today
        if DailyEarning.objects.filter(date=today).exists():
            self.stdout.write(self.style.WARNING('Daily earnings already processed for today'))
            return
        
        # Get all active investments
        active_investments = Investment.objects.filter(
            status='active',
            end_date__gte=today
        )
        
        earnings_added = 0
        with transaction.atomic():
            for investment in active_investments:
                # Calculate daily earning based on your investment plan
                daily_earning = investment.calculate_daily_earning()
                
                if daily_earning > 0:
                    # Create daily earning record
                    DailyEarning.objects.create(
                        user=investment.user,
                        amount=daily_earning,
                        date=today,
                        investment=investment
                    )
                    
                    # Update user's total earnings and wallet balance
                    profile, created = UserProfile.objects.get_or_create(
                        user=investment.user,
                        defaults={'total_earnings': Decimal('0.00'), 'wallet_balance': Decimal('0.00')}
                    )
                    
                    profile.total_earnings += daily_earning
                    profile.wallet_balance += daily_earning
                    profile.save()
                    
                    earnings_added += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully added daily earnings for {earnings_added} investments')
        )