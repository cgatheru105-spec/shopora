from django.conf import settings
from django.db import models


class Profile(models.Model):
    ACCOUNT_BUYER = "buyer"
    ACCOUNT_SELLER = "seller"
    ACCOUNT_STAFF = "staff"
    ACCOUNT_TYPES = (
        (ACCOUNT_BUYER, "Buyer"),
        (ACCOUNT_SELLER, "Seller"),
        (ACCOUNT_STAFF, "Staff"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    account_type = models.CharField(
        max_length=10, choices=ACCOUNT_TYPES, default=ACCOUNT_BUYER
    )
    profile_picture = models.FileField(upload_to="profiles/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.account_type})"


class Item(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class ItemImage(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to="items/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Image for {self.item_id}"
