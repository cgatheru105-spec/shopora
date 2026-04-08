import re
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .constants import FOUNDER_USERNAMES_BY_KEY
from .models import (
    ContactSubmission,
    Item,
    ItemReview,
    MarketCategory,
    Profile,
    SellerFulfillment,
    SellerRating,
)


class LocationValidationMixin:
    latitude_field_name = "latitude"
    longitude_field_name = "longitude"
    label_field_name = "location_label"
    address_field_name = "location_address"

    def _clean_location_fields(self):
        label = (self.cleaned_data.get(self.label_field_name) or "").strip()
        address = (self.cleaned_data.get(self.address_field_name) or "").strip()
        raw_latitude = self.cleaned_data.get(self.latitude_field_name)
        raw_longitude = self.cleaned_data.get(self.longitude_field_name)

        latitude = None
        longitude = None
        if raw_latitude not in (None, ""):
            try:
                latitude = Decimal(str(raw_latitude))
            except Exception as exc:
                raise ValidationError("Please choose a valid map location.") from exc
        if raw_longitude not in (None, ""):
            try:
                longitude = Decimal(str(raw_longitude))
            except Exception as exc:
                raise ValidationError("Please choose a valid map location.") from exc

        has_any_location_value = any([label, address, latitude is not None, longitude is not None])
        if not has_any_location_value:
            self.cleaned_data[self.label_field_name] = ""
            self.cleaned_data[self.address_field_name] = ""
            self.cleaned_data[self.latitude_field_name] = None
            self.cleaned_data[self.longitude_field_name] = None
            return

        if not label:
            self.add_error(self.label_field_name, "Add a short label for this location.")
        if latitude is None or longitude is None:
            raise ValidationError("Pick the location on the map so we can save exact coordinates.")

        self.cleaned_data[self.label_field_name] = label
        self.cleaned_data[self.address_field_name] = address
        self.cleaned_data[self.latitude_field_name] = latitude
        self.cleaned_data[self.longitude_field_name] = longitude


class RegisterForm(LocationValidationMixin, forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    account_type = forms.ChoiceField(
        choices=(
            (Profile.ACCOUNT_BUYER, "Buyer (I want to buy)"),
            (Profile.ACCOUNT_SELLER, "Seller (I want to sell)"),
        ),
        required=True,
    )
    
    # Contact and address information
    phone_number = forms.CharField(max_length=15, required=False, help_text="Phone number for MPESA payments (optional)")
    delivery_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, help_text="Default delivery address (optional)")
    location_label = forms.CharField(max_length=120, required=False)
    location_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    latitude = forms.DecimalField(required=False, widget=forms.HiddenInput())
    longitude = forms.DecimalField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Username"}
        )
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Email"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Confirm password"}
        )
        self.fields["account_type"].widget.attrs.update({"class": "form-select"})
        self.fields["phone_number"].widget.attrs.update(
            {"class": "form-control", "placeholder": "0712345678 or 254712345678"}
        )
        self.fields["delivery_address"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Your delivery address"}
        )
        self.fields["location_label"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Home, farm gate, collection point"}
        )
        self.fields["location_address"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Nearest road, landmark, estate, or village"}
        )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Please enter a username.")
        username = FOUNDER_USERNAMES_BY_KEY.get(username.lower(), username)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number", "").strip()
        if phone_number:
            # Basic phone number validation for Kenyan numbers
            phone_number = ''.join(filter(str.isdigit, phone_number))
            if len(phone_number) < 9 or len(phone_number) > 12:
                raise ValidationError("Please enter a valid phone number.")
            if not (phone_number.startswith('07') and len(phone_number) == 10) and not (phone_number.startswith('2547') and len(phone_number) == 12):
                raise ValidationError("Please enter a valid Kenyan phone number (e.g., 0712345678 or 254712345678).")
        return phone_number or None

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        if password1:
            validate_password(password1)
        self._clean_location_fields()
        return cleaned

    def save(self, commit=True):
        email = self.cleaned_data["email"].strip().lower()
        username = self.cleaned_data["username"].strip()
        password = self.cleaned_data["password1"]
        user = User(username=username, email=email)
        user.set_password(password)
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Email or username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Password"}
        )


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactSubmission
        fields = ("name", "email", "phone_number", "subject", "message")
        widgets = {
            "name": forms.TextInput(),
            "email": forms.EmailInput(),
            "phone_number": forms.TextInput(),
            "subject": forms.TextInput(),
            "message": forms.Textarea(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Your name",
                "autocomplete": "name",
            }
        )
        self.fields["email"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }
        )
        self.fields["phone_number"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Optional phone number",
                "autocomplete": "tel",
            }
        )
        self.fields["subject"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "What can we help with?",
            }
        )
        self.fields["message"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Share the details so the team can follow up quickly.",
                "rows": 6,
            }
        )

    def clean_phone_number(self):
        phone_number = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone_number:
            return ""
        if not re.fullmatch(r"[0-9+\-\s()]{7,40}", phone_number):
            raise ValidationError("Please enter a valid phone number or leave it blank.")
        return " ".join(phone_number.split())


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("name", "category", "description", "condition_summary", "price")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "form-control"})
        self.fields["category"].queryset = MarketCategory.objects.order_by("name")
        self.fields["category"].required = False
        self.fields["category"].widget.attrs.update({"class": "form-select"})
        self.fields["description"].widget.attrs.update({"class": "form-control", "rows": 4})
        self.fields["condition_summary"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Harvested today, dry and sorted, chilled, ripe, etc.",
            }
        )
        self.fields["price"].widget.attrs.update({"class": "form-control"})
        self.fields["condition_summary"].required = True


