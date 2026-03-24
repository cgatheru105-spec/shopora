from django.contrib import admin

from .models import ContactSubmission, Item, MarketCategory, Profile, SellerNotification


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


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_filter = ("is_read", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "owner", "is_available", "created_at")
    list_select_related = ("owner", "category")
    search_fields = ("name", "category__name", "owner__username", "owner__email")
    list_filter = ("category", "is_available", "created_at")


@admin.register(SellerNotification)
class SellerNotificationAdmin(admin.ModelAdmin):
    list_display = ("seller", "notification_type", "title", "is_read", "created_at")
    list_select_related = ("seller", "item", "order")
    search_fields = ("seller__username", "title", "message")
    list_filter = ("notification_type", "is_read", "created_at")
    readonly_fields = ("created_at", "read_at")
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing notification
            return self.readonly_fields + ("seller", "notification_type", "title", "message", "item", "order", "order_item")
        return self.readonly_fields
