from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import uuid
import json
import logging
from urllib.parse import urlencode

from .constants import FOUNDER_USERNAMES, FOUNDER_USERNAMES_BY_KEY
from .forms import (
    AvailabilityFilterForm, CheckoutForm, ContactForm, ItemFilterForm, ItemForm,
    ItemReviewForm, LoginForm, ProfilePictureForm, RegisterForm, SellerRatingForm,
    StockUpdateForm
)
from .models import (
    Item, ItemImage, ItemReview, MarketCategory, Order, OrderItem, Payment,
    PaymentLog, Profile, RecentlyViewed, SellerRating, SellerNotification, Wishlist
)
from .mpesa_utils import MPESAConfigurationError, create_mpesa_client

logger = logging.getLogger(__name__)

CHECKOUT_SESSION_KEY = "checkout_cart"
CLEAR_BROWSER_CART_SESSION_KEY = "clear_browser_cart_on_next_page"


def _active_seller_ids(limit=6, minimum_items=2):
    return list(
        Item.objects.values("owner")
        .annotate(item_count=models.Count("id"))
        .filter(item_count__gte=minimum_items)
        .order_by("-item_count", "owner")
        .values_list("owner", flat=True)[:limit]
    )


def _founder_filter():
    founder_query = models.Q()
    for username in FOUNDER_USERNAMES:
        founder_query |= models.Q(username__iexact=username)
    return founder_query


def _first_item_image_url(item):
    prefetched_images = getattr(item, "_prefetched_objects_cache", {}).get("images")
    if prefetched_images is not None:
        if prefetched_images:
            return prefetched_images[0].image.url
        return ""

    first_image = item.images.order_by("created_at").first()
    return first_image.image.url if first_image else ""


def _serialize_item_card(item, include_owner=False, user=None):
    card = {
        "id": item.id,
        "name": item.name,
        "description": item.description or "No description available",
        "price": item.price,
        "created_at": item.created_at,
        "image_url": _first_item_image_url(item),
        "is_available": item.is_available,
        "average_rating": item.average_rating,
        "total_reviews": item.total_reviews,
        "wishlist_count": item.wishlist_count,
        "is_wishlisted": False,
        "category_name": item.category.name if item.category else "",
        "category_slug": item.category.slug if item.category else "",
    }
    if user and user.is_authenticated:
        card["is_wishlisted"] = Wishlist.objects.filter(user=user, item=item).exists()
    if include_owner:
        card["owner_username"] = item.owner.username
        card["owner_profile_url"] = reverse("profile_public", args=[item.owner.username])
        card["seller_rating"] = item.owner.profile.average_seller_rating if hasattr(item.owner, 'profile') else 0
    return card


def _get_marketplace_snapshot():
    snapshot = Item.objects.aggregate(
        total_listings=models.Count("id"),
        average_price=models.Avg("price"),
        lowest_price=models.Min("price"),
        newest_listing=models.Max("created_at"),
    )
    snapshot["active_sellers"] = (
        Item.objects.values("owner").distinct().count()
    )
    snapshot["community_members"] = Profile.objects.exclude(
        account_type=Profile.ACCOUNT_STAFF
    ).count()
    snapshot["active_categories"] = (
        MarketCategory.objects.filter(items__isnull=False).distinct().count()
    )
    return snapshot


def _items_public_url(**params):
    base_url = reverse("items_public")
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def _get_category_hubs(limit=6, owner=None):
    item_filter = models.Q()
    if owner is not None:
        item_filter &= models.Q(items__owner=owner)

    categories = (
        MarketCategory.objects.annotate(
            listing_count=models.Count("items", filter=item_filter, distinct=True),
            available_count=models.Count(
                "items",
                filter=item_filter & models.Q(items__is_available=True),
                distinct=True,
            ),
            seller_count=models.Count("items__owner", filter=item_filter, distinct=True),
            average_price=models.Avg("items__price", filter=item_filter),
        )
        .filter(listing_count__gt=0)
        .order_by("-listing_count", "name")[:limit]
    )

    hubs = []
    for category in categories:
        hubs.append(
            {
                "name": category.name,
                "slug": category.slug,
                "icon": category.icon,
                "theme": category.theme,
                "description": category.description,
                "listing_count": category.listing_count,
                "available_count": category.available_count,
                "seller_count": category.seller_count,
                "average_price": category.average_price,
                "browse_url": _items_public_url(category=category.slug),
            }
        )
    return hubs


