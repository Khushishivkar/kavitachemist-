from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
import json

from .models import Category, Supplier, Product, StockTransaction, ContactMessage
from .forms import (
    RegisterForm, LoginForm, ProductForm,
    CategoryForm, SupplierForm, StockTransactionForm, ContactForm
)


def is_admin(user):
    return user.is_authenticated and user.is_staff


# ─── PUBLIC PAGES ────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'index.html')


def about(request):
    return render(request, 'about.html')


def features(request):
    return render(request, 'features.html')


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your message has been sent! We will get back to you soon.')
            return redirect('contact')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})


# ─── AUTH PAGES ──────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            user.save()
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    user = request.user
    products = Product.objects.filter(created_by=user)
    categories = Category.objects.filter(created_by=user)
    suppliers = Supplier.objects.filter(created_by=user)
    transactions = StockTransaction.objects.filter(created_by=user).order_by('-created_at')[:10]

    total_products = products.count()
    low_stock = products.filter(quantity__lte=models_low_stock_value(products)).count()
    low_stock_products = [p for p in products if p.is_low_stock]
    expired_products = [p for p in products if p.is_expired]
    total_stock_value = sum(p.stock_value for p in products)

    # Category distribution for chart
    cat_data = []
    for cat in categories:
        count = products.filter(category=cat).count()
        if count > 0:
            cat_data.append({'name': cat.name, 'count': count})

    # Monthly stock-in vs stock-out for chart (last 6 months)
    from datetime import timedelta
    months = []
    stock_in_data = []
    stock_out_data = []
    today = timezone.now().date()
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1)
        months.append(month_start.strftime('%b'))
        s_in = StockTransaction.objects.filter(
            created_by=user, transaction_type='in',
            created_at__date__gte=month_start, created_at__date__lt=month_end
        ).aggregate(total=Sum('quantity'))['total'] or 0
        s_out = StockTransaction.objects.filter(
            created_by=user, transaction_type='out',
            created_at__date__gte=month_start, created_at__date__lt=month_end
        ).aggregate(total=Sum('quantity'))['total'] or 0
        stock_in_data.append(s_in)
        stock_out_data.append(abs(s_out))

    context = {
        'total_products': total_products,
        'total_categories': categories.count(),
        'total_suppliers': suppliers.count(),
        'low_stock_count': len(low_stock_products),
        'expired_count': len(expired_products),
        'total_stock_value': total_stock_value,
        'low_stock_products': low_stock_products[:5],
        'expired_products': expired_products[:5],
        'recent_transactions': transactions,
        'products': products.order_by('-created_at')[:8],
        'cat_data': json.dumps(cat_data),
        'months': json.dumps(months),
        'stock_in_data': json.dumps(stock_in_data),
        'stock_out_data': json.dumps(stock_out_data),
    }
    return render(request, 'dashboard.html', context)


def models_low_stock_value(products):
    return 10  # default threshold


# ─── PRODUCTS ────────────────────────────────────────────────────────────────

@login_required
def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.filter(created_by=request.user)
    if query:
        products = products.filter(Q(name__icontains=query) | Q(brand__icontains=query) | Q(batch_number__icontains=query))
    if category_id:
        products = products.filter(category_id=category_id)
    categories = Category.objects.filter(created_by=request.user)
    return render(request, 'products/list.html', {
        'products': products.order_by('-created_at'),
        'categories': categories,
        'query': query,
        'selected_category': category_id,
    })


@login_required
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.save()
            # Record initial stock
            if product.quantity > 0:
                StockTransaction.objects.create(
                    product=product,
                    transaction_type='in',
                    quantity=product.quantity,
                    notes='Initial stock entry',
                    created_by=request.user
                )
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('product_list')
    else:
        form = ProductForm(user=request.user)
    return render(request, 'products/form.html', {'form': form, 'title': 'Add Product', 'action': 'Add'})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product, user=request.user)
    return render(request, 'products/form.html', {'form': form, 'title': 'Edit Product', 'action': 'Update', 'product': product})


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, created_by=request.user)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully.')
        return redirect('product_list')
    return render(request, 'products/confirm_delete.html', {'product': product})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, created_by=request.user)
    transactions = product.transactions.order_by('-created_at')
    return render(request, 'products/detail.html', {'product': product, 'transactions': transactions})


# ─── STOCK TRANSACTIONS ──────────────────────────────────────────────────────

@login_required
def stock_transaction(request, pk):
    product = get_object_or_404(Product, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = StockTransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.product = product
            txn.created_by = request.user
            # Adjust quantity
            if txn.transaction_type == 'in':
                product.quantity += txn.quantity
            elif txn.transaction_type == 'out':
                if product.quantity < txn.quantity:
                    messages.error(request, 'Insufficient stock available.')
                    return redirect('product_detail', pk=pk)
                product.quantity -= txn.quantity
            else:
                product.quantity = txn.quantity
            product.save()
            txn.save()
            messages.success(request, 'Stock updated successfully!')
            return redirect('product_detail', pk=pk)
    else:
        form = StockTransactionForm()
    return render(request, 'products/transaction.html', {'form': form, 'product': product})


# ─── CATEGORIES ──────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.filter(created_by=request.user).annotate(product_count=Count('product'))
    return render(request, 'categories/list.html', {'categories': categories})


@login_required
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.created_by = request.user
            cat.save()
            messages.success(request, 'Category added!')
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'categories/form.html', {'form': form, 'title': 'Add Category'})


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated!')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'categories/form.html', {'form': form, 'title': 'Edit Category'})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, created_by=request.user)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('category_list')
    return render(request, 'categories/confirm_delete.html', {'category': category})


# ─── SUPPLIERS ───────────────────────────────────────────────────────────────

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.filter(created_by=request.user).annotate(product_count=Count('product'))
    return render(request, 'suppliers/list.html', {'suppliers': suppliers})


@login_required
def supplier_add(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            sup = form.save(commit=False)
            sup.created_by = request.user
            sup.save()
            messages.success(request, 'Supplier added!')
            return redirect('supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'suppliers/form.html', {'form': form, 'title': 'Add Supplier'})


@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated!')
            return redirect('supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'suppliers/form.html', {'form': form, 'title': 'Edit Supplier'})


@login_required
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk, created_by=request.user)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted.')
        return redirect('supplier_list')
    return render(request, 'suppliers/confirm_delete.html', {'supplier': supplier})


# ─── HIDDEN ADMIN PANEL ──────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_panel(request):
    all_users = User.objects.all().order_by('-date_joined')
    all_products = Product.objects.select_related('created_by', 'category').order_by('-created_at')
    all_contacts = ContactMessage.objects.order_by('-created_at')
    total_products = all_products.count()
    total_users = all_users.count()
    total_messages = all_contacts.filter(is_read=False).count()

    context = {
        'all_users': all_users,
        'all_products': all_products[:20],
        'all_contacts': all_contacts[:10],
        'total_products': total_products,
        'total_users': total_users,
        'unread_messages': total_messages,
    }
    return render(request, 'admin_panel.html', context)


@user_passes_test(is_admin, login_url='/login/')
def mark_message_read(request, pk):
    msg = get_object_or_404(ContactMessage, pk=pk)
    msg.is_read = True
    msg.save()
    return redirect('admin_panel')