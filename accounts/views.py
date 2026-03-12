from django.contrib.auth import login, logout, authenticate, update_session_auth_hash, get_user_model
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    errors = []
    form_data = {}

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        form_data = {'username': username}

        if not username or not password:
            errors.append('Username/email and password are required.')
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                next_url = request.GET.get('next', '')
                if next_url:
                    return redirect(next_url)
                return redirect(_get_post_login_url(user))
            else:
                errors.append('Invalid username/email or password.')

    return render(request, 'accounts/signin.html', {'errors': errors, 'form_data': form_data})


# ─────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    errors = []
    form_data = {}

    if request.method == 'POST':
        form_data = {
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name': request.POST.get('last_name', '').strip(),
            'username': request.POST.get('username', '').strip(),
            'email': request.POST.get('email', '').strip().lower(),
            'phone': request.POST.get('phone', '').strip(),
        }
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not form_data['username']:
            errors.append('Username is required.')
        if not form_data['email']:
            errors.append('Email is required.')
        if not password:
            errors.append('Password is required.')
        if password != password_confirm:
            errors.append('Passwords do not match.')
        if form_data['username'] and User.objects.filter(username__iexact=form_data['username']).exists():
            errors.append('This username is already taken.')
        if form_data['email'] and User.objects.filter(email__iexact=form_data['email']).exists():
            errors.append('A user with this email already exists.')

        if not errors:
            user = User(
                first_name=form_data['first_name'],
                last_name=form_data['last_name'],
                username=form_data['username'],
                email=form_data['email'],
                phone=form_data['phone'],
            )
            user.set_password(password)
            user.save()
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('accounts:login')

    return render(request, 'accounts/register.html', {'errors': errors, 'form_data': form_data})


# ─────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────
@login_required
def profile_view(request):
    errors = []
    form_data = {
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'email': request.user.email,
        'phone': request.user.phone,
    }

    if request.method == 'POST':
        form_data = {
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name': request.POST.get('last_name', '').strip(),
            'email': request.POST.get('email', '').strip().lower(),
            'phone': request.POST.get('phone', '').strip(),
        }
        if not form_data['email']:
            errors.append('Email is required.')
        elif User.objects.filter(email__iexact=form_data['email']).exclude(pk=request.user.pk).exists():
            errors.append('This email is already in use.')

        if not errors:
            request.user.first_name = form_data['first_name']
            request.user.last_name = form_data['last_name']
            request.user.email = form_data['email']
            request.user.phone = form_data['phone']
            if request.FILES.get('avatar'):
                request.user.avatar = request.FILES['avatar']
            request.user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {'errors': errors, 'form_data': form_data})


# ─────────────────────────────────────────────────────────────
# CHANGE PASSWORD
# ─────────────────────────────────────────────────────────────
@login_required
def change_password_view(request):
    errors = []

    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not current_password or not new_password or not confirm_password:
            errors.append('All password fields are required.')
        if current_password and not request.user.check_password(current_password):
            errors.append('Current password is incorrect.')
        if new_password and confirm_password and new_password != confirm_password:
            errors.append('New passwords do not match.')

        if not errors:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:profile')

    return render(request, 'accounts/change_password.html', {'errors': errors})


# ─────────────────────────────────────────────────────────────
# MANAGE USERS  (superadmin)
# ─────────────────────────────────────────────────────────────
@login_required
def manage_users(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            username = request.POST.get('username')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            is_active = request.POST.get('is_active') == 'on'
            avatar = request.FILES.get('avatar')

            if password and password == confirm_password:
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        phone=phone,
                        is_active=is_active,
                    )
                    if avatar:
                        user.avatar = avatar
                        user.save()
                    messages.success(request, 'User added successfully.')
                else:
                    messages.error(request, 'Username already exists.')
            else:
                messages.error(request, 'Passwords do not match or are required.')

        elif action == 'update':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, id=user_id)
            user.username = request.POST.get('username', user.username)
            user.email = request.POST.get('email', user.email)
            user.phone = request.POST.get('phone', user.phone)
            user.is_active = request.POST.get('is_active') == 'on'
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            if password:
                if password == confirm_password:
                    user.set_password(password)
                else:
                    messages.error(request, 'Passwords do not match.')
            if request.POST.get('verified') == 'on':
                user.is_verified = True
            if request.FILES.get('avatar'):
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, 'User updated successfully.')

        elif action == 'delete':
            user_id = request.POST.get('user_id')
            user = get_object_or_404(User, id=user_id)
            user.delete()
            messages.success(request, 'User deleted successfully.')

        return redirect('accounts:manage_users')

    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/users.html', {'users': users})


# ─────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────
def _get_post_login_url(user):
    if user.is_superuser:
        return '/core/superadmin-dashboard/'
    if not user.has_staff_profile:
        return '/core/dashboard/'
    store = user.active_store
    if not store:
        return '/core/dashboard/'
    bt_code = store.business_type.code.lower() if store.business_type else ''
    url_map = {
        'pharmacy': '/pharmacy/',
        'grocery': '/grocery/',
        'ecommerce': '/ecommerce/',
    }
    return url_map.get(bt_code, '/core/dashboard/')