def _get_market_radar():
    radar = []

    busiest_category = (
        MarketCategory.objects.annotate(
            listing_count=models.Count("items", distinct=True),
            seller_count=models.Count("items__owner", distinct=True),
        )
        .filter(listing_count__gt=0)
        .order_by("-listing_count", "name")
        .first()
    )
    if busiest_category:
        radar.append(
            {
                "eyebrow": "Busiest aisle",
                "title": busiest_category.name,
                "value": f"{busiest_category.listing_count} live listing{'s' if busiest_category.listing_count != 1 else ''}",
                "summary": f"Stocked by {busiest_category.seller_count} seller{'s' if busiest_category.seller_count != 1 else ''}.",
                "href": _items_public_url(category=busiest_category.slug),
                "cta": "Browse aisle",
                "theme": busiest_category.theme,
            }
        )

    most_saved_item = (
        Item.objects.select_related("owner", "category")
        .annotate(
            save_count=models.Count("wishlisted_by", distinct=True),
            review_count=models.Count("item_reviews", distinct=True),
        )
        .filter(save_count__gt=0)
        .order_by("-save_count", "-review_count", "-created_at")
        .first()
    )
    if most_saved_item:
        radar.append(
            {
                "eyebrow": "Most saved",
                "title": most_saved_item.name,
                "value": f"{most_saved_item.save_count} wishlist save{'s' if most_saved_item.save_count != 1 else ''}",
                "summary": f"From @{most_saved_item.owner.username} and still drawing attention.",
                "href": reverse("profile_public", args=[most_saved_item.owner.username]),
                "cta": "View seller",
                "theme": most_saved_item.category.theme if most_saved_item.category else MarketCategory.THEME_PANTRY,
            }
        )

    top_rated_item = (
        Item.objects.select_related("owner", "category")
        .annotate(
            average_score=models.Avg("item_reviews__rating"),
            review_count=models.Count("item_reviews", distinct=True),
        )
        .filter(review_count__gt=0)
        .order_by("-average_score", "-review_count", "-created_at")
        .first()
    )
    if top_rated_item:
        radar.append(
            {
                "eyebrow": "Top rated pick",
                "title": top_rated_item.name,
                "value": f"{top_rated_item.average_score:.1f}/5 from {top_rated_item.review_count} review{'s' if top_rated_item.review_count != 1 else ''}",
                "summary": f"Buyers are rating this @{top_rated_item.owner.username} listing especially highly.",
                "href": reverse("profile_public", args=[top_rated_item.owner.username]),
                "cta": "Meet seller",
                "theme": top_rated_item.category.theme if top_rated_item.category else MarketCategory.THEME_GARDEN,
            }
        )

    most_ordered_item = (
        OrderItem.objects.filter(item__isnull=False)
        .values("item_id", "item__name", "item__owner__username", "item__category__theme")
        .annotate(total_units=models.Sum("quantity"), total_orders=models.Count("order", distinct=True))
        .order_by("-total_units", "-total_orders")
        .first()
    )
    if most_ordered_item:
        radar.append(
            {
                "eyebrow": "Fast mover",
                "title": most_ordered_item["item__name"],
                "value": f"{most_ordered_item['total_units']} units across {most_ordered_item['total_orders']} order{'s' if most_ordered_item['total_orders'] != 1 else ''}",
                "summary": f"One of the marketplace items buyers keep coming back to from @{most_ordered_item['item__owner__username']}.",
                "href": reverse("profile_public", args=[most_ordered_item["item__owner__username"]]),
                "cta": "See storefront",
                "theme": most_ordered_item["item__category__theme"] or MarketCategory.THEME_CITRUS,
            }
        )
    elif not radar:
        radar.append(
            {
                "eyebrow": "Market radar",
                "title": "First movers wanted",
                "value": "No engagement signals yet",
                "summary": "As shoppers save, review, and order products, this panel turns into a live pulse of the marketplace.",
                "href": reverse("items_public"),
                "cta": "Explore listings",
                "theme": MarketCategory.THEME_PANTRY,
            }
        )

    return radar[:4]


def _get_buyer_activity(user):
    if not user.is_authenticated:
        return {}

    latest_order = Order.objects.filter(buyer=user).order_by("-created_at").first()
    return {
        "wishlist_count": Wishlist.objects.filter(user=user).count(),
        "recently_viewed_count": RecentlyViewed.objects.filter(user=user).count(),
        "orders_count": Order.objects.filter(buyer=user).count(),
        "latest_order_id": latest_order.order_id if latest_order else "",
        "latest_order_status": latest_order.get_status_display() if latest_order else "",
    }


def _get_spotlight_sellers(limit=4, exclude_user_id=None):
    User = get_user_model()
    users = User.objects.annotate(item_count=models.Count("items", distinct=True)).filter(
        item_count__gt=0
    )
    if exclude_user_id is not None:
        users = users.exclude(pk=exclude_user_id)

    users = list(users.order_by("-item_count", "-date_joined", "username")[:limit])
    if not users:
        return []

    profiles = Profile.objects.select_related("user").filter(user__in=users)
    profile_by_user_id = {profile.user_id: profile for profile in profiles}

    spotlights = []
    for user in users:
        profile = profile_by_user_id.get(user.id)
        profile_picture_url = (
            profile.profile_picture.url
            if profile and profile.profile_picture
            else ""
        )
        spotlights.append(
            {
                "username": user.username,
                "item_count": user.item_count,
                "profile_type": profile.get_account_type_display() if profile else "Member",
                "profile_url": reverse("profile_public", args=[user.username]),
                "profile_picture_url": profile_picture_url,
                "joined_at": user.date_joined,
                "is_founder": user.username.lower() in FOUNDER_USERNAMES_BY_KEY,
            }
        )
    return spotlights


