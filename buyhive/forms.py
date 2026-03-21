from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .constants import FOUNDER_USERNAMES_BY_KEY
from .models import Item, ItemReview, MarketCategory, Profile, SellerRating


class RegisterForm(forms.Form):
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


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("name", "category", "description", "price", "is_available")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "form-control"})
        self.fields["category"].queryset = MarketCategory.objects.order_by("name")
        self.fields["category"].required = False
        self.fields["category"].widget.attrs.update({"class": "form-select"})
        self.fields["description"].widget.attrs.update({"class": "form-control", "rows": 4})
        self.fields["price"].widget.attrs.update({"class": "form-control"})
        self.fields["is_available"].widget.attrs.update({"class": "form-check-input"})


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("profile_picture",)
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            )
        }

    def clean_profile_picture(self):
        file = self.cleaned_data.get("profile_picture")
        if not file:
            return file
        content_type = getattr(file, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValidationError("Please upload an image file.")
        return file


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


class CheckoutForm(forms.Form):
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

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number", "").strip()
        if not phone:
            raise ValidationError("Phone number is required.")
        # Remove non-digit characters for validation
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) < 10:
            raise ValidationError("Please enter a valid phone number.")
        return phone
