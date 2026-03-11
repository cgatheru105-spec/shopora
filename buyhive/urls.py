from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('book/', views.Buy_products, name='book'),
    path('login/', views.login_user, name='login'),
    path('register/', views.register_user, name='register'),
]