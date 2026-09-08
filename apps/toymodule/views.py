import logging
from django.shortcuts import render, redirect
from .models import Product
from .forms import AddProductForm, AddUserForm, LoginForm
from django.contrib.auth.models import auth
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, connection
from django.http import HttpResponse

#logger = logging.getLogger(__name__)

def healthz(request):
    """Health check for the host (Render polls this after every deploy).

    Touches the database rather than just returning 200, so an instance that
    boots but cannot reach Supabase is reported unhealthy instead of serving
    500s. Exempt from the HTTPS redirect via SECURE_REDIRECT_EXEMPT: the probe
    is internal to the platform and arrives without X-Forwarded-Proto, so
    otherwise it would only ever see a 301.
    """
    try:
        connection.ensure_connection()
    except DatabaseError:
        return HttpResponse("database unavailable\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")

def index(request):
    # render the appropriate template for this request
    products = Product.objects.filter().order_by('pname')
    return render(request, 'toymodule/index.html', {'products':products})

def login(request):
    form = LoginForm()
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth.login(request, user)
                return redirect('dashboard')
        
    return render(request, 'toymodule/login.html', {'loginform': form})

def logout(request):
    auth.logout(request)
    return redirect("index")

def register(request):
    form = AddUserForm()
    if request.method == "POST":
        form = AddUserForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, 'toymodule/registerSuccess.html')
    
    return render(request, 'toymodule/register.html', {"registerform":form})

@login_required(login_url='login')
def addProduct(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES)
        image = request.FILES.get('pimage')
        print(image)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = AddProductForm()
    return render(request, 'toymodule/addProduct.html', {"form":form})

@login_required(login_url='login')
def dashboard(request):
    return render(request, 'toymodule/dashboard.html')

@login_required(login_url='login')
def accountInfo(request):
    user = request.user
    email = user.email
    username = user.username
    context = {"email":email,"username":username}
    return render(request, 'toymodule/accountInfo.html', context=context)


def babyToys(request):
    products = Product.objects.filter(pcategory__exact = 'Baby Toys').order_by('pname')
    return render(request, 'toymodule/babyToys.html', {'products':products})

def outdoors(request):
    products = Product.objects.filter(pcategory__exact = 'Outdoors').order_by('pname')
    return render(request, 'toymodule/outdoors.html', {'products':products})

def dollsAndPlaysets(request):
    products = Product.objects.filter(pcategory__exact = 'Dolls and Playsets').order_by('pname')
    return render(request, 'toymodule/dollsAndPlaysets.html', {'products':products})

def carsAndBikes(request):
    products = Product.objects.filter(pcategory__exact = 'Cars and Bikes').order_by('pname')
    return render(request, 'toymodule/carsAndBikes.html', {'products':products})
