"""
Seed management command to create initial core models data.
Usage: python manage.py seed_data

NOTE: CompanySubscription, SubscriptionPlan, and CompanySetting are deferred
and NOT created by this command intentionally.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import BusinessType, Company, Store, StaffProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial core models data'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding data...")
        self._seed_business_types()
        self._seed_users_and_companies()
        self.stdout.write(self.style.SUCCESS('\nSeed data loaded successfully.'))

    def _seed_business_types(self):
        business_types = [
            {
                'name': 'Pharmacy',
                'code': 'pharmacy',
                'description': 'Medical store, drug store, chemist shop management.',
                'icon': 'ti ti-pill',
                'color': '#0d9488',
            },
            {
                'name': 'Grocery',
                'code': 'grocery',
                'description': 'Supermarket, grocery store, fresh produce management.',
                'icon': 'ti ti-shopping-cart',
                'color': '#f97316',
            },
            {
                'name': 'eCommerce',
                'code': 'ecommerce',
                'description': 'Online store, marketplace, digital retail.',
                'icon': 'ti ti-world',
                'color': '#7638ff',
            },
            {
                'name': 'Restaurant',
                'code': 'restaurant',
                'description': 'Food & beverage, restaurant, café management.',
                'icon': 'ti ti-salad',
                'color': '#e11d48',
            },
            {
                'name': 'Hardware',
                'code': 'hardware',
                'description': 'Hardware shop, tools, building materials management.',
                'icon': 'ti ti-tool',
                'color': '#ca8a04',
            },
        ]
        for bt in business_types:
            obj, created = BusinessType.objects.update_or_create(
                code=bt['code'],
                defaults=bt
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  {status} BusinessType: {obj.name}')

    def _seed_users_and_companies(self):
        self.stdout.write("\nSeeding Users, Companies, Stores, and Staff Profiles...")

        # 1. Create superuser (platform admin)
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write("  Created Superuser: admin / admin123")
        else:
            self.stdout.write("  Superuser 'admin' already exists.")

        # 2. Create an Owner user for pharmacy
        owner1, created = User.objects.get_or_create(username='owner1', defaults={
            'email': 'owner1@example.com',
            'first_name': 'Demo',
            'last_name': 'Owner',
        })
        if created:
            owner1.set_password('pass123')
            owner1.save()
            self.stdout.write("  Created User: owner1 / pass123")

        # 3. Create an Owner user for grocery
        owner2, created = User.objects.get_or_create(username='owner2', defaults={
            'email': 'owner2@example.com',
            'first_name': 'Fresh',
            'last_name': 'Mart',
        })
        if created:
            owner2.set_password('pass123')
            owner2.save()
            self.stdout.write("  Created User: owner2 / pass123")

        pharmacy_type = BusinessType.objects.filter(code='pharmacy').first()
        grocery_type = BusinessType.objects.filter(code='grocery').first()

        # ── Pharmacy Company ──────────────────────────────────────
        if pharmacy_type:
            company1, created = Company.objects.get_or_create(
                name='HealthPlus Pharmacy',
                defaults={
                    'owner': owner1,
                    'email': 'contact@healthplus.com',
                    'phone': '+91-9876543210',
                    'address': '123 Main St',
                    'city': 'Mumbai',
                    'state': 'Maharashtra',
                    'is_active': True,
                    'is_verified': True,
                }
            )
            if created:
                company1.business_types.add(pharmacy_type)
                self.stdout.write(f"  Created Company: {company1.name}")

            store1, created = Store.objects.get_or_create(
                company=company1,
                store_code='HP001',
                defaults={
                    'business_type': pharmacy_type,
                    'name': 'HealthPlus Main Branch',
                    'is_main_branch': True,
                    'address': '123 Main St, Mumbai',
                }
            )
            if created:
                self.stdout.write(f"  Created Store: {store1.name}")

            profile1, created = StaffProfile.objects.get_or_create(
                user=owner1,
                defaults={
                    'company': company1,
                    'store': store1,
                    'role': 'owner',
                    'designation': 'Proprietor',
                    'joined_date': timezone.now().date(),
                }
            )
            if created:
                self.stdout.write("  Created StaffProfile for owner1")

        # ── Grocery Company ───────────────────────────────────────
        if grocery_type:
            company2, created = Company.objects.get_or_create(
                name='FreshMart Grocery',
                defaults={
                    'owner': owner2,
                    'email': 'contact@freshmart.com',
                    'phone': '+91-9123456789',
                    'address': '45 Market Road',
                    'city': 'Bangalore',
                    'state': 'Karnataka',
                    'is_active': True,
                    'is_verified': True,
                }
            )
            if created:
                company2.business_types.add(grocery_type)
                self.stdout.write(f"  Created Company: {company2.name}")

            store2, created = Store.objects.get_or_create(
                company=company2,
                store_code='FM001',
                defaults={
                    'business_type': grocery_type,
                    'name': 'FreshMart Main Store',
                    'is_main_branch': True,
                    'address': '45 Market Road, Bangalore',
                }
            )
            if created:
                self.stdout.write(f"  Created Store: {store2.name}")

            profile2, created = StaffProfile.objects.get_or_create(
                user=owner2,
                defaults={
                    'company': company2,
                    'store': store2,
                    'role': 'owner',
                    'designation': 'Proprietor',
                    'joined_date': timezone.now().date(),
                }
            )
            if created:
                self.stdout.write("  Created StaffProfile for owner2")
