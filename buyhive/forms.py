from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Item, Profile


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=False)
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
        self.fields["full_name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Full name"}
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

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
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
        password = self.cleaned_data["password1"]
        user = User(username=email, email=email)
        user.first_name = (self.cleaned_data.get("full_name") or "").strip()
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

    def clean_profile_picture(self):
        file = self.cleaned_data.get("profile_picture")
        if not file:
            return file
        content_type = getattr(file, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValidationError("Please upload an image file.")
        return file