def _get_founders():
    User = get_user_model()
    founder_users = list(
        User.objects.annotate(item_count=models.Count("items", distinct=True)).filter(
            _founder_filter()
        )
    )
    profiles = Profile.objects.select_related("user").filter(user__in=founder_users)
    profile_by_user_id = {profile.user_id: profile for profile in profiles}
    founder_by_key = {user.username.lower(): user for user in founder_users}

    founders = []
    for username in FOUNDER_USERNAMES:
        user = founder_by_key.get(username.lower())
        profile = profile_by_user_id.get(user.id) if user else None
        item_count = getattr(user, "item_count", 0) if user else 0
        profile_picture_url = None
        if profile and profile.profile_picture:
            profile_picture_url = profile.profile_picture.url
        
        founders.append(
            {
                "seat_name": username,
                "display_name": user.username if user else username,
                "profile_type": profile.get_account_type_display() if profile else "",
                "profile_url": reverse("profile_public", args=[user.username]) if user else "",
                "profile_picture_url": profile_picture_url,
                "item_count": item_count,
                "is_live": bool(user),
                "user_id": user.id if user else None,
                "status_label": "Founding Member" if user else "Throne Reserved",
                "description": (
                    f"{profile.get_account_type_display()} account with {item_count} listing{'s' if item_count != 1 else ''}."
                    if user and profile
                    else "Profile coming online soon."
                    if user
                    else "Waiting for the rightful owner to claim this seat."
                ),
            }
        )
    return founders


# Create your views here.
def index(request):
    popular_sellers = _active_seller_ids(limit=4, minimum_items=2)

    popular_items = list(
        Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .filter(owner__in=popular_sellers)
        .order_by("-created_at")[:8]
    )
    popular_cards = [
        _serialize_item_card(item, include_owner=True, user=request.user) for item in popular_items
    ]

    fresh_cards = [
        _serialize_item_card(item, include_owner=True, user=request.user)
        for item in Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("-created_at")[:4]
    ]
    budget_cards = [
        _serialize_item_card(item, include_owner=True, user=request.user)
        for item in Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("price", "-created_at")[:4]
    ]

    return render(
        request,
        "index.html",
        {
            "popular_cards": popular_cards,
            "fresh_cards": fresh_cards,
            "budget_cards": budget_cards,
            "spotlight_sellers": _get_spotlight_sellers(),
            "marketplace_snapshot": _get_marketplace_snapshot(),
            "category_hubs": _get_category_hubs(),
            "market_radar": _get_market_radar(),
            "founders": _get_founders(),
        },
    )

def Buy_products(request):
    q = (request.GET.get("q") or "").strip()
    items = (
        Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    if q:
        items = items.filter(
            models.Q(name__icontains=q) | models.Q(description__icontains=q)
        )
    
    # Filter by availability if requested
    available_only = request.GET.get("available_only") == "on"
    if available_only:
        items = items.filter(is_available=True)

    items_count = items.count()

    return render(request, "book.html", {
        "items": items,
        "items_count": items_count,
        "q": q,
        "available_only": available_only,
    })

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
        Profile.objects.create(
            user=user, 
            account_type=form.cleaned_data["account_type"],
            phone_number=form.cleaned_data.get("phone_number"),
            delivery_address=form.cleaned_data.get("delivery_address")
        )
        login(request, user)
        return redirect("dashboard")

    return render(request, "register.html", {"form": form})


def logout_user(request):
    logout(request)
    return redirect("index")


def _initial_contact_data(user):
    if not user.is_authenticated:
        return {}

    profile = getattr(user, "profile", None)
    full_name = user.get_full_name().strip()
    initial = {
        "name": full_name or user.username,
        "email": user.email,
    }
    if profile and profile.phone_number:
        initial["phone_number"] = profile.phone_number
    return initial


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Thanks for reaching out. Your message has been saved and the team can review it now.",
            )
            return redirect("contact")
    else:
        form = ContactForm(initial=_initial_contact_data(request.user))

    return render(request, "contact.html", {"form": form})


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
        items = Item.objects.filter(owner=request.user).select_related("category").prefetch_related("images")
        total_items = items.count()
        recent_items = items.order_by('-created_at')[:5]  # For slider
        seller_snapshot = items.aggregate(
            total_value=models.Sum("price"),
            average_price=models.Avg("price"),
            latest_listing=models.Max("created_at"),
        )
        seller_performance = OrderItem.objects.filter(
            seller=request.user, order__status__in=["paid", "completed"]
        ).aggregate(
            orders_count=models.Count("order", distinct=True),
            units_sold=models.Sum("quantity"),
            revenue=models.Sum("subtotal"),
        )
        seller_engagement = items.aggregate(
            wishlist_saves=models.Count("wishlisted_by", distinct=True),
            reviews_count=models.Count("item_reviews", distinct=True),
            average_rating=models.Avg("item_reviews__rating"),
        )
        return render(request, "seller/dashboard.html", {
            "profile": profile,
            "total_items": total_items,
            "total_value": seller_snapshot["total_value"] or 0,
            "recent_items": recent_items,
            "seller_snapshot": seller_snapshot,
            "seller_performance": seller_performance,
            "seller_engagement": seller_engagement,
            "category_hubs": _get_category_hubs(limit=4, owner=request.user),
        })

    buyer_cards = [
        _serialize_item_card(item, include_owner=True, user=request.user)
        for item in Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("-created_at")[:3]
    ]
    budget_cards = [
        _serialize_item_card(item, include_owner=True, user=request.user)
        for item in Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("price", "-created_at")[:3]
    ]

    return render(
        request,
        "buyer/dashboard.html",
        {
            "profile": profile,
            "marketplace_snapshot": _get_marketplace_snapshot(),
            "recommended_cards": buyer_cards,
            "budget_cards": budget_cards,
            "market_radar": _get_market_radar(),
            "buyer_activity": _get_buyer_activity(request.user),
            "category_hubs": _get_category_hubs(limit=4),
            "spotlight_sellers": _get_spotlight_sellers(
                limit=3, exclude_user_id=request.user.id
            ),
        },
    )


