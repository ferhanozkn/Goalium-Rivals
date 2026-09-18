from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import GuestSession, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "display_name", "preferred_language", "is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")} ),
        ("Profil", {"fields": ("display_name", "preferred_language")} ),
        ("Yetkiler", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")} ),
        ("Zaman", {"fields": ("last_login", "created_at")} ),
    )
    readonly_fields = ["created_at", "last_login"]
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2")} ),
    )


@admin.register(GuestSession)
class GuestSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "display_name", "created_at", "last_seen_at", "expires_at"]
    readonly_fields = ["token_hash"]
