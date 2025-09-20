from django import forms
from .models import Deposit, CryptoWallet, UserProfile
from django.contrib.auth.models import User


class DepositForm(forms.ModelForm):
    crypto_wallet = forms.ModelChoiceField(
        queryset=CryptoWallet.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        empty_label=None
    )
    
    class Meta:
        model = Deposit
        fields = ['crypto_wallet', 'amount', 'transaction_hash', 'screenshot']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minimum $50',
                'min': '50',
                'step': '0.01'
            }),
            'transaction_hash': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your transaction hash'
            }),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount < 50:
            raise forms.ValidationError("Minimum deposit amount is $50")
        return amount

class AdminDepositConfirmationForm(forms.ModelForm):
    class Meta:
        model = Deposit
        fields = ['status', 'amount_in_crypto']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'amount_in_crypto': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001'
            }),
        }

class InvestmentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=50,
        label="Investment Amount ($)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=10,
        label="Withdrawal Amount ($)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    wallet_address = forms.CharField(
        max_length=100,
        label="Your Crypto Wallet Address",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'country', 'profile_picture']
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }