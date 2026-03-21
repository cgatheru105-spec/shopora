from django.contrib import admin

from .models import Item, MarketCategory, Profile


@admin.register(MarketCategory)
class MarketCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "theme", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug", "description")
    list_filter = ("theme",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "account_type", "created_at")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email")
    list_filter = ("account_type",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "owner", "is_available", "created_at")
    list_select_related = ("owner", "category")
    search_fields = ("name", "category__name", "owner__username", "owner__email")
    list_filter = ("category", "is_available", "created_at")