@login_required
def profile_edit(request):
    profile = _get_or_create_profile(request.user)
    user_items = Item.objects.filter(owner=request.user)
    profile_stats = user_items.aggregate(
        total_items=models.Count("id"),
        avg_price=models.Avg("price"),
        latest_listing=models.Max("created_at"),
    )
    form = ProfilePictureForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("dashboard")
    return render(
        request,
        "profile_edit.html",
        {
            "form": form,
            "profile": profile,
            "profile_stats": profile_stats,
            "is_founder": request.user.username.lower() in FOUNDER_USERNAMES_BY_KEY,
            "member_since": profile.created_at or request.user.date_joined,
        },
    )


def items_public_list(request):
    form = ItemFilterForm(request.GET)
    items = (
        Item.objects.select_related("owner", "category")
        .prefetch_related("images")
        .order_by("-created_at")
    )
    quick_filter = (request.GET.get("quick") or "").strip()
    marketplace_snapshot = _get_marketplace_snapshot()
    active_category = None

    if form.is_valid():
        category_slug = form.cleaned_data.get("category")
        if category_slug:
            items = items.filter(category__slug=category_slug)
            active_category = MarketCategory.objects.filter(slug=category_slug).first()

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

    if quick_filter == "budget" and marketplace_snapshot.get("average_price") is not None:
        items = items.filter(price__lte=marketplace_snapshot["average_price"]).order_by(
            "price", "-created_at"
        )
    elif quick_filter == "community":
        items = items.filter(owner__in=_active_seller_ids(limit=12, minimum_items=2))
    elif quick_filter == "fresh":
        items = items.order_by("-created_at")
    
    # Filter by availability if requested
    available_only = request.GET.get("available_only") == "on"
    if available_only:
        items = items.filter(is_available=True)

    items_count = items.count()
    items_list = list(items)
    items_cards = [_serialize_item_card(item, include_owner=True, user=request.user) for item in items_list]

    return render(request, "items/public_list.html", {
        "items": items,
        "items_cards": items_cards,
        "filter_form": form,
        "quick_filter": quick_filter,
        "items_count": items_count,
        "marketplace_snapshot": marketplace_snapshot,
        "category_hubs": _get_category_hubs(limit=6),
        "active_category": active_category,
        "available_only": available_only,
    })

def profiles_search(request):
    q = (request.GET.get("q") or "").strip()
    account_type_filter = request.GET.get("account_type", "")
    sort_by = request.GET.get("sort_by", "username")
    
    User = get_user_model()
    results = []
    users = User.objects.annotate(item_count=models.Count("items", distinct=True)).all()

    if q:
        users = users.filter(username__icontains=q)

    if account_type_filter:
        users = users.filter(profile__account_type=account_type_filter)

    if request.user.is_authenticated:
        users = users.exclude(pk=request.user.pk)

    if sort_by == "username":
        users = users.order_by("username")
    elif sort_by == "date_joined":
        users = users.order_by("-date_joined")
    elif sort_by == "items_count":
        users = users.order_by("-item_count", "username")

    users = list(users[:100])

    if users:
        profiles = Profile.objects.select_related("user").filter(user__in=users)
        profile_by_user_id = {p.user_id: p for p in profiles}

        results = []
        for user in users:
            profile = profile_by_user_id.get(user.id)
            results.append({
                "user": user,
                "profile": profile,
                "item_count": user.item_count,
                "is_founder": user.username.lower() in FOUNDER_USERNAMES_BY_KEY,
                "profile_type": profile.get_account_type_display() if profile else "",
                "profile_url": reverse("profile_public", args=[user.username]),
            })
    
    return render(request, "profiles/search.html", {
        "q": q, 
        "account_type_filter": account_type_filter,
        "sort_by": sort_by,
        "results": results,
        "founders": _get_founders(),
    })


