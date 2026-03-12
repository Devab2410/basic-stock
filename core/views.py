from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import (
    BusinessType, SubscriptionPlan, Company, Store, StaffProfile
)

User = get_user_model()

def _enforce_superadmin(request):
    if not request.user.is_superuser:
        messages.error(request, 'Super Admin access required.')
        return redirect('accounts:login')
    return None


def _default_store_code(company):
    base = ''.join(ch for ch in company.name.upper() if ch.isalnum())[:4] or 'MAIN'
    code = f'{base}-001'
    n = 2
    while Store.objects.filter(company=company, store_code=code).exists():
        code = f'{base}-{n:03d}'
        n += 1
    return code


def _first_business_type(company):
    bt = company.business_types.filter(is_active=True).order_by('name').first()
    if bt:
        return bt
    return BusinessType.objects.filter(is_active=True).order_by('name').first()


def _ensure_owner_staff_profile(company):
    owner = company.owner
    if not owner:
        return

    main_store = company.stores.filter(is_main_branch=True).first() or company.stores.first()
    if not main_store:
        return

    profile, created = StaffProfile.objects.get_or_create(
        user=owner,
        defaults={
            'company': company,
            'store': main_store,
            'role': 'owner',
            'joined_date': timezone.now().date(),
            'is_active': True,
        }
    )
    if not created:
        changed = False
        if profile.company_id != company.id:
            profile.company = company
            changed = True
        if profile.store_id != main_store.id:
            profile.store = main_store
            changed = True
        if profile.role != 'owner':
            profile.role = 'owner'
            changed = True
        if not profile.is_active:
            profile.is_active = True
            changed = True
        if changed:
            profile.save()


