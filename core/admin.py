from django.contrib import admin
from .models import (
    BusinessType, SubscriptionPlan, Company, CompanySubscription,
    Store, StaffProfile, CompanySetting
)


@admin.register(BusinessType)
class BusinessTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'icon', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'max_stores', 'max_users', 'max_products', 'duration_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


class StoreInline(admin.TabularInline):
    model = Store
    extra = 0
    fields = ('name', 'store_code', 'business_type', 'city', 'is_active', 'is_main_branch')
    show_change_link = True


class StaffProfileInline(admin.TabularInline):
    model = StaffProfile
    extra = 0
    fields = ('user', 'store', 'role', 'designation', 'joined_date', 'is_active')
    show_change_link = True


class CompanySubscriptionInline(admin.StackedInline):
    model = CompanySubscription
    can_delete = False
    verbose_name_plural = 'Subscription'


class CompanySettingInline(admin.StackedInline):
    model = CompanySetting
    can_delete = False
    verbose_name_plural = 'Settings'


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'phone', 'city', 'is_active', 'is_verified', 'created_at')
    list_filter = ('is_active', 'is_verified', 'business_types')
    search_fields = ('name', 'email', 'phone', 'registration_no', 'gstin')
    filter_horizontal = ('business_types',)
    readonly_fields = ('slug', 'created_at', 'updated_at')
    inlines = [CompanySubscriptionInline, CompanySettingInline, StoreInline, StaffProfileInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'registration_no', 'gstin', 'owner', 'business_types')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address', 'city', 'state', 'country')
        }),
        ('Branding', {
            'fields': ('logo',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'store_code', 'company', 'business_type', 'city', 'is_active', 'is_main_branch')
    list_filter = ('is_active', 'is_main_branch', 'business_type')
    search_fields = ('name', 'store_code', 'company__name')
    list_select_related = ('company', 'business_type')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'store', 'role', 'designation', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__email', 'company__name', 'store__name')
    list_select_related = ('user', 'company', 'store')


@admin.register(CompanySetting)
class CompanySettingAdmin(admin.ModelAdmin):
    list_display = ('company', 'currency', 'tax_enabled', 'invoice_prefix', 'timezone')
    search_fields = ('company__name',)
