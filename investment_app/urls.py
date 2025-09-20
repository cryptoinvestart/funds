from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('invest/', views.invest, name='invest'),
    path('plans/', views.investment_plans, name='investment_plans'),
    path('withdraw/', views.withdraw, name='withdraw'),
    path('transactions/', views.transactions, name='transactions'),
    path('referrals/', views.referrals, name='referrals'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),

    path('deposit/', views.deposit_funds, name='deposit'),
    path('deposit/history/', views.deposit_history, name='deposit_history'),
    path('admin/deposits/', views.admin_deposit_list, name='admin_deposit_list'),
    path('admin/deposits/<int:deposit_id>/', views.admin_deposit_detail, name='admin_deposit_detail'),
]