class ProfileForm(LocationValidationMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = (
            "profile_picture",
            "phone_number",
            "delivery_address",
            "location_label",
            "location_address",
            "latitude",
            "longitude",
        )
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "0712345678 or 254712345678"}),
            "delivery_address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Default delivery notes or address"}),
            "location_label": forms.TextInput(attrs={"class": "form-control", "placeholder": "Home, farm gate, collection point"}),
            "location_address": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Nearest road, landmark, estate, or village"}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def clean_profile_picture(self):
        file = self.cleaned_data.get("profile_picture")
        if not file:
            return file
        content_type = getattr(file, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValidationError("Please upload an image file.")
        return file

    def clean_phone_number(self):
        phone_number = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone_number:
            return ""
        digits = "".join(filter(str.isdigit, phone_number))
        if len(digits) < 9 or len(digits) > 12:
            raise ValidationError("Please enter a valid phone number.")
        if not (digits.startswith("07") and len(digits) == 10) and not (
            digits.startswith("2547") and len(digits) == 12
        ):
            raise ValidationError("Please enter a valid Kenyan phone number (e.g., 0712345678 or 254712345678).")
        return digits

    def clean(self):
        cleaned = super().clean()
        self._clean_location_fields()
        return cleaned


class ItemFilterForm(forms.Form):
    category = forms.ChoiceField(
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": "form-select"})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Search items..."
        })
    )
    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Min price",
            "step": "0.01"
        })
    )
    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Max price",
            "step": "0.01"
        })
    )
    available_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ("-created_at", "Newest first"),
            ("created_at", "Oldest first"),
            ("price", "Price: Low to High"),
            ("-price", "Price: High to Low"),
            ("name", "Name: A to Z"),
            ("-name", "Name: Z to A"),
        ],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_choices = [("", "All categories")]
        category_choices.extend(
            (category.slug, category.name)
            for category in MarketCategory.objects.order_by("name")
        )
        self.fields["category"].choices = category_choices


class ItemReviewForm(forms.ModelForm):
    class Meta:
        model = ItemReview
        fields = ("rating", "title", "review_text")
        widgets = {
            "rating": forms.RadioSelect(choices=ItemReview.RATING_CHOICES),
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Review title (optional)"
            }),
            "review_text": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Share your experience with this item (optional)"
            })
        }


class SellerRatingForm(forms.ModelForm):
    class Meta:
        model = SellerRating
        fields = ("rating", "comment")
        widgets = {
            "rating": forms.RadioSelect(choices=SellerRating.RATING_CHOICES),
            "comment": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional: Share your experience with this seller"
            })
        }


class AvailabilityFilterForm(forms.Form):
    available_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Available items only"
    )


class CheckoutForm(LocationValidationMixin, forms.Form):
    latitude_field_name = "delivery_latitude"
    longitude_field_name = "delivery_longitude"
    label_field_name = "delivery_location_label"
    address_field_name = "delivery_address"

    buyer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Full name"
        })
    )
    buyer_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Email address"
        })
    )
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Phone number (e.g., 0712345678 or 254712345678)"
        })
    )
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "placeholder": "Delivery address",
            "rows": 3
        })
    )
    delivery_location_label = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Home, office, hostel, pickup gate",
        }),
    )
    delivery_latitude = forms.DecimalField(required=False, widget=forms.HiddenInput())
    delivery_longitude = forms.DecimalField(required=False, widget=forms.HiddenInput())

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            raise ValidationError("Phone number is required.")
        # Remove non-digit characters for validation
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) < 10:
            raise ValidationError("Please enter a valid phone number.")
        return phone

    def clean(self):
        cleaned = super().clean()
        self._clean_location_fields()
        return cleaned


class StockUpdateForm(forms.Form):
    """Form for adding stock to an item"""
    quantity = forms.IntegerField(
        min_value=1,
        max_value=10000,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Quantity to add",
            "min": "1"
        }),
        help_text="Enter the quantity to add to current stock"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Optional notes about this stock addition"
        })
    )


class SellerFulfillmentUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=SellerFulfillment.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    dispatch_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional dispatch notes for the buyer or your own records",
            }
        ),
    )

    def __init__(self, *args, current_status=SellerFulfillment.STATUS_PENDING, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_statuses = SellerFulfillment.allowed_statuses_from(current_status)
        self.fields["status"].choices = [
            choice for choice in SellerFulfillment.STATUS_CHOICES if choice[0] in allowed_statuses
        ]