@login_required
def superadmin_dashboard(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied
    return render(request, 'core/superadmin_dashboard.html')

@login_required
def business_types(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied

    business_types = BusinessType.objects.all()

    if request.method == "POST":

        action = request.POST.get("action")

        # CREATE
        if action == "create":
            name = request.POST.get('name')
            code = request.POST.get('code')
            description = request.POST.get('description')
            icon = request.POST.get('icon')
            color = request.POST.get('color')
            is_active = request.POST.get('is_active')
            if is_active == 'on':
                is_active = True
            else:
                is_active = False
            business_type = BusinessType.objects.create(name=name, code=code, description=description, icon=icon, color=color, is_active=is_active)
            messages.success(request, 'Business type created successfully.')

        # UPDATE
        elif action == "update":

            bt = BusinessType.objects.get(id=request.POST.get("id"))

            bt.name = request.POST.get("name")
            bt.code = request.POST.get("code")
            bt.description = request.POST.get("description")
            bt.icon = request.POST.get("icon")
            bt.color = request.POST.get("color")
            bt.is_active = request.POST.get("is_active") == "on"

            bt.save()
            messages.success(request, "Updated successfully")

        # DELETE
        elif action == "delete":

            BusinessType.objects.filter(id=request.POST.get("id")).delete()

            messages.success(request, "Deleted successfully")

        return redirect("core:business_types")

    return render(request, "core/business_types.html", { "business_types": business_types })

@login_required
def plans(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied

    plans = SubscriptionPlan.objects.all()
    return render(request, 'core/plans.html', {'plans': plans})

@login_required
def companies(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied

    business_types = BusinessType.objects.all()
    users = User.objects.filter(is_active=True).order_by('username')
    companies = Company.objects.all()
    if request.method == "POST":

        action = request.POST.get("action")

        # CREATE
        if action == "create":
            try:
                with transaction.atomic():
                    name = request.POST.get("name")
                    slug = request.POST.get("slug")
                    registration_no = request.POST.get("registration_no")
                    gstin = request.POST.get("gstin")
                    selected_business_types = request.POST.getlist("business_type")
                    owner = User.objects.get(id=request.POST.get("owner"))
                    email = request.POST.get("email")
                    phone = request.POST.get("phone")
                    address = request.POST.get("address")
                    city = request.POST.get("city")
                    state = request.POST.get("state")
                    country = request.POST.get("country")
                    logo = request.FILES.get("logo")
                    is_active = request.POST.get("is_active") == "True"

                    company = Company.objects.create(
                        name=name,
                        slug=slug,
                        registration_no=registration_no,
                        gstin=gstin,
                        owner=owner,
                        email=email,
                        phone=phone,
                        address=address,
                        city=city,
                        state=state,
                        country=country,
                        logo=logo,
                        is_active=is_active
                    )
                    if selected_business_types:
                        company.business_types.set(selected_business_types)

                    # Company creation should not auto-create a store.
                    # Owner staff profile can be created later when a store is assigned.
                    _ensure_owner_staff_profile(company)

                    messages.success(
                        request,
                        'Company created successfully. Add stores and staff profile separately.'
                    )
            except Exception as exc:
                messages.error(request, f'Unable to create company: {exc}')

        # UPDATE
        elif action == "update":
            cp = Company.objects.get(id=request.POST.get("id"))
            cp.name = request.POST.get("name")
            cp.slug = request.POST.get("slug")
            cp.registration_no = request.POST.get("registration_no")
            cp.gstin = request.POST.get("gstin")
            business_types = request.POST.getlist("business_type")
            cp.owner = User.objects.get(id=request.POST.get("owner"))
            cp.email = request.POST.get("email")
            cp.phone = request.POST.get("phone")
            cp.address = request.POST.get("address")
            cp.city = request.POST.get("city")
            cp.state = request.POST.get("state")
            # cp.zip_code = request.POST.get("zip_code")
            cp.country = request.POST.get("country")
            new_logo = request.FILES.get("logo")
            if new_logo:
                cp.logo = new_logo
            cp.is_active = request.POST.get("is_active") == "True"
            cp.business_types.set(business_types)
            cp.save()
            if cp.stores.filter(is_main_branch=True).count() == 0:
                fallback_store = cp.stores.first()
                if fallback_store:
                    fallback_store.is_main_branch = True
                    fallback_store.save(update_fields=['is_main_branch'])
            _ensure_owner_staff_profile(cp)
            messages.success(request, "Updated successfully")

        # DELETE
        elif action == "delete":

            Company.objects.filter(id=request.POST.get("id")).delete()

            messages.success(request, "Deleted successfully")

        return redirect("core:companies")

    return render(request, 'core/companies.html', {'companies': companies, 'users': users, 'business_types': business_types})


@login_required
def stores(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied

    stores = Store.objects.all()
    companies = Company.objects.all()
    users = User.objects.filter(is_active=True).order_by('username')
    business_types = BusinessType.objects.all()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            company = Company.objects.get(id=request.POST.get("company"))
            business_type = BusinessType.objects.get(id=request.POST.get("business_type"))
            name = request.POST.get("name")
            store_code = request.POST.get("store_code")
            manager_id = request.POST.get("manager")
            manager = User.objects.filter(id=manager_id).first() if manager_id else None
            email = request.POST.get("email")
            phone = request.POST.get("phone")
            address = request.POST.get("address")
            city = request.POST.get("city")
            state = request.POST.get("state")
            country = request.POST.get("country")
            is_main_store = request.POST.get("is_main_store") == "True"
            is_active = request.POST.get("is_active") == "True"
            if not company.stores.exists():
                is_main_store = True
            if is_main_store:
                company.stores.update(is_main_branch=False)
            store = Store.objects.create(name=name, store_code=store_code, company=company, business_type=business_type, manager=manager, email=email, phone=phone, address=address, city=city, state=state, country=country, is_main_branch=is_main_store, is_active=is_active)
            messages.success(request, 'Store created successfully.')

        # UPDATE
        elif action == "update":
            st = Store.objects.get(id=request.POST.get("id"))
            st.name = request.POST.get("name")
            st.store_code = request.POST.get("store_code")
            st.company = Company.objects.get(id=request.POST.get("company"))
            st.business_type = BusinessType.objects.get(id=request.POST.get("business_type"))
            manager_id = request.POST.get("manager")
            st.manager = User.objects.filter(id=manager_id).first() if manager_id else None
            st.email = request.POST.get("email")
            st.phone = request.POST.get("phone")
            st.address = request.POST.get("address")
            st.city = request.POST.get("city")
            st.state = request.POST.get("state")
            st.country = request.POST.get("country")
            requested_main = request.POST.get("is_main_store") == "True"
            if st.is_main_branch and not requested_main:
                other_main_exists = Store.objects.filter(
                    company=st.company,
                    is_main_branch=True
                ).exclude(pk=st.pk).exists()
                if not other_main_exists:
                    requested_main = True
                    messages.warning(request, 'At least one main branch is required per company.')
            st.is_main_branch = requested_main
            st.is_active = request.POST.get("is_active") == "True"
            st.save()
            if st.is_main_branch:
                Store.objects.filter(company=st.company).exclude(pk=st.pk).update(is_main_branch=False)
            messages.success(request, "Updated successfully")

        # DELETE
        elif action == "delete":
            store = Store.objects.filter(id=request.POST.get("id")).first()
            if store:
                company_id = store.company_id
                was_main = store.is_main_branch
                store.delete()
                if was_main:
                    fallback = Store.objects.filter(company_id=company_id).order_by('created_at').first()
                    if fallback:
                        fallback.is_main_branch = True
                        fallback.save(update_fields=['is_main_branch'])
            messages.success(request, "Deleted successfully")

        return redirect("core:stores")
    return render(request, 'core/store_list.html', {'stores': stores, 'companies': companies, 'users': users, 'business_types': business_types})


@login_required
def company_detail(request, pk):
    denied = _enforce_superadmin(request)
    if denied:
        return denied
    company = get_object_or_404(
        Company.objects.select_related('owner').prefetch_related('business_types', 'stores', 'staff__user'),
        pk=pk
    )
    return render(request, 'core/company_detail.html', {
        'company': company,
        'stores': company.stores.filter(is_active=True).select_related('business_type'),
        'staff': company.staff.filter(is_active=True).select_related('user', 'store'),
    })


@login_required
def company_toggle(request, pk):
    denied = _enforce_superadmin(request)
    if denied:
        return denied
    company = get_object_or_404(Company, pk=pk)
    company.is_active = not company.is_active
    company.save(update_fields=['is_active'])
    status = 'activated' if company.is_active else 'deactivated'
    messages.success(request, f'Company {company.name} has been {status}.')
    return redirect('core:companies')


@login_required
def staff(request):
    denied = _enforce_superadmin(request)
    if denied:
        return denied

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            try:
                user_id = request.POST.get("user")
                new_username = request.POST.get("new_username", "").strip()
                new_email = request.POST.get("new_email", "").strip().lower()
                new_phone = request.POST.get("new_phone", "").strip()
                new_password = request.POST.get("new_password", "")
                company_id = request.POST.get("company")
                store_id = request.POST.get("store")
                role = request.POST.get("role", "staff")
                designation = request.POST.get("designation", "").strip()
                joined_date = request.POST.get("joined_date")
                is_active = request.POST.get("is_active") == "on"

                if not company_id or not store_id:
                    messages.error(request, "Company and store are required.")
                    return redirect("core:staff_list")

                user = None
                # Option 1: existing user selected
                if user_id:
                    user = User.objects.get(pk=user_id)
                # Option 2: create new user in staff page
                else:
                    if not new_username or not new_password:
                        messages.error(request, "Select a user or enter new username + password.")
                        return redirect("core:staff_list")
                    if User.objects.filter(username__iexact=new_username).exists():
                        messages.error(request, "Username already exists.")
                        return redirect("core:staff_list")
                    if new_email and User.objects.filter(email__iexact=new_email).exists():
                        messages.error(request, "Email already exists.")
                        return redirect("core:staff_list")
                    user = User.objects.create_user(
                        username=new_username,
                        email=new_email,
                        password=new_password,
                        phone=new_phone,
                        is_active=is_active,
                    )

                company = Company.objects.get(pk=company_id)
                store = Store.objects.get(pk=store_id)

                if store.company_id != company.id:
                    messages.error(request, "Selected store does not belong to selected company.")
                    return redirect("core:staff_list")

                if StaffProfile.objects.filter(user=user).exists():
                    messages.error(request, f"{user.username} already has a staff profile.")
                    return redirect("core:staff_list")

                StaffProfile.objects.create(
                    user=user,
                    company=company,
                    store=store,
                    role=role,
                    designation=designation,
                    joined_date=joined_date or timezone.now().date(),
                    is_active=is_active,
                )
                messages.success(request, "Staff profile created successfully.")
            except (User.DoesNotExist, Company.DoesNotExist, Store.DoesNotExist):
                messages.error(request, "Invalid user/company/store selected.")
            except IntegrityError:
                messages.error(request, "Unable to create staff profile due to duplicate data.")
            except Exception as exc:
                messages.error(request, f"Unable to create staff profile: {exc}")
        return redirect("core:staff_list")

    staff_list = StaffProfile.objects.select_related('user', 'company', 'store').all()
    users_for_staff = User.objects.filter(is_active=True).exclude(staffprofile__isnull=False).order_by('username')
    companies = Company.objects.filter(is_active=True).order_by('name')
    stores = Store.objects.filter(is_active=True).select_related('company').order_by('company__name', 'name')
    return render(request, 'core/staff_list.html', {
        'staff_list': staff_list,
        'users_for_staff': users_for_staff,
        'companies': companies,
        'stores': stores,
        'role_choices': StaffProfile.ROLE_CHOICES,
    })


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.user.is_superuser:
        return redirect('core:superadmin_dashboard')
    if request.user.has_staff_profile and request.user.active_store and request.user.active_store.business_type:
        bt_code = request.user.active_store.business_type.code.lower()
        url_map = {
            'pharmacy': '/pharmacy/',
            'grocery': '/grocery/',
            'ecommerce': '/ecommerce/',
        }
        return redirect(url_map.get(bt_code, '/accounts/profile/'))
    return redirect('accounts:profile')
