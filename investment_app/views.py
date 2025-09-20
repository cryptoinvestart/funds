from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum, Count
from django.http import JsonResponse
from .models import InvestmentPlan, Investment, Transaction, Referral, UserProfile, Deposit, CryptoWallet, DailyEarning
from .forms import (InvestmentForm, WithdrawalForm, DepositForm, AdminDepositConfirmationForm, 
                    ProfileUpdateForm, UserUpdateForm)
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from decimal import Decimal
import uuid
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm



def index(request):
    plans = InvestmentPlan.objects.all()
    return render(request, 'investment_app/index.html', {'plans': plans})

def investment_plans(request):
    plans = InvestmentPlan.objects.filter(is_active=True)
    return render(request, 'investment_app/investment_plans.html', {'plans': plans})


@login_required
def dashboard(request):
    user = request.user
    
    # Get or create user profile
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    # Get investments with select_related to optimize database queries
    active_investments = Investment.objects.filter(user=user, status='active').select_related('plan')
    completed_investments = Investment.objects.filter(user=user, status='completed').select_related('plan')
    
    # Get transactions
    pending_transactions = Transaction.objects.filter(user=user, status='pending')
    
    # Calculate total stats
    total_invested = active_investments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Calculate total earnings from all completed transactions of type 'return' and 'referral'
    total_earnings = Transaction.objects.filter(
        user=user, 
        status='completed',
        transaction_type__in=['return', 'referral']
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Update profile total_earnings if different
    if profile.total_earnings != total_earnings:
        profile.total_earnings = total_earnings
        profile.save()
    
    total_referral_bonus = profile.total_referral_bonus
    
    # Get today's earnings from DailyEarning model
    today = timezone.now().date()
    try:
        today_earning = DailyEarning.objects.get(user=user, date=today)
        today_earnings = today_earning.amount
    except DailyEarning.DoesNotExist:
        today_earnings = Decimal('0.00')
    
    # Get weekly earnings (last 7 days) from DailyEarning model
    week_ago = today - timezone.timedelta(days=7)
    weekly_earnings = DailyEarning.objects.filter(
        user=user, 
        date__gte=week_ago
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Get referral stats
    referral_count = Referral.objects.filter(referrer=user).count()
    referral_link = request.build_absolute_uri(f'/register/?ref={profile.referral_code}')
    
    # Get recent activities (last 5 transactions)
    recent_transactions = Transaction.objects.filter(
        user=user
    ).order_by('-created_at')[:5]
    
    # Get upcoming investment maturities (next 7 days)
    upcoming_maturities = Investment.objects.filter(
        user=user,
        status='active',
        end_date__lte=today + timezone.timedelta(days=7),
        end_date__gte=today
    ).order_by('end_date').select_related('plan')
    
    # Calculate portfolio growth percentage
    if total_invested > 0:
        growth_percentage = ((total_earnings / total_invested) * 100) if total_invested > 0 else 0
    else:
        growth_percentage = 0
    
    context = {
        'profile': profile,
        'active_investments': active_investments,
        'completed_investments': completed_investments,
        'pending_transactions': pending_transactions,
        'recent_transactions': recent_transactions,
        'upcoming_maturities': upcoming_maturities,
        'total_invested': total_invested,
        'total_earnings': total_earnings,
        'today_earnings': today_earnings,
        'weekly_earnings': weekly_earnings,
        'total_referral_bonus': total_referral_bonus,
        'referral_count': referral_count,
        'referral_link': referral_link,
        'growth_percentage': round(growth_percentage, 2),
    }
    
    return render(request, 'investment_app/dashboard.html', context)

@login_required
def profile(request):
    try:
        user_profile = request.user.userprofile
    except:
        # Create profile if it doesn't exist
        from .models import UserProfile
        user_profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Check which form was submitted
        if 'update_profile' in request.POST:
            profile_form = ProfileUpdateForm(request.POST, instance=user_profile)
            user_form = UserUpdateForm(request.POST, instance=request.user)
            
            if profile_form.is_valid() and user_form.is_valid():
                profile_form.save()
                user_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('profile')
        
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Important to keep the user logged in
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the error below.')
        else:
            profile_form = ProfileUpdateForm(instance=user_profile)
            user_form = UserUpdateForm(instance=request.user)
            password_form = PasswordChangeForm(request.user)
    else:
        profile_form = ProfileUpdateForm(instance=user_profile)
        user_form = UserUpdateForm(instance=request.user)
        password_form = PasswordChangeForm(request.user)
    
    context = {
        'profile_form': profile_form,
        'user_form': user_form,
        'password_form': password_form,
        'user_profile': user_profile
    }
    
    return render(request, 'investment_app/profile.html', context)


@login_required
def invest(request):
    plans = InvestmentPlan.objects.filter(is_active=True)
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        amount = request.POST.get('amount')
        
        try:
            plan = InvestmentPlan.objects.get(id=plan_id, is_active=True)
            amount_decimal = Decimal(amount)
            
            # Validate amount
            if amount_decimal < plan.min_deposit:
                messages.error(request, f'Minimum deposit for {plan.get_name_display()} is ${plan.min_deposit}')
                return redirect('invest')
            
            # Check if user has sufficient balance
            profile = request.user.userprofile
            if profile.wallet_balance < amount_decimal:
                messages.error(request, 'Insufficient balance in your wallet')
                return redirect('invest')
            
            # Create investment
            investment = Investment.objects.create(
                user=request.user,
                plan=plan,
                amount=amount_decimal,
                status='active'  # Change to active immediately
            )
            
            # Create transaction
            Transaction.objects.create(
                user=request.user,
                transaction_type='deposit',
                amount=amount_decimal,
                status='completed',
                investment=investment
            )
            
            # Deduct from wallet balance
            profile.wallet_balance -= amount_decimal
            profile.save()
            
            messages.success(request, f'Investment in {plan.get_name_display()} created successfully.')
            return redirect('dashboard')
            
        except InvestmentPlan.DoesNotExist:
            messages.error(request, 'Invalid investment plan selected')
            return redirect('invest')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return redirect('invest')
    
    return render(request, 'investment_app/invest.html', {'plans': plans})

@login_required
def withdraw(request):
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            # Check if user has sufficient balance
            profile = UserProfile.objects.get(user=request.user)
            if profile.wallet_balance < amount:
                form.add_error('amount', 'Insufficient balance in your wallet.')
                return render(request, 'investment_app/withdraw.html', {'form': form})
            
            # Create withdrawal transaction (admin needs to confirm)
            Transaction.objects.create(
                user=request.user,
                transaction_type='withdrawal',
                amount=amount,
                status='pending'
            )
            
            return redirect('dashboard')
    else:
        form = WithdrawalForm()
    
    return render(request, 'investment_app/withdraw.html', {'form': form})


@login_required
def transactions(request):
    transactions_list = Transaction.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(transactions_list, 10)  #Show 10 transactions per page
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'investment_app/transactions.html', {'transactions': page_obj})

@login_required
def referrals(request):
    profile = UserProfile.objects.get(user=request.user)
    user_referrals = Referral.objects.filter(referrer=request.user)
    referral_link = request.build_absolute_uri(f'/register/?ref={profile.referral_code}')
    
    context = {
        'referrals': user_referrals,
        'referral_link': referral_link,
    }
    
    return render(request, 'investment_app/referrals.html', context)

def register(request):
    referral_code = request.GET.get('ref', None)
    
    if request.method == 'POST':
        # Registration logic here
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Validate that all required fields are present
        if not all([username, email, password1, password2]):
            return render(request, 'registration/register.html', {
                'referral_code': referral_code,
                'error': 'All fields are required'
            })
        
        # Check if passwords match
        if password1 != password2:
            return render(request, 'registration/register.html', {
                'referral_code': referral_code,
                'error': 'Passwords do not match'
            })
        
        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            return render(request, 'registration/register.html', {
                'referral_code': referral_code,
                'error': 'Username already exists'
            })
        
        if User.objects.filter(email=email).exists():
            return render(request, 'registration/register.html', {
                'referral_code': referral_code,
                'error': 'Email already exists'
            })
        
        try:
            # Create user - this should hash the password automatically
            user = User.objects.create_user(username, email, password1)
            
            # Create user profile
            profile = UserProfile.objects.create(user=user)
            
            # Process referral if exists
            if referral_code:
                try:
                    referrer_profile = UserProfile.objects.get(referral_code=referral_code)
                    Referral.objects.create(
                        referrer=referrer_profile.user,
                        referred_user=user
                    )
                except UserProfile.DoesNotExist:
                    pass
            
            # AUTOMATICALLY LOGIN THE USER AFTER REGISTRATION
            user = authenticate(username=username, password=password1)
            if user is not None:
                login(request, user)
                return redirect('dashboard')  # Redirect to home page or dashboard
            
        except Exception as e:
            # Handle any other errors
            return render(request, 'registration/register.html', {
                'referral_code': referral_code,
                'error': f'Registration failed: {str(e)}'
            })
    
    return render(request, 'registration/register.html', {'referral_code': referral_code})


def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')  # Redirect to your home page
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect to a success page or next parameter
                next_url = request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard')  # Change 'home' to your desired redirect
        else:
            # Form is not valid - show error message
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    # Pass the next parameter to the template context
    next_param = request.GET.get('next', '')
    return render(request, 'investment_app/login.html', {
        'form': form,
        'next': next_param
    })

@login_required
def deposit_funds(request):
    if request.method == 'POST':
        form = DepositForm(request.POST, request.FILES)
        if form.is_valid():
            deposit = form.save(commit=False)
            deposit.user = request.user
            deposit.save()
            messages.success(request, 'Deposit request submitted successfully. Please wait for admin confirmation.')
            return redirect('deposit_history')
    else:
        form = DepositForm()
    
    # Get active crypto wallets
    crypto_wallets = CryptoWallet.objects.filter(is_active=True)
    
    context = {
        'form': form,
        'crypto_wallets': crypto_wallets,
        'min_deposit': 50
    }
    return render(request, 'investment_app/deposit.html', context)

@login_required
def deposit_history(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(deposits, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'deposits': page_obj,
    }
    return render(request, 'investment_app/deposit_history.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_deposit_list(request):
    status_filter = request.GET.get('status', 'pending')
    
    deposits = Deposit.objects.all().order_by('-created_at')
    
    if status_filter != 'all':
        deposits = deposits.filter(status=status_filter)
    
    # Search functionality
    search_query = request.GET.get('q')
    if search_query:
        deposits = deposits.filter(
            Q(user__username__icontains=search_query) |
            Q(transaction_hash__icontains=search_query) |
            Q(reference_id__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(deposits, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'deposits': page_obj,
        'status_filter': status_filter,
        'search_query': search_query or '',
    }
    return render(request, 'investment_app/admin_deposit_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_deposit_detail(request, deposit_id):
    deposit = get_object_or_404(Deposit, id=deposit_id)
    
    if request.method == 'POST':
        form = AdminDepositConfirmationForm(request.POST, instance=deposit)
        if form.is_valid():
            updated_deposit = form.save(commit=False)
            if 'status' in form.changed_data:
                if form.cleaned_data['status'] == 'confirmed':
                    updated_deposit.confirmed_by = request.user
                    # Add deposit amount to user's wallet balance
                    profile = updated_deposit.user.userprofile
                    profile.wallet_balance += updated_deposit.amount
                    profile.save()
                    
                    # Create transaction record
                    from .models import Transaction
                    Transaction.objects.create(
                        user=updated_deposit.user,
                        transaction_type='deposit',
                        amount=updated_deposit.amount,
                        status='completed',
                        investment=None
                    )
            updated_deposit.save()
            messages.success(request, 'Deposit status updated successfully.')
            return redirect('admin_deposit_list')
    else:
        form = AdminDepositConfirmationForm(instance=deposit)
    
    context = {
        'deposit': deposit,
        'form': form,
    }
    return render(request, 'investment_app/admin_deposit_detail.html', context)


def confirm_deposit(request, deposit_id):
    deposit = get_object_or_404(Deposit, id=deposit_id)
    
    # Update the deposit status
    deposit.status = 'confirmed'
    deposit.save()
    
    # Credit the user's balance
    user_balance, created = CryptoWallet.objects.get_or_create(
        user=deposit.user,
        defaults={'balance': Decimal('0.00')}
    )
    user_balance.balance += deposit.amount
    user_balance.save()
    
    messages.success(request, f"Deposit #{deposit.reference_id} confirmed and user balance updated.")
    return redirect('admin:investment_app_deposit_changelist')

def home(request):
    plans = InvestmentPlan.objects.filter(is_active=True)
    return render(request, 'investment_app/home.html', {'plans': plans})

def about(request):
    return render(request, 'investment_app/about.html')

def terms(request):
    return render(request, 'investment_app/terms.html')

def privacy(request):
    return render(request, 'investment_app/privacy.html')