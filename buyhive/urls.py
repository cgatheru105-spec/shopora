from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('book/', views.Buy_products, name='book'),
    path('login/', views.login_user, name='login'),
    path('register/', views.register_user, name='register'),
    path("logout/", views.logout_user, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("items/", views.items_public_list, name="items_public"),
    path("seller/items/", views.seller_items, name="seller_items"),
    path("seller/items/new/", views.seller_item_create, name="seller_item_create"),
    path("seller/items/<int:pk>/edit/", views.seller_item_update, name="seller_item_update"),
    path("seller/items/<int:pk>/delete/", views.seller_item_delete, name="seller_item_delete"),
]
