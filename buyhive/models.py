from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


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
    
    # Contact and address information
    phone_number = models.CharField(max_length=15, blank=True, null=True, help_text="Phone number for MPESA payments")
    delivery_address = models.TextField(blank=True, null=True, help_text="Default delivery address")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.account_type})"

    @property
    def average_seller_rating(self):
        ratings = SellerRating.objects.filter(seller=self.user)
        if not ratings.exists():
            return 0
        return sum(r.rating for r in ratings) / ratings.count()

    @property
    def total_reviews(self):
        return SellerRating.objects.filter(seller=self.user).count()


class ContactSubmission(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone_number = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.subject} ({self.email})"


class MarketCategory(models.Model):
    THEME_CITRUS = "citrus"
    THEME_GARDEN = "garden"
    THEME_DAIRY = "dairy"
    THEME_GRAIN = "grain"
    THEME_SPICE = "spice"
    THEME_PANTRY = "pantry"
    THEME_CHOICES = (
        (THEME_CITRUS, "Citrus"),
        (THEME_GARDEN, "Garden"),
        (THEME_DAIRY, "Dairy"),
        (THEME_GRAIN, "Grain"),
        (THEME_SPICE, "Spice"),
        (THEME_PANTRY, "Pantry"),
    )

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=40, default="bi-basket3")
    description = models.CharField(max_length=180)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default=THEME_PANTRY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Item(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    category = models.ForeignKey(
        MarketCategory,
        on_delete=models.SET_NULL,
        related_name="items",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=10, help_text="Available quantity in stock")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.name

    @property
    def average_rating(self):
        reviews = ItemReview.objects.filter(item=self)
        if not reviews.exists():
            return 0
        return sum(r.rating for r in reviews) / reviews.count()

    @property
    def total_reviews(self):
        return ItemReview.objects.filter(item=self).count()

    @property
    def wishlist_count(self):
        return Wishlist.objects.filter(item=self).count()


class ItemImage(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="images")
    image = models.FileField(upload_to="items/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f"Image for {self.item_id}"


class ItemReview(models.Model):
    RATING_CHOICES = (
        (1, "⭐ Poor"),
        (2, "⭐⭐ Fair"),
        (3, "⭐⭐⭐ Good"),
        (4, "⭐⭐⭐⭐ Excellent"),
        (5, "⭐⭐⭐⭐⭐ Outstanding"),
    )

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="item_reviews")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="item_reviews"
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=100, blank=True)
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('item', 'reviewer')
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Review by {self.reviewer.username} for {self.item.name}"


class Wishlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="wishlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'item')
        ordering = ['-added_at']

    def __str__(self) -> str:
        return f"{self.user.username}'s wishlist - {self.item.name}"


class SellerRating(models.Model):
    RATING_CHOICES = (
        (1, "⭐ Poor"),
        (2, "⭐⭐ Fair"),
        (3, "⭐⭐⭐ Good"),
        (4, "⭐⭐⭐⭐ Excellent"),
        (5, "⭐⭐⭐⭐⭐ Outstanding"),
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_ratings"
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="given_seller_ratings"
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('seller', 'rater')
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Rating of {self.seller.username} by {self.rater.username}"


class RecentlyViewed(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recently_viewed"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'item')
        ordering = ['-viewed_at']

    def __str__(self) -> str:
        return f"{self.user.username} viewed {self.item.name}"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('payment_initiated', 'Payment Initiated'),
        ('paid', 'Paid'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    )

    order_id = models.CharField(max_length=50, unique=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    buyer_name = models.CharField(max_length=100)
    buyer_email = models.EmailField()
    delivery_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Order {self.order_id} by {self.buyer.username}"

    @property
    def is_paid(self):
        return self.status == 'paid'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sold_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['-order__created_at']

    def __str__(self) -> str:
        return f"{self.quantity}x {self.item.name} in {self.order.order_id}"


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    checkout_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Payment for {self.order.order_id} - {self.status}"


class PaymentLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="logs")
    event = models.CharField(max_length=100)
    message = models.TextField()
    response_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.payment.order.order_id} - {self.event}"


class SellerNotification(models.Model):
    NOTIFICATION_TYPES = (
        ('product_sold', 'Product Sold'),
        ('stock_low', 'Stock Low'),
        ('order_placed', 'Order Placed'),
        ('order_cancelled', 'Order Cancelled'),
        ('review_received', 'Review Received'),
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_notifications"
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_notifications")
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_notifications")
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Seller Notifications"

    def __str__(self) -> str:
        return f"{self.seller.username} - {self.get_notification_type_display()}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
