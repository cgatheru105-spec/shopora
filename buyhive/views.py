from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import ItemFilterForm, ItemForm, LoginForm, ProfilePictureForm, RegisterForm
from .models import Item, ItemImage, Profile

# Create your views here.
def index(request):
    # Get popular items - items from sellers with multiple listings (proxy for active sellers)
    # Since we don't have sales data, we'll use sellers with most items as a popularity proxy
    popular_sellers = (
        Item.objects.values('owner')
        .annotate(item_count=models.Count('id'))
        .filter(item_count__gt=1)  # Only sellers with more than 1 item
        .order_by('-item_count')[:3]  # Top 3 most active sellers
        .values_list('owner', flat=True)
    )
    
    popular_items = (
        Item.objects.select_related('owner')
        .prefetch_related('images')
        .filter(owner__in=popular_sellers)
        .order_by('-created_at')[:8]  # Get up to 8 items from popular sellers
    )
    
    return render(request, 'index.html', {'popular_items': popular_items})

def Buy_products(request):
    q = (request.GET.get("q") or "").strip()
    items = Item.objects.prefetch_related("images").order_by("-created_at")
    if q:
        items = items.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    return render(request, "book.html", {"items": items, "q": q})

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
        items = Item.objects.filter(owner=request.user)
        total_items = items.count()
        total_value = sum(item.price for item in items) if items else 0
        recent_items = items.order_by('-created_at')[:5]  # For slider
        return render(request, "seller/dashboard.html", {
            "profile": profile,
            "total_items": total_items,
            "total_value": total_value,
            "recent_items": recent_items,
        })

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
    form = ItemFilterForm(request.GET)
    items = (
        Item.objects.select_related("owner")
        .prefetch_related("images")
        .order_by("-created_at")
    )

    if form.is_valid():
        # Search filter
        search_query = form.cleaned_data.get("search")
        if search_query:
            items = items.filter(
                models.Q(name__icontains=search_query) |
                models.Q(description__icontains=search_query)
            )

        # Price filters
        min_price = form.cleaned_data.get("min_price")
        if min_price is not None:
            items = items.filter(price__gte=min_price)

        max_price = form.cleaned_data.get("max_price")
        if max_price is not None:
            items = items.filter(price__lte=max_price)

        # Sorting
        sort_by = form.cleaned_data.get("sort_by")
        if sort_by:
            items = items.order_by(sort_by)

    return render(request, "items/public_list.html", {
        "items": items,
        "filter_form": form
    })

def profiles_search(request):
    q = (request.GET.get("q") or "").strip()
    User = get_user_model()
    results = []
    if q:
        users = User.objects.filter(username__icontains=q).order_by("username")
        if request.user.is_authenticated:
            users = users.exclude(pk=request.user.pk)
        users = users[:50]
        profiles = Profile.objects.select_related("user").filter(user__in=users)
        profile_by_user_id = {p.user_id: p for p in profiles}
        results = [{"user": user, "profile": profile_by_user_id.get(user.id)} for user in users]
    return render(request, "profiles/search.html", {"q": q, "results": results})


def profile_public(request, username: str):
    User = get_user_model()
    user_obj = get_object_or_404(User, username=username)
    profile = Profile.objects.filter(user=user_obj).first()
    items = (
        Item.objects.filter(owner=user_obj)
        .prefetch_related("images")
        .order_by("-created_at")[:8]
    )
    return render(
        request,
        "profiles/public.html",
        {"profile_user": user_obj, "profile": profile, "items": items},
    )


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