def profile_public(request, username: str):
    User = get_user_model()
    user_obj = get_object_or_404(User, username__iexact=username)
    profile = Profile.objects.filter(user=user_obj).first()
    user_items = Item.objects.filter(owner=user_obj)
    profile_stats = user_items.aggregate(
        total_items=models.Count("id"),
        avg_price=models.Avg("price"),
        min_price=models.Min("price"),
        max_price=models.Max("price"),
        latest_listing=models.Max("created_at"),
    )
    items = list(
        user_items
        .select_related("category")
        .prefetch_related("images")
        .order_by("-created_at")[:8]
    )
    item_cards = [_serialize_item_card(item) for item in items]
    featured_item = item_cards[0] if item_cards else None
    return render(
        request,
        "profiles/public.html",
        {
            "profile_user": user_obj,
            "profile": profile,
            "item_cards": item_cards,
            "featured_item": featured_item,
            "profile_stats": profile_stats,
            "is_founder": user_obj.username.lower() in FOUNDER_USERNAMES_BY_KEY,
            "profile_type": profile.get_account_type_display() if profile else "User",
            "member_since": profile.created_at if profile else user_obj.date_joined,
        },
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
    items = Item.objects.filter(owner=request.user).select_related("category").prefetch_related("images").order_by("-created_at")
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


# Wishlist views
@login_required
@require_http_methods(["POST"])
def toggle_wishlist(request, pk: int):
    """Toggle item in wishlist (AJAX endpoint)"""
    item = get_object_or_404(Item, pk=pk)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, item=item)
    
    if not created:
        wishlist_item.delete()
        is_wishlisted = False
    else:
        is_wishlisted = True
    
    return JsonResponse({
        "success": True,
        "is_wishlisted": is_wishlisted,
        "wishlist_count": item.wishlist_count
    })


@login_required
def wishlist_view(request):
    """Show user's wishlist"""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related("item").order_by("-added_at")
    items = [w.item for w in wishlist_items]
    items_cards = [_serialize_item_card(item, include_owner=True, user=request.user) for item in items]
    
    return render(request, "buyer/wishlist.html", {
        "items": items,
        "items_cards": items_cards,
        "wishlist_count": len(items),
    })


# Review views
@login_required
def item_review_create(request, item_id: int):
    """Create or update a review for an item"""
    item = get_object_or_404(Item, pk=item_id)
    review, created = ItemReview.objects.get_or_create(item=item, reviewer=request.user)
    
    form = ItemReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Review submitted successfully!" if created else "Review updated!")
        return redirect("item_detail", pk=item_id)
    
    return render(request, "items/review_form.html", {
        "form": form,
        "item": item,
        "is_update": not created,
    })


# Seller rating views
@login_required
def seller_rating_create(request, seller_username: str):
    """Create or update a rating for a seller"""
    User = get_user_model()
    seller = get_object_or_404(User, username__iexact=seller_username)
    
    # Prevent self-rating
    if request.user == seller:
        messages.error(request, "You cannot rate yourself.")
        return redirect("profile_public", username=seller.username)
    
    rating, created = SellerRating.objects.get_or_create(seller=seller, rater=request.user)
    
    form = SellerRatingForm(request.POST or None, instance=rating)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Seller rating submitted successfully!" if created else "Rating updated!")
        return redirect("profile_public", username=seller.username)
    
    return render(request, "profiles/rating_form.html", {
        "form": form,
        "seller": seller,
        "is_update": not created,
    })


# Recently viewed tracking
@login_required
@require_http_methods(["POST"])
def track_item_view(request, item_id: int):
    """Track when a user views an item"""
    item = get_object_or_404(Item, pk=item_id)
    RecentlyViewed.objects.update_or_create(user=request.user, item=item)
    return JsonResponse({"success": True})


@login_required
def recently_viewed_items(request):
    """Show user's recently viewed items"""
    recently_viewed = RecentlyViewed.objects.filter(user=request.user).select_related("item").order_by("-viewed_at")[:20]
    items = [rv.item for rv in recently_viewed]
    items_cards = [_serialize_item_card(item, include_owner=True, user=request.user) for item in items]
    
    return render(request, "buyer/recently_viewed.html", {
        "items": items,
        "items_cards": items_cards,
        "count": len(items),
    })


def _normalize_cart_item_id(raw_item_id):
    item_id = str(raw_item_id or "").strip()
    if item_id.startswith("item-"):
        item_id = item_id[5:]
    return item_id if item_id.isdigit() else ""


def _parse_checkout_cart(data):
    cart = {}
    invalid_entries = 0

    for key, value in data.items():
        if not key.startswith("cart_"):
            continue

        item_id = _normalize_cart_item_id(key[5:])
        if not item_id:
            invalid_entries += 1
            continue

        try:
            quantity = int(value)
        except (TypeError, ValueError):
            invalid_entries += 1
            continue

        if quantity < 1:
            invalid_entries += 1
            continue

        cart[item_id] = quantity

    return cart, invalid_entries


def _get_checkout_cart_from_session(request):
    raw_cart = request.session.get(CHECKOUT_SESSION_KEY, {})
    if not isinstance(raw_cart, dict):
        return {}

    normalized_cart = {}
    for item_id, quantity in raw_cart.items():
        normalized_id = _normalize_cart_item_id(item_id)
        try:
            parsed_quantity = int(quantity)
        except (TypeError, ValueError):
            continue

        if normalized_id and parsed_quantity > 0:
            normalized_cart[normalized_id] = parsed_quantity

    if normalized_cart != raw_cart:
        request.session[CHECKOUT_SESSION_KEY] = normalized_cart
        request.session.modified = True

    return normalized_cart


