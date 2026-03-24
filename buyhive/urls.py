from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('contact/', views.contact, name='contact'),
    path('book/', views.Buy_products, name='book'),
    path('login/', views.login_user, name='login'),
    path('register/', views.register_user, name='register'),
    path("logout/", views.logout_user, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("profiles/", views.profiles_search, name="profiles_search"),
    path("profiles/<str:username>/", views.profile_public, name="profile_public"),
    path("items/", views.items_public_list, name="items_public"),
    path("seller/items/", views.seller_items, name="seller_items"),
    path("seller/items/new/", views.seller_item_create, name="seller_item_create"),
    path("seller/items/<int:pk>/edit/", views.seller_item_update, name="seller_item_update"),
    path("seller/items/<int:pk>/delete/", views.seller_item_delete, name="seller_item_delete"),
    # Stock Management URLs
    path("seller/stock/", views.seller_stock_management, name="seller_stock_management"),
    path("seller/items/<int:pk>/stock/", views.seller_item_stock_update, name="seller_item_stock_update"),
    # Seller Notifications URLs
    path("seller/notifications/", views.seller_notifications, name="seller_notifications"),
    path("seller/notifications/<int:notification_id>/read/", views.seller_notification_mark_read, name="seller_notification_mark_read"),
    path("seller/notifications/mark-all-read/", views.seller_notification_mark_all_read, name="seller_notification_mark_all_read"),
    # Wishlist URLs
    path("wishlist/", views.wishlist_view, name="wishlist"),
    path("wishlist/toggle/<int:pk>/", views.toggle_wishlist, name="toggle_wishlist"),
    # Review URLs
    path("items/<int:item_id>/review/", views.item_review_create, name="item_review_create"),
    # Seller rating URLs
    path("sellers/<str:seller_username>/rate/", views.seller_rating_create, name="seller_rating_create"),
    # Recently viewed URLs
    path("items/<int:item_id>/track/", views.track_item_view, name="track_item_view"),
    path("recently-viewed/", views.recently_viewed_items, name="recently_viewed"),
    # Checkout and Payment URLs
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.orders_list, name="orders_list"),
    path("orders/<str:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<str:order_id>/payment/", views.initiate_payment, name="initiate_payment"),
    path("orders/<str:order_id>/status/", views.payment_status, name="payment_status"),
    path("api/mpesa/callback/", views.mpesa_callback, name="mpesa_callback"),
]
