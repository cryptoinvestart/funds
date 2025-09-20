from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from investment_app.models import Referral, UserProfile, Transaction

class Command(BaseCommand):
    help = 'Process referral bonuses every 3 months'
    
    def handle(self, *args, **options):
        three_months_ago = timezone.now() - timedelta(days=90)
        unpaid_referrals = Referral.objects.filter(
            created_at__lte=three_months_ago,
            bonus_paid=False
        )
        
        for referral in unpaid_referrals:
            # Get all investments made by the referred user
            referred_investments = referral.referred_user.investment_set.all()
            total_deposits = sum(inv.amount for inv in referred_investments)
            
            # Calculate 2% bonus
            bonus_amount = total_deposits * Decimal('0.02')
            
            if bonus_amount > 0:
                # Update referrer's profile
                referrer_profile = UserProfile.objects.get(user=referral.referrer)
                referrer_profile.wallet_balance += bonus_amount
                referrer_profile.total_referral_bonus += bonus_amount
                referrer_profile.save()
                
                # Create transaction for referral bonus
                Transaction.objects.create(
                    user=referral.referrer,
                    transaction_type='referral',
                    amount=bonus_amount,
                    status='completed'
                )
                
                # Mark referral as paid
                referral.bonus_paid = True
                referral.save()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully processed referral bonuses')
        )