def _set_checkout_cart(request, cart):
    request.session[CHECKOUT_SESSION_KEY] = cart
    request.session.modified = True


def _clear_checkout_cart(request):
    if CHECKOUT_SESSION_KEY in request.session:
        del request.session[CHECKOUT_SESSION_KEY]
        request.session.modified = True


def _flag_browser_cart_clear(request):
    request.session[CLEAR_BROWSER_CART_SESSION_KEY] = True
    request.session.modified = True


def _consume_browser_cart_clear_flag(request):
    should_clear = bool(request.session.pop(CLEAR_BROWSER_CART_SESSION_KEY, False))
    if should_clear:
        request.session.modified = True
    return should_clear


def _resolve_checkout_cart(cart):
    normalized_ids = [int(item_id) for item_id in cart.keys() if item_id.isdigit()]
    items_by_id = Item.objects.select_related("owner").in_bulk(normalized_ids)

    valid_cart = {}
    cart_items = []
    total_amount = 0
    unavailable_count = 0
    missing_count = 0

    for item_id, quantity in cart.items():
        item = items_by_id.get(int(item_id))
        if item is None:
            missing_count += 1
            continue
        if not item.is_available:
            unavailable_count += 1
            continue

        subtotal = item.price * quantity
        total_amount += subtotal
        valid_cart[item_id] = quantity
        cart_items.append(
            {
                "item": item,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

    return {
        "cart": valid_cart,
        "cart_items": cart_items,
        "total_amount": total_amount,
        "missing_count": missing_count,
        "unavailable_count": unavailable_count,
    }


def _checkout_prefill_initial_data(user):
    initial_data = {
        "buyer_name": user.get_full_name() or user.username,
        "buyer_email": user.email,
    }
    profile = getattr(user, "profile", None)
    if profile:
        if profile.phone_number:
            initial_data["phone_number"] = profile.phone_number
        if profile.delivery_address:
            initial_data["delivery_address"] = profile.delivery_address
    return {key: value for key, value in initial_data.items() if value}


def _payment_status_payload(order, payment):
    return {
        "order_id": order.order_id,
        "order_status": order.status,
        "order_status_label": order.get_status_display(),
        "payment_status": payment.status,
        "payment_status_label": payment.get_status_display(),
        "is_paid": order.status in {"paid", "completed"} or payment.status == "completed",
        "is_terminal": order.status in {"paid", "completed", "failed", "cancelled"},
        "result_description": payment.result_description,
        "status_url": reverse("payment_status", args=[order.order_id]),
        "order_url": reverse("order_detail", args=[order.order_id]),
    }


# Checkout and Payment Views
@login_required
def checkout(request):
    """Review or submit a checkout sourced from the browser cart."""
    action = request.POST.get("checkout_action")
    if request.method == "POST" and action == "review":
        cart, invalid_entries = _parse_checkout_cart(request.POST)
        if invalid_entries:
            messages.warning(request, "Some cart entries were ignored because their quantities were invalid.")

        resolved_cart = _resolve_checkout_cart(cart)
        if resolved_cart["missing_count"] or resolved_cart["unavailable_count"]:
            messages.warning(request, "Some cart items were removed because they are missing or no longer available.")

        if not resolved_cart["cart_items"]:
            _clear_checkout_cart(request)
            messages.warning(request, "Your cart is empty.")
            return redirect("items_public")

        _set_checkout_cart(request, resolved_cart["cart"])
        return redirect("checkout")

    session_cart = _get_checkout_cart_from_session(request)
    if not session_cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("items_public")

    resolved_cart = _resolve_checkout_cart(session_cart)
    if resolved_cart["missing_count"] or resolved_cart["unavailable_count"]:
        if resolved_cart["cart"]:
            _set_checkout_cart(request, resolved_cart["cart"])
            messages.warning(request, "Your checkout was updated because some items are missing or no longer available.")
        else:
            _clear_checkout_cart(request)
            messages.warning(request, "Your cart is empty.")
            return redirect("items_public")

    cart_items = resolved_cart["cart_items"]
    total_amount = resolved_cart["total_amount"]

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if resolved_cart["missing_count"] or resolved_cart["unavailable_count"]:
            messages.warning(request, "Please review your updated cart before completing checkout.")
        elif form.is_valid():
            with transaction.atomic():
                order_id = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
                order = Order.objects.create(
                    order_id=order_id,
                    buyer=request.user,
                    total_amount=total_amount,
                    phone_number=form.cleaned_data["phone_number"],
                    buyer_name=form.cleaned_data["buyer_name"],
                    buyer_email=form.cleaned_data["buyer_email"],
                    delivery_address=form.cleaned_data["delivery_address"],
                    status="pending",
                )

                for cart_item in cart_items:
                    order_item = OrderItem.objects.create(
                        order=order,
                        item=cart_item["item"],
                        seller=cart_item["item"].owner,
                        quantity=cart_item["quantity"],
                        price=cart_item["item"].price,
                        subtotal=cart_item["subtotal"],
                    )
                    
                    # Decrease item stock
                    item = cart_item["item"]
                    item.stock -= cart_item["quantity"]
                    if item.stock < 0:
                        item.stock = 0
                    item.save()
                    
                    # Create notification for seller
                    _create_seller_notification(
                        seller=cart_item["item"].owner,
                        notification_type='product_sold',
                        title=f'Product Sold: {item.name}',
                        message=f'Your product "{item.name}" has been ordered by {order.buyer_name}.\n\nOrder Details:\n• Quantity: {cart_item["quantity"]}\n• Phone: {order.phone_number}\n• Delivery Address: {order.delivery_address}\n• Order ID: {order.order_id}',
                        item=item,
                        order=order,
                        order_item=order_item,
                    )

                Payment.objects.create(
                    order=order,
                    amount=total_amount,
                    phone_number=form.cleaned_data["phone_number"],
                    status="pending",
                )

            _clear_checkout_cart(request)
            _flag_browser_cart_clear(request)
            return redirect("initiate_payment", order_id=order.order_id)
    else:
        form = CheckoutForm(initial=_checkout_prefill_initial_data(request.user))

    return render(
        request,
        "checkout.html",
        {
            "form": form,
            "cart_items": cart_items,
            "total_amount": total_amount,
        },
    )


@login_required
def initiate_payment(request, order_id):
    """Initiate MPESA payment"""
    order = get_object_or_404(Order, order_id=order_id, buyer=request.user)

    if order.status not in ["pending", "failed"]:
        messages.error(request, "This order cannot be paid.")
        return redirect("orders_list")

    payment = order.payment
    clear_browser_cart = _consume_browser_cart_clear_flag(request)

    try:
        mpesa = create_mpesa_client()
        callback_url = mpesa.get_callback_url()
        result = mpesa.initiate_stk_push(
            phone_number=payment.phone_number,
            amount=int(payment.amount),
            order_id=order.order_id,
            callback_url=callback_url,
        )

        if "CheckoutRequestID" in result:
            payment.checkout_request_id = result["CheckoutRequestID"]
            payment.status = "initiated"
            payment.result_description = ""
            payment.save(update_fields=["checkout_request_id", "status", "result_description"])

            PaymentLog.objects.create(
                payment=payment,
                event="STK_PUSH_INITIATED",
                message=f"STK push initiated for order {order.order_id}",
                response_data=result,
            )

            order.status = "payment_initiated"
            order.save(update_fields=["status", "updated_at"])

            messages.success(request, f"Check your phone {payment.phone_number} for the payment prompt.")
            return render(
                request,
                "payment_pending.html",
                {
                    "order": order,
                    "payment": payment,
                    "clear_browser_cart": clear_browser_cart,
                },
            )

        error_msg = result.get("errorMessage") or result.get("ResponseDescription") or "Failed to initiate payment."
        PaymentLog.objects.create(
            payment=payment,
            event="STK_PUSH_FAILED",
            message=error_msg,
            response_data=result,
        )
        payment.status = "failed"
        payment.result_description = error_msg
        payment.save(update_fields=["status", "result_description"])
        order.status = "failed"
        order.save(update_fields=["status", "updated_at"])
        messages.error(request, error_msg)
        return render(
            request,
            "payment_failed.html",
            {
                "order": order,
                "payment": payment,
                "clear_browser_cart": clear_browser_cart,
            },
        )

    except MPESAConfigurationError as exc:
        error_message = str(exc)
        payment.status = "failed"
        payment.result_description = error_message
        payment.save(update_fields=["status", "result_description"])
        order.status = "failed"
        order.save(update_fields=["status", "updated_at"])
        PaymentLog.objects.create(
            payment=payment,
            event="STK_PUSH_CONFIG_ERROR",
            message=error_message,
            response_data={},
        )
        messages.error(request, error_message)
        return render(
            request,
            "payment_failed.html",
            {
                "order": order,
                "payment": payment,
                "clear_browser_cart": clear_browser_cart,
            },
        )

    except Exception as exc:
        error_message = str(exc)
        payment.status = "failed"
        payment.result_description = error_message
        payment.save(update_fields=["status", "result_description"])
        order.status = "failed"
        order.save(update_fields=["status", "updated_at"])
        PaymentLog.objects.create(
            payment=payment,
            event="STK_PUSH_ERROR",
            message=error_message,
            response_data={},
        )
        messages.error(request, f"Error initiating payment: {error_message}")
        return render(
            request,
            "payment_failed.html",
            {
                "order": order,
                "payment": payment,
                "clear_browser_cart": clear_browser_cart,
            },
        )


@csrf_exempt  # MPESA callback doesn't have CSRF token
def mpesa_callback(request):
    """MPESA payment callback handler"""
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Extract data from MPESA callback
        result_data = data.get('Body', {}).get('stkCallback', {})
        request_id = result_data.get('CheckoutRequestID')
        result_code = result_data.get('ResultCode')
        result_desc = result_data.get('ResultDesc', '')
        callback_metadata = result_data.get('CallbackMetadata', {})
        
        # Find payment by checkout request ID
        payment = Payment.objects.filter(checkout_request_id=request_id).first()
        
        if not payment:
            return JsonResponse({'success': False, 'message': 'Payment not found'}, status=404)
        
        order = payment.order
        
        # Log the callback
        PaymentLog.objects.create(
            payment=payment,
            event='CALLBACK_RECEIVED',
            message=result_desc,
            response_data=data
        )
        
        # Check result code
        if result_code == 0:
            # Payment successful
            items = callback_metadata.get('Item', [])
            mpesa_receipt = None
            
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
            
            payment.status = 'completed'
            payment.mpesa_receipt = mpesa_receipt
            payment.result_code = result_code
            payment.result_description = result_desc
            payment.completed_at = timezone.now()
            payment.save()
            
            order.status = 'paid'
            order.paid_at = timezone.now()
            order.save()
            
            PaymentLog.objects.create(
                payment=payment,
                event='PAYMENT_SUCCESSFUL',
                message=f"Payment successful. Receipt: {mpesa_receipt}",
                response_data=callback_metadata
            )
            
            # Send confirmation email (optional)
            # send_payment_confirmation_email(order)
            
            return JsonResponse({'success': True, 'message': 'Payment received'})
        else:
            # Payment failed
            payment.status = 'failed'
            payment.result_code = result_code
            payment.result_description = result_desc
            payment.save()
            
            order.status = 'failed'
            order.save()
            
            PaymentLog.objects.create(
                payment=payment,
                event='PAYMENT_FAILED',
                message=result_desc,
                response_data=data
            )
            
            return JsonResponse({'success': False, 'message': result_desc})
    
    except Exception as e:
        logger.error(f"Error processing MPESA callback: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
def payment_status(request, order_id):
    """Check payment status"""
    order = get_object_or_404(Order, order_id=order_id, buyer=request.user)
    payment = order.payment

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )
    if wants_json:
        return JsonResponse(_payment_status_payload(order, payment))

    return render(
        request,
        "payment_status.html",
        {
            "order": order,
            "payment": payment,
        },
    )


@login_required
def orders_list(request):
    """View user's orders"""
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items').order_by('-created_at')
    
    return render(request, 'orders_list.html', {
        'orders': orders,
    })


@login_required
def order_detail(request, order_id):
    """View order details"""
    order = get_object_or_404(Order, order_id=order_id, buyer=request.user)
    order_items = order.items.select_related('item', 'seller')
    
    return render(request, 'order_detail.html', {
        'order': order,
        'order_items': order_items,
    })


# ==================== Stock Management Views ====================

@login_required
def seller_stock_management(request):
    """View for seller to manage stock for their items"""
    if not _seller_required(request):
        raise Http404()
    
    items = Item.objects.filter(owner=request.user).select_related(
        "category"
    ).prefetch_related("images").order_by("-created_at")
    
    return render(request, "seller/stock_management.html", {
        "items": items,
    })


@login_required
def seller_item_stock_update(request, pk: int):
    """Add stock to an item"""
    if not _seller_required(request):
        raise Http404()
    
    item = get_object_or_404(Item, pk=pk, owner=request.user)
    
    if request.method == "POST":
        form = StockUpdateForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data["quantity"]
            item.stock += quantity
            item.save()
            
            messages.success(
                request,
                f"Stock updated! Added {quantity} units to {item.name}. Current stock: {item.stock}."
            )
            return redirect("seller_stock_management")
    else:
        form = StockUpdateForm()
    
    return render(request, "seller/item_stock_update.html", {
        "item": item,
        "form": form,
    })


# ==================== Seller Notifications Views ====================

@login_required
def seller_notifications(request):
    """View seller's notifications"""
    if not _seller_required(request):
        raise Http404()
    
    # Get unread count
    unread_count = SellerNotification.objects.filter(
        seller=request.user,
        is_read=False
    ).count()
    
    # Get all notifications with ordering
    notifications = SellerNotification.objects.filter(
        seller=request.user
    ).select_related(
        'item', 'order', 'order_item__item', 'order_item__seller'
    ).order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "seller/notifications.html", {
        "page_obj": page_obj,
        "unread_count": unread_count,
        "total_notifications": notifications.count(),
    })


@login_required
def seller_notification_mark_read(request, notification_id: int):
    """Mark a notification as read"""
    if not _seller_required(request):
        raise Http404()
    
    notification = get_object_or_404(
        SellerNotification,
        id=notification_id,
        seller=request.user
    )
    
    notification.mark_as_read()
    
    # Redirect to referring page or notifications page
    next_url = request.GET.get('next', 'seller_notifications')
    return redirect(next_url)


@login_required
def seller_notification_mark_all_read(request):
    """Mark all notifications as read"""
    if not _seller_required(request):
        raise Http404()
    
    if request.method == "POST":
        unread_notifications = SellerNotification.objects.filter(
            seller=request.user,
            is_read=False
        )
        
        for notification in unread_notifications:
            notification.mark_as_read()
        
        messages.success(request, f"Marked {unread_notifications.count()} notifications as read.")
    
    return redirect("seller_notifications")


# ==================== Helper Functions ====================

def _create_seller_notification(seller, notification_type, title, message, item=None, order=None, order_item=None):
    """Create a notification for a seller"""
    SellerNotification.objects.create(
        seller=seller,
        notification_type=notification_type,
        title=title,
        message=message,
        item=item,
        order=order,
        order_item=order_item,
    )
