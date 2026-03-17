from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Item, Profile


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

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Please enter a username.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

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
        fields = ("name", "description", "price")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "form-control"})
        self.fields["description"].widget.attrs.update({"class": "form-control", "rows": 4})
        self.fields["price"].widget.attrs.update({"class": "form-control"})


class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("profile_picture",)
        widgets = {
            "profile_picture": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            )
        }


class ItemFilterForm(forms.Form):
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

    def clean_profile_picture(self):
        file = self.cleaned_data.get("profile_picture")
        if not file:
            return file
        content_type = getattr(file, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValidationError("Please upload an image file.")
        return file
