from django.shortcuts import render
from urllib import request

# Create your views here.
def index(request):
    return render(request, 'index.html')

def Buy_products(request):
    return render(request, 'book.html')

def login_user(request):
    return render(request, 'login.html')

def register_user(request):
    return render(request, 'register.html')