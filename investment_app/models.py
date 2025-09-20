from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal, ROUND_DOWN
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid


class InvestmentPlan(models.Model):
    PLAN_CHOICES = (
        ('basic', 'Basic Plan'),
        ('standard', 'Standard Plan'),
        ('premium', 'Premium Plan'),
    )
    
    name = models.CharField(max_length=100, choices=PLAN_CHOICES, unique=True)
    daily_return = models.DecimalField(max_digits=5, decimal_places=2)  # in percentage
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.get_name_display()} ({self.daily_return}% daily)"
    
    class Meta:
        ordering = ['min_deposit']

class Investment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey('InvestmentPlan', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    total_return = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    referral_bonus_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_confirmed = models.BooleanField(default=False, verbose_name="Confirmed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def clean(self):
        """Validate investment amount against plan minimum"""
        super().clean()
        if self.plan and self.amount < self.plan.min_deposit:
            raise ValidationError(
                f"Investment amount must be at least ${self.plan.min_deposit} for {self.plan.get_name_display()}"
            )
    
    def save(self, *args, **kwargs):
        # Run validation before saving
        self.full_clean()
        
        # Set end_date based on plan duration if not set
        if not self.end_date and self.plan:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        
        # Auto-complete investments that have passed their end date
        if (self.status == 'active' and self.end_date and 
            timezone.now() > self.end_date):
            self.status = 'completed'
            self.total_return = self.calculate_total_return()
        
        super().save(*args, **kwargs)
    
    def calculate_daily_return(self):
        """Calculate daily return based on plan's daily return percentage"""
        if self.plan and self.status == 'active':
            daily_return = (self.amount * self.plan.daily_return) / 100
            return daily_return.quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def calculate_total_return(self):
        """Calculate total return if investment was completed"""
        if self.status == 'completed' and self.plan and self.start_date and self.end_date:
            total_days = (self.end_date - self.start_date).days
            daily_return = self.calculate_daily_return()
            total_return = daily_return * total_days
            return total_return.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')
    
    @property
    def current_value(self):
        """Calculate current investment value including earned returns"""
        if self.status == 'active':
            days_elapsed = self.days_elapsed
            daily_return = self.calculate_daily_return()
            earned_returns = daily_return * days_elapsed
            return (self.amount + earned_returns).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        elif self.status == 'completed':
            return (self.amount + self.total_return).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return self.amount  # For pending or cancelled investments
    
    @property
    def days_remaining(self):
        """Calculate days remaining until investment completion"""
        if self.end_date and self.status == 'active':
            today = timezone.now()
            remaining = (self.end_date - today).days
            return max(0, remaining)
        return 0
    
    @property
    def days_elapsed(self):
        """Calculate days since investment started"""
        if self.start_date:
            today = timezone.now()
            elapsed = (today - self.start_date).days
            return max(0, elapsed)
        return 0
    
    @property
    def is_active(self):
        """Check if investment is currently active"""
        return self.status == 'active' and self.days_remaining > 0
    
    @property
    def progress_percentage(self):
        """Calculate investment progress percentage"""
        if self.plan and self.plan.duration_days > 0 and self.status == 'active':
            elapsed = self.days_elapsed
            total = self.plan.duration_days
            return min(100, (elapsed / total) * 100)
        return 100 if self.status == 'completed' else 0
    
    def calculate_referral_bonus(self, referral_percentage=5):
        """
        Calculate referral bonus for this investment
        Default: 5% of the investment amount
        """
        bonus = (self.amount * Decimal(referral_percentage)) / 100
        return bonus.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    
    def award_referral_bonus(self, referrer, referral_percentage=5):
        """Award referral bonus to the referrer"""
        from .models import UserProfile  # Import here to avoid circular imports
        
        if referrer and referrer != self.user:
            bonus_amount = self.calculate_referral_bonus(referral_percentage)
            
            # Update referrer's profile
            try:
                referrer_profile = UserProfile.objects.get(user=referrer)
                referrer_profile.total_referral_bonus += bonus_amount
                referrer_profile.wallet_balance += bonus_amount
                referrer_profile.save()
                
                # Update investment record
                self.referral_bonus_earned = bonus_amount
                self.save()
                
                return bonus_amount
            except UserProfile.DoesNotExist:
                pass
        
        return Decimal('0.00')
    
    def confirm_investment(self):
        """Confirm the investment and update status"""
        if not self.is_confirmed:
            self.is_confirmed = True
            self.status = 'active'
            self.save()
    
    def complete_investment(self):
        """Mark investment as completed and calculate final returns"""
        if self.status == 'active':
            self.status = 'completed'
            self.total_return = self.calculate_total_return()
            self.save()
    
    def cancel_investment(self):
        """Cancel the investment"""
        if self.status in ['pending', 'active']:
            self.status = 'cancelled'
            self.save()
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.get_name_display()} - ${self.amount}"
    

class Transaction(models.Model):
    TYPE_CHOICES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('return', 'Daily Return'),
        ('referral', 'Referral Bonus'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, null=True, blank=True)
    reference_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"

class Referral(models.Model):
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referred_by')
    created_at = models.DateTimeField(default=timezone.now)
    bonus_paid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.referrer.username} referred {self.referred_user.username}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    referral_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    total_earnings = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    today_earnings = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    weekly_earnings = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_referral_bonus = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    wallet_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
    
    def generate_referral_code(self):
        return f"REF{self.user.id:06d}{UserProfile.objects.count() + 1:04d}"

    User.add_to_class('referrals', 
        models.ManyToManyField('self', 
            symmetrical=False, 
            related_name='referrers',
            blank=True
        )
    )
    
    def __str__(self):
        return f"{self.user.username}'s Profile"


class CryptoWallet(models.Model):
    CRYPTO_CHOICES = (
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('BSC', 'Binance Smart Chain'),
        ('USDT', 'Tether'),
        ('USDC', 'USD Coin'),
    )
    
    network = models.CharField(max_length=10, choices=CRYPTO_CHOICES)
    wallet_address = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.get_network_display()} - {self.wallet_address[:10]}..."
    
class DailyEarning(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    investment = models.ForeignKey('Investment', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'date']

class Deposit(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    crypto_wallet = models.ForeignKey(CryptoWallet, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_in_crypto = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    transaction_hash = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_deposits')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reference_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    screenshot = models.ImageField(upload_to='deposit_screenshots/', blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = self.generate_reference_id()
        super().save(*args, **kwargs)
    
    def generate_reference_id(self):
        return f"DEP{self.created_at.strftime('%Y%m%d')}{Deposit.objects.count() + 1:04d}"

    
    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.get_status_display()}"
    
    class Meta:
        ordering = ['-created_at']