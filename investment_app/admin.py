from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.urls import path
from decimal import Decimal
from .models import InvestmentPlan, Investment, Transaction, Referral, UserProfile, CryptoWallet, Deposit


@admin.register(CryptoWallet)
class CryptoWalletAdmin(admin.ModelAdmin):
    list_display = ['network', 'wallet_address', 'is_active']
    list_editable = ['is_active']
    list_filter = ['network', 'is_active']

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ['user', 'crypto_wallet', 'amount', 'status', 'created_at', 'confirmed_by']
    list_filter = ['status', 'crypto_wallet__network', 'created_at']
    search_fields = ['user__username', 'transaction_hash', 'reference_id']
    readonly_fields = ['reference_id', 'created_at', 'updated_at', 'confirmed_by']
    actions = ['confirm_deposits', 'reject_deposits']
    
    def confirm_deposits(self, request, queryset):
        confirmed_count = 0
        for deposit in queryset:
            if deposit.status != 'confirmed':
                deposit.status = 'confirmed'
                deposit.confirmed_by = request.user
                deposit.save()
                
                # Add to user's wallet balance - try both approaches
                try:
                    # First approach: UserProfile model
                    profile = deposit.user.userprofile
                    profile.wallet_balance += deposit.amount
                    profile.save()
                except AttributeError:
                    try:
                        # Second approach: UserBalance model
                        user_balance, created = CryptoWallet.objects.get_or_create(
                            user=deposit.user,
                            defaults={'balance': Decimal('0.00')}
                        )
                        user_balance.balance += deposit.amount
                        user_balance.save()
                    except NameError:
                        # If neither model exists, just update the deposit status
                        pass
                
                confirmed_count += 1
        
        if confirmed_count > 0:
            self.message_user(
                request, 
                f"{confirmed_count} deposit(s) confirmed and user balances updated."
            )
        else:
            self.message_user(
                request,
                "No deposits were confirmed (they may already be confirmed)."
            )
    
    def reject_deposits(self, request, queryset):
        rejected_count = queryset.update(status='rejected')
        self.message_user(
            request, 
            f"{rejected_count} deposit(s) have been rejected."
        )
    
    confirm_deposits.short_description = "✓ Confirm selected deposits"
    reject_deposits.short_description = "✗ Reject selected deposits"
    
    # Add fieldsets for better organization in detail view
    fieldsets = (
        (None, {
            'fields': ('user', 'crypto_wallet', 'amount', 'status')
        }),
        ('Transaction Details', {
            'fields': ('transaction_hash', 'screenshot', 'reference_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_by'),
            'classes': ('collapse',)
        }),
    )

@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'daily_return', 'min_deposit', 'duration_days', 'is_active']
    list_editable = ['daily_return', 'min_deposit', 'duration_days', 'is_active']
    list_filter = ['is_active', 'name']
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of plans that have active investments
        if obj and obj.investment_set.exists():
            return False
        return True
    

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'is_confirmed', 'amount', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'plan', 'start_date', 'is_confirmed']
    search_fields = ['user__username']
    actions = ['confirm_payments']

    def confirm_payment(self, obj):
        if obj.is_confirmed:
            return format_html(
                '<span style="color: green;">✓ Confirmed</span>'
            )
        else:
            return format_html(
                '<a class="button" href="{}">Confirm</a>',
                reverse('admin:confirm_investment', args=[obj.pk])
            )
    confirm_payment.short_description = 'Payment Confirmation'
    
    def confirm_payments(self, request, queryset):
        queryset.update(is_confirmed=True)
        self.message_user(request, "Selected investments have been confirmed.")
    confirm_payments.short_description = "Mark selected investments as confirmed"
    
    # Add this to your urls.py as well
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/confirm/',
                self.admin_site.admin_view(self.confirm_investment),
                name='confirm_investment',
            ),
        ]
        return custom_urls + urls
    
    def confirm_investment(self, request, object_id, *args, **kwargs):
        investment = Investment.objects.get(id=object_id)
        investment.is_confirmed = True
        investment.save()
        self.message_user(request, f"Investment #{object_id} has been confirmed.")
        return redirect(reverse('admin:investment_app_investment_changelist'))

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_type', 'amount', 'status', 'created_at', 'reference_id']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['user__username', 'reference_id']
    actions = ['approve_transactions', 'reject_transactions']
    
    def approve_transactions(self, request, queryset):
        for transaction in queryset:
            if transaction.status == 'pending':
                transaction.status = 'completed'
                transaction.save()
                
                # If it's a deposit, create investment
                if transaction.transaction_type == 'deposit':
                    # Find appropriate plan based on amount
                    plans = InvestmentPlan.objects.all().order_by('min_deposit')
                    selected_plan = None
                    for plan in plans:
                        if transaction.amount >= plan.min_deposit:
                            selected_plan = plan
                    
                    if selected_plan:
                        investment = Investment.objects.create(
                            user=transaction.user,
                            plan=selected_plan,
                            amount=transaction.amount,
                            status='active'
                        )
                        transaction.investment = investment
                        transaction.save()
                
                # If it's a withdrawal, deduct from wallet
                elif transaction.transaction_type == 'withdrawal':
                    profile = UserProfile.objects.get(user=transaction.user)
                    profile.wallet_balance -= transaction.amount
                    profile.save()
        
        self.message_user(request, "Selected transactions have been approved.")
    
    def reject_transactions(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, "Selected transactions have been rejected.")

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referrer', 'referred_user', 'created_at', 'bonus_paid']
    list_filter = ['bonus_paid', 'created_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'referral_code', 'wallet_balance', 'total_earnings', 'total_referral_bonus']
    search_fields = ['user__username']