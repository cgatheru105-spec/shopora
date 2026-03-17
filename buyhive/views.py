from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ItemForm, LoginForm, ProfilePictureForm, RegisterForm
from .models import Item, ItemImage, Profile

# Create your views here.
def index(request):
    return render(request, 'index.html')

def Buy_products(request):
    items = Item.objects.order_by("-created_at")
    return render(request, 'book.html', {"items": items})

def login_user(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["email"].strip()
        password = form.cleaned_data["password"]
        user = authenticate(request, username=identifier, password=password)
        if user is None and "@" in identifier:
            User = get_user_model()
            existing_user = User.objects.filter(email__iexact=identifier).first()
            if existing_user:
                user = authenticate(request, username=existing_user.username, password=password)
        if user is None:
            messages.error(request, "Invalid email or password.")
        else:
            login(request, user)
            next_url = request.GET.get("next") or reverse("dashboard")
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = reverse("dashboard")
            return redirect(next_url)

    return render(request, "login.html", {"form": form})

def register_user(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        Profile.objects.create(user=user, account_type=form.cleaned_data["account_type"])
        login(request, user)
        return redirect("dashboard")

    return render(request, "register.html", {"form": form})


def logout_user(request):
    logout(request)
    return redirect("index")


def _get_or_create_profile(user):
    if not user.is_authenticated:
        return None
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


@login_required
def dashboard(request):
    profile = _get_or_create_profile(request.user)

    if request.user.is_staff or (profile and profile.account_type == Profile.ACCOUNT_STAFF):
        return render(request, "admin/admindashboard.html", {"profile": profile})

    if profile and profile.account_type == Profile.ACCOUNT_SELLER:
        return render(request, "seller/dashboard.html", {"profile": profile})

    return render(request, "buyer/dashboard.html", {"profile": profile})


@login_required
def profile_edit(request):
    profile = _get_or_create_profile(request.user)
    form = ProfilePictureForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("dashboard")
    return render(request, "profile_edit.html", {"form": form, "profile": profile})


def items_public_list(request):
    items = (
        Item.objects.select_related("owner")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    return render(request, "items/public_list.html", {"items": items})


def _seller_required(request):
    if not request.user.is_authenticated:
        return False
    profile = _get_or_create_profile(request.user)
    return bool(profile and profile.account_type == Profile.ACCOUNT_SELLER) or request.user.is_staff


@login_required
def seller_items(request):
    if not _seller_required(request):
        raise Http404()
    items = Item.objects.filter(owner=request.user).prefetch_related("images").order_by("-created_at")
    return render(request, "seller/items_list.html", {"items": items})

def _is_image_upload(upload) -> bool:
    content_type = getattr(upload, "content_type", "") or ""
    return bool(content_type.startswith("image/"))


@login_required
def seller_item_create(request):
    if not _seller_required(request):
        raise Http404()
    form = ItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        uploads = request.FILES.getlist("images")
        if any(not _is_image_upload(upload) for upload in uploads):
            messages.error(request, "Please upload only image files.")
            return render(request, "seller/item_form.html", {"form": form, "mode": "create"})
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        for upload in uploads:
            ItemImage.objects.create(item=item, image=upload)
        messages.success(request, "Item created.")
        return redirect("seller_items")
    return render(request, "seller/item_form.html", {"form": form, "mode": "create"})


@login_required
def seller_item_update(request, pk: int):
    if not _seller_required(request):
        raise Http404()
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        uploads = request.FILES.getlist("images")
        if any(not _is_image_upload(upload) for upload in uploads):
            messages.error(request, "Please upload only image files.")
            return render(
                request,
                "seller/item_form.html",
                {"form": form, "mode": "edit", "item": item},
            )
        form.save()
        for upload in uploads:
            ItemImage.objects.create(item=item, image=upload)
        messages.success(request, "Item updated.")
        return redirect("seller_items")
    return render(
        request, "seller/item_form.html", {"form": form, "mode": "edit", "item": item}
    )


@login_required
def seller_item_delete(request, pk: int):
    if not _seller_required(request):
        raise Http404()
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Item deleted.")
        return redirect("seller_items")
    return render(request, "seller/item_confirm_delete.html", {"item": item})
