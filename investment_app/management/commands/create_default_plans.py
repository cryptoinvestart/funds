from django.core.management.base import BaseCommand
from investment_app.models import InvestmentPlan

class Command(BaseCommand):
    help = 'Create default investment plans'
    
    def handle(self, *args, **options):
        plans = [
            {
                'name': 'basic',
                'daily_return': 3.0,
                'min_deposit': 50.00,
                'duration_days': 30,
                'description': 'Basic investment plan with 3% daily returns'
            },
            {
                'name': 'standard',
                'daily_return': 5.0,
                'min_deposit': 100.00,
                'duration_days': 30,
                'description': 'Standard investment plan with 5% daily returns'
            },
            {
                'name': 'premium',
                'daily_return': 8.0,
                'min_deposit': 250.00,
                'duration_days': 30,
                'description': 'Premium investment plan with 8% daily returns'
            }
        ]
        
        for plan_data in plans:
            plan, created = InvestmentPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created {plan.get_name_display()}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'{plan.get_name_display()} already exists')
                )