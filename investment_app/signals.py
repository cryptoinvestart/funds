# In signals.py
from django.db.models.signals import post_save, pre_save
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.utils import timezone
from .models import Deposit, CryptoWallet, Investment
from decimal import Decimal

@receiver(post_save, sender=Deposit)
def update_user_balance_on_deposit_confirmation(sender, instance, **kwargs):
    if instance.status == 'confirmed':
        # Check if we need to update balance (only if previously not confirmed)
        try:
            old_instance = Deposit.objects.get(pk=instance.pk)
            if old_instance.status != 'confirmed':
                user_balance, created = CryptoWallet.objects.get_or_create(
                    user=instance.user,
                    defaults={'balance': Decimal('0.00')}
                )
                user_balance.balance += instance.amount
                user_balance.save()
        except Deposit.DoesNotExist:
            # New instance, handle accordingly
            pass


@receiver(pre_save, sender=Investment)
def validate_investment_amount(sender, instance, **kwargs):
    """
    Signal to validate investment amount against plan minimum before saving
    """
    if instance.plan and instance.amount < instance.plan.min_deposit:
        raise ValidationError(
            f"Investment amount must be at least ${instance.plan.min_deposit} "
            f"for {instance.plan.get_name_display()}"
        )


@receiver(post_save, sender=Investment)
def handle_investment_status_change(sender, instance, created, **kwargs):
    """
    Signal to handle investment status changes and automatic actions
    """
    from .models import UserProfile
    
    if created:
        # New investment created
        print(f"New investment created: {instance}")
    
    # Handle investment confirmation
    if instance.is_confirmed and instance.status == 'pending':
        instance.status = 'active'
        instance.save()
    
    # Handle completed investments
    if instance.status == 'completed' and instance.total_return == 0:
        # Calculate and assign total returns for completed investments
        instance.total_return = instance.calculate_total_return()
        
        # Add returns to user's wallet
        try:
            user_profile = UserProfile.objects.get(user=instance.user)
            user_profile.wallet_balance += instance.total_return
            user_profile.total_earnings += instance.total_return
            user_profile.save()
        except UserProfile.DoesNotExist:
            pass
        
        instance.save()


@receiver(post_save, sender=Investment)
def check_investment_completion(sender, instance, **kwargs):
    """
    Signal to automatically complete investments that have passed their end date
    """
    if (instance.status == 'active' and instance.end_date and 
        timezone.now() > instance.end_date):
        instance.complete_investment()