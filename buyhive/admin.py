from django.contrib import admin

from .models import Item, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "account_type", "created_at")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email")
    list_filter = ("account_type",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "owner", "created_at")
    list_select_related = ("owner",)
    search_fields = ("name", "owner__username", "owner__email")
    list_filter = ("created_at",)
