from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import User, Profile, Product, CartItem, Order, Transaction, Follow, Message, StarsFeedback, Notification
from django.contrib import messages
from .forms import ProductForm, SignUpForm, LoginForm, CommentForm, StarsFeedbackForm, SearchForm, ProfileUpdateForm, MessageForm
from django.utils import timezone
import stripe
import uuid
import smtplib
from django.utils import translation
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.utils.translation import activate
from sendgrid.helpers.mail import Mail, Email, Content
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.conf import settings
from django.urls import reverse
from django.db.models import Q
from django.contrib.sites.shortcuts import get_current_site
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

stripe.api_key = settings.STRIPE_SECRET_KEY
account_activation_token = PasswordResetTokenGenerator()

def switch_language(request, language_code):
    if request.method == 'POST':
        language_code = request.POST.get('language')
        if language_code and translation.check_for_language(language_code):
            translation.activate(language_code)
            response = HttpResponseRedirect(request.POST.get('next', '/'))
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language_code)
            request.session['django_language'] = language_code
            request.LANGUAGE_CODE = language_code  # Set the LANGUAGE_CODE variable
            return response
    return HttpResponseBadRequest()

def stripe_checkout(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        product = get_object_or_404(Product, id=product_id)
        # Calculate the amount to charge (in cents)
        amount = int(product.price * 100)
        # Get the absolute URL of the product image
        image_url = request.build_absolute_uri(product.image.url) if product.image else ''
        # Create a Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.title,
                        'images': [request.build_absolute_uri(product.image.url)],
                        'description': product.description,  # Include description
                    },
                    'unit_amount': amount,
                },
                'quantity': quantity,
            }],
            metadata={
                'product_id': str(product.id),  # Include product ID
                'category': product.category,  # Include category
            },
            mode='payment',
            success_url=request.build_absolute_uri('/success/'),  # Replace with your success URL
            cancel_url=request.build_absolute_uri('/cancel/'),  # Replace with your cancel URL
        )

        return redirect(checkout_session.url)

    return redirect('home')

@login_required
def stripe_checkout_from_cart(request):
    if request.method == 'POST':
        # Retrieve the user's cart items
        cart_items = CartItem.objects.filter(user=request.user)

        # Create line items for each product in the cart
        line_items = []
        for cart_item in cart_items:
            line_item = {
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': cart_item.product.title,
                        'images': [request.build_absolute_uri(cart_item.product.image.url)],
                        'description': cart_item.product.description,
                    },
                    'unit_amount': int(cart_item.product.price * 100),  # Amount in cents
                },
                'quantity': cart_item.quantity,
            }
            line_items.append(line_item)

        # Create a Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri('/success-checkout/'),  # Replace with your success URL
            cancel_url=request.build_absolute_uri('/cancel/'),  # Replace with your cancel URL
        )

        # Do not clear the user's cart here

        print(f"Redirecting to: {checkout_session.url}")

        return redirect(checkout_session.url)

    # Handle the case where the request method is not POST
    print("Redirecting to home")
    return redirect('home')


def success_checkout(request):
    user_id = request.GET.get('user_id')
    user = get_object_or_404(Profile, id=user_id).user

    # Clear the user's cart after successful payment
    CartItem.objects.filter(user=user).delete()

    messages.success(request, "Payment successful! Your cart has been cleared.")

    return render(request, 'success.html')


def success(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.GET.get('quantity', 1))

    # Calculate the total amount
    total_amount = product.price * quantity

    # Get the seller's profile
    seller_profile = Profile.objects.get(user=product.seller)

    # Update the seller's balance
    seller_profile.balance += total_amount
    seller_profile.save()

    # Create a transaction record
    transaction = Transaction.objects.create(
        seller=product.seller,
        amount=total_amount,
    )

    messages.success(request, f"Payment successful! Your balance is now ${seller_profile.balance:.2f}.")
    
    return render(request, 'success.html', {'product': product})

def cancel(request):
    return render(request, 'cancel.html')    
def generate_verification_link(request, user):
    current_site = get_current_site(request)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    verification_link = f"{request.scheme}://{current_site.domain}/activate/{uid}/{token}/"
    return verification_link

def send_verification_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Verify your email'
    verification_link = generate_verification_link(request, user)
    message = f"Click the following link to verify your email: {verification_link}"
    email = EmailMultiAlternatives(mail_subject, message, from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email])
    email.send()

def verification_email_sent(request):
    user = request.user
    return render(request, 'auth/email_verification_sent.html', {'verification_sent': True, 'user': user})

def verification_email_resend(request):
    user = request.user
    send_verification_email(request, user)
    return render(request, 'auth/email_verification_sent.html', {'verification_sent': True, 'user': user})

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # User is not active until they verify their email
            user.save()
            Profile.objects.create(user=user)

            send_verification_email(request, user)

            # Redirect the user to the verification sent page
            return redirect('verification_email_sent')
    else:
        form = SignUpForm()
    return render(request, 'auth/signup.html', {'form': form, 'LANGUAGES': settings.LANGUAGES})

def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return render(request, 'auth/account_activated.html')
    else:
        return render(request, 'auth/email_verification_sent.html')
def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form, 'LANGUAGES': settings.LANGUAGES})

def forgot_password(request):
    if request.method == 'POST': 
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            associated_users = User.objects.filter(email=email)
            
            if associated_users.exists():
                for user in associated_users:
                    # Generate reset password token
                    token = default_token_generator.make_token(user)
                    
                    # Build reset password URL
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    reset_password_url = reverse('reset_password', kwargs={'uidb64': uid, 'token': token})
                    reset_password_url = request.build_absolute_uri(reset_password_url)
                    
                    # Render email template
                    mail_subject = 'Reset your password'
                    message = render_to_string('auth/reset_password_email.html', {
                        'user': user,
                        'reset_password_url': reset_password_url,
                    })
                    
                    # Send email
                    send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [email])
                
                messages.success(request, 'A password reset link has been sent to your email.')
            else:
                messages.error(request, 'No user associated with this email.')
            
            return redirect('forgot_password')
    else:
        form = PasswordResetForm()
    
    return render(request, 'auth/forgot_password.html', {'form': form})


def reset_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your password has been reset successfully.')
                return redirect('login')
        else:
            form = SetPasswordForm(user)
        
        return render(request, 'auth/reset_password.html', {'form': form, 'uidb64': uidb64, 'token': token})
    else:
        messages.error(request, 'Invalid reset password link.')
        return redirect('login')

def user_logout(request):
    logout(request)
    messages.success(request, 'Logout successful.')
    return redirect('home')

def home(request, product_id=None):
    if product_id is not None:
        product = get_object_or_404(Product, id=product_id)
    else:
        product = None

    # Retrieve all products and order by created_at descending
    products = Product.objects.all().order_by('-created_at')
    search_form = SearchForm()
    # Create forms for comment and stars feedback
    form_comment = CommentForm(initial={'product': product_id})
    form_stars_feedback = StarsFeedbackForm(initial={'product': product_id})
    category_choices = Product.CATEGORY_CHOICES
    # Filter products based on category
    category_filter = request.GET.get('category')
    if category_filter:
        products = products.filter(category=category_filter)

    # Filter products based on date
    date_filter = request.GET.get('date')
    if date_filter:
        products = products.filter(created_at__date=date_filter)
    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user, product_id__in=products.values('id'))
        cart_items_ids = set(cart_item.product_id for cart_item in cart_items)
    else:
        cart_items_ids = set()

    # Set the number of products to display per page
    products_per_page = 12

    # Paginate the products
    paginator = Paginator(products, products_per_page)
    page = request.GET.get('page')

    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        # If the page parameter is not an integer, deliver the first page.
        products = paginator.page(1)
    except EmptyPage:
        # If the page is out of range (e.g., 9999), deliver the last page of results.
        products = paginator.page(paginator.num_pages)

    # Filter products based on price
    price_filter = request.GET.get('price')
    if price_filter:
        # Assuming price_filter is a range, e.g., "0-50"
        min_price, max_price = map(int, price_filter.split('-'))
        products = products.filter(price__range=(min_price, max_price))
    if request.method == 'POST':
        # Handle comment creation
        if 'comment' in request.POST:
            form_comment = CommentForm(request.POST)
            if form_comment.is_valid():
                comment = form_comment.save(commit=False)
                comment.author = request.user
                product_id = request.POST.get('product_id')
                if product_id:
                    product = get_object_or_404(Product, id=product_id)
                comment.product = product
                comment.created_at = timezone.now()
                comment.save()
                return redirect('show_product', product_id=request.POST.get('product_id'))

        # Handle stars feedback creation
        elif 'stars' in request.POST:
            form_stars_feedback = StarsFeedbackForm(request.POST)
            if form_stars_feedback.is_valid():
                stars_feedback = form_stars_feedback.save(commit=False)
                stars_feedback.author = request.user
                product_id = request.POST.get('product_id')
                if product_id:
                    product = get_object_or_404(Product, id=product_id)
                stars_feedback.product = product
                stars_feedback.created_at = timezone.now()
                stars_feedback.save()
                return redirect('show_product', product_id=request.POST.get('product_id'))
    # Get notifications for current user
    # Check if the user is authenticated
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        notifications = None
        unread_notifications = None
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    if unread_notifications:  # Check if unread_notifications is not None
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            notification.is_read = True
            notification.save()
    return render(request, 'home.html', {'form_comment': form_comment, 'search_form': search_form, 'category_choices': category_choices, 'form_stars_feedback': form_stars_feedback, 'products': products, 'cart_items_ids': cart_items_ids, 'notifications': notifications, 'unread_notifications': unread_notifications, 'LANGUAGES': settings.LANGUAGES})
             

def search(request):
    # Get notifications for current user
    # notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
    # unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    search_form = SearchForm()
    users = []
    products = []
    if 'search' in request.POST:
        search_form = SearchForm(request.POST)
        if search_form.is_valid():
            query = search_form.cleaned_data['query']
            users = User.objects.filter(username__icontains=query)
            products = Product.objects.filter(title__icontains=query) 
    # Check if the user is authenticated
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        notifications = None
        unread_notifications = None
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    if unread_notifications:  # Check if unread_notifications is not None
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            notification.is_read = True
            notification.save()                  
    return render(request, 'results_search.html', {'users': users, 'products': products, 'search_form': search_form, 'notifications': notifications, 'unread_notifications': unread_notifications, 'LANGUAGES': settings.LANGUAGES})

def follow_user(request, username):
    user = get_object_or_404(User, username=username)

    if request.user.is_authenticated:
        following = Follow.objects.filter(follower=request.user, following=user)
        if not following.exists():
            # create a new follow object
            Follow.objects.create(follower=request.user, following=user)
    return redirect('profile', username=user.username)

def unfollow_user(request, username):
    user = get_object_or_404(User, username=username)

    if request.user.is_authenticated:
        following = Follow.objects.filter(follower=request.user, following=user)
        if following.exists():
            # delete the existing follow object
            following.delete()
    return redirect('profile', username=user.username)

@login_required
def profile(request, username):
    User = get_user_model()
    user = get_object_or_404(User, username=username)

    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)

    transactions = Transaction.objects.filter(seller=request.user).order_by('-timestamp')
    products = Product.objects.filter(seller=user)
    orders = Order.objects.filter(user=user)
    cart_items = CartItem.objects.filter(product__seller=user)
    category_choices = Product.CATEGORY_CHOICES

    total_sales = sum(order.total_amount for order in orders)
    total_products_sold = sum(item.quantity for order in orders for item in order.items.all())
    total_inventory = sum(item.quantity for item in cart_items)

    # Set the number of products to display per page
    products_per_page = 12

    # Paginate the products
    paginator = Paginator(products, products_per_page)
    page = request.GET.get('page')

    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        # If the page parameter is not an integer, deliver the first page.
        products = paginator.page(1)
    except EmptyPage:
        # If the page is out of range (e.g., 9999), deliver the last page of results.
        products = paginator.page(paginator.num_pages)

    performance_metrics = {
        'Total Sales': total_sales,
        'Total Products Sold': total_products_sold,
        'Total Inventory': total_inventory,
    }

    
    is_following = False
    following = Follow.objects.filter(follower=request.user, following=user)
    if following.exists():
        is_following = True
    # Check if the user is authenticated
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        notifications = None
        unread_notifications = None
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    if unread_notifications:  # Check if unread_notifications is not None
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            notification.is_read = True
            notification.save()    
    context = {
        'user': user,
        'profile': profile,
        'transactions': transactions,
        'products': products,
        'orders': orders,
        'category_choices': category_choices,
        'cart_items': cart_items,
        'performance_metrics': performance_metrics,
        'is_following': is_following,
        'notifications': notifications,
        'unread_notifications': unread_notifications,
        'LANGUAGES': settings.LANGUAGES,
    }

    if request.user.is_authenticated:
        if request.user.username == username:  # check if the user is visiting their own profile
            if request.method == 'POST':
                form_profile = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
                if form_profile.is_valid():
                    form_profile.save()
                    messages.success(request, ('Your Profile Was successfully updated'))
                else:
                    form_profile = ProfileUpdateForm(instance=request.user.profile)
            return render(request, 'profile.html', context)
        else:  # the user is visiting someone else's profile
            following = Follow.objects.filter(follower=request.user, following=user)
            if following.exists():
                is_following = True            
            return render(request, 'public_profile.html', {'user': user, 'is_following': is_following})

    else:
        return render(request, 'public_profile.html', context)

@login_required
def withdraw(request):
    profile = Profile.objects.get(user=request.user)

    if profile.balance >= 100:
        # Deduct $5 for withdrawal fee
        withdrawal_amount = profile.balance - 5
        profile.balance = 0  # Set balance to zero after withdrawal
        profile.save()

        # Create a transaction record
        Transaction.objects.create(seller=request.user, amount=withdrawal_amount)

    return redirect('profile')    
@login_required
def edit_profile(request):
    user_profile = get_object_or_404(Profile, user=request.user)

    if request.method == 'POST':
        # Handle form submission with updated data
        # Your code here to update user profile fields
        return redirect('profile')

    return render(request, 'edit_profile.html', {'profile': user_profile})

@login_required
def sell_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            return redirect('home')
    else:
        form = ProductForm()

    return render(request, 'sell_product.html', {'form': form})


# def cart(request):
#     cart_items = CartItem.objects.filter(user=request.user)
#     total_price = sum(item.product.price * item.quantity for item in cart_items)
#     return render(request, 'cart.html', {'cart_items': cart_items, 'total_price': total_price})


# def add_to_cart(request, product_id):
#     product = get_object_or_404(Product, pk=product_id)
#     cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
#     if not created:
#         cart_item.quantity += 1
#         cart_item.save()
#     return redirect('cart')


# def remove_from_cart(request, cart_item_id):
#     cart_item = get_object_or_404(CartItem, pk=cart_item_id, user=request.user)
#     cart_item.delete()
#     return redirect('cart')

def cart(request):
    # Check if the user is authenticated
    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user)
        total_price = sum(item.product.price * item.quantity for item in cart_items)
        return render(request, 'cart.html', {'cart_items': cart_items, 'total_price': total_price})
    else:
        # Handle the case when the user is not authenticated
        return render(request, 'cart.html', {'cart_items': [], 'total_price': 0})

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    # Check if the user is authenticated
    if request.user.is_authenticated:
        cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
        if not created:
            cart_item.quantity += 1
            cart_item.save()
        return redirect('cart')
    else:
        # Handle the case when the user is not authenticated
        return redirect('login')  # Redirect to login page or handle as needed

def remove_from_cart(request, product_id):
    # Check if the user is authenticated
    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, pk=product_id, user=request.user)
        cart_item.delete()
        return redirect('cart')
    else:
        # Handle the case when the user is not authenticated
        return redirect('login')  # Redirect to login page or handle as needed
@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        # Your code here to handle the checkout process, create an order, etc.
        # Remember to clear the user's cart after successful checkout
        return redirect('order_confirmation')
    # Check if the user is authenticated
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        notifications = None
        unread_notifications = None
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    if unread_notifications:  # Check if unread_notifications is not None
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            notification.is_read = True
            notification.save()
    return render(request, 'checkout.html', {'cart_items': cart_items, 'total_price': total_price, 'notifications': notifications, 'unread_notifications': unread_notifications})

@login_required
def order_confirmation(request):
    return render(request, 'order_confirmation.html')

def show_product(request, product_id):
    # Get the product
    product = get_object_or_404(Product, id=product_id)
    # Retrieve all comments for the post with the given post_id
    comments = product.comments.all()
    # Retrieve all products (or filter as needed)
    products = Product.objects.all()
    # Retrieve all emoji reactions for the post with the given post_id
    stars_feedback = product.stars_feedback.all()
    # Create forms for comment and stars feedback
    form_comment = CommentForm(initial={'product': product_id})
    form_stars_feedback = StarsFeedbackForm(initial={'product': product_id})
    # Assuming you have an Order related to the product
    # order = Order.objects.filter(items__product=product).first()
    if request.method == 'POST':
        # Handle comment creation
        if 'comment' in request.POST:
            form_comment = CommentForm(request.POST)
            if form_comment.is_valid():
                comment = form_comment.save(commit=False)
                comment.author = request.user
                product_id = request.POST.get('product_id')
                if product_id:
                    product = get_object_or_404(Product, id=product_id)
                comment.product = product
                comment.created_at = timezone.now()
                comment.save()
                return redirect('show_product', product_id=request.POST.get('product_id'))

        # Handle stars feedback creation
        elif 'stars' in request.POST:
            form_stars_feedback = StarsFeedbackForm(request.POST)
            if form_stars_feedback.is_valid():
                stars_feedback = form_stars_feedback.save(commit=False)
                stars_feedback.author = request.user
                product_id = request.POST.get('product_id')
                if product_id:
                    product = get_object_or_404(Product, id=product_id)
                stars_feedback.product = product
                stars_feedback.created_at = timezone.now()
                stars_feedback.save()
                return redirect('show_product', product_id=request.POST.get('product_id'))
    # Check if the user is authenticated
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    else:
        notifications = None
        unread_notifications = None
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    if unread_notifications:  # Check if unread_notifications is not None
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            notification.is_read = True
            notification.save()
    return render(request, 'show_product.html', {'product': product, 'comments': comments, 'stars_feedback': stars_feedback, 'form_comment': form_comment, 'form_stars_feedback': form_stars_feedback, 'notifications': notifications, 'unread_notifications': unread_notifications, 'LANGUAGES': settings.LANGUAGES})
@login_required
def update_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save(commit=False)
            product.author = request.user
            product.save()
            if request.is_ajax():
                return JsonResponse({'success': True})
            else:
                messages.success(request, 'Post updated successfully!')
                return redirect('profile', username=request.user)
        else:
            if request.is_ajax():
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ProductForm(instance=product)
        # Get notifications for current user
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
        
        # Separate notifications by type
        message_notifications = []
        product_notifications = []
        stars_feedback_notifications = []
        join_request_notifications = []
        for notification in unread_notifications:
            if notification.message:
                message_notifications.append(notification)
            elif notification.product:
                product_notifications.append(notification)
            elif notification.stars_feedback:
                stars_feedback_notifications.append(notification)
            elif notification.comment:
                comment_notifications.append(notification)
            elif notification.join_request:
                join_request_notifications.append(notification)

            notification.is_read = True
            notification.save()
        context = {'form': form, 'unread_notifications': unread_notifications, 'LANGUAGES': settings.LANGUAGES}
        return render(request, 'modals/edit_product.html', context)
@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)

    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Your post has been deleted!')
        return redirect('profile', username=request.user)

    data = {
        'product': product,
    }

    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        html = render_to_string('delete_product_modal.html', data, request=request)
        return JsonResponse({'html': html})    
    return render(request, 'modals/delete_product.html', data) 
@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)

    if request.method == 'POST':
        comment_form = CommentForm(request.POST, instance=comment)
        if comment_form.is_valid():
            comment_form.save()
            return redirect('show_product', product_id=comment.product.id)
    else:
        comment_form = CommentForm(instance=comment)

    return render(request, 'edit_comment.html', {'comment_form': comment_form})

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, author=request.user)
    product_id = comment.product.id
    comment.delete()
    return redirect('show_product', product_id=product_id)

@login_required
def add_stars_feedback(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.method == 'POST':
        stars_feedback_form = StarsFeedbackForm(request.POST)
        if stars_feedback_form.is_valid():
            new_stars_feedback = stars_feedback_form.save(commit=False)
            new_stars_feedback.product = product
            new_stars_feedback.author = request.user
            new_stars_feedback.save()
            return redirect('show_product', product_id=product_id)
    else:
        stars_feedback_form = StarsFeedbackForm()

    return render(request, 'add_stars_feedback.html', {'product': product, 'stars_feedback_form': stars_feedback_form})

@login_required
def edit_stars_feedback(request, stars_feedback_id):
    stars_feedback = get_object_or_404(StarsFeedback, pk=stars_feedback_id, author=request.user)

    if request.method == 'POST':
        stars_feedback_form = StarsFeedbackForm(request.POST, instance=stars_feedback)
        if stars_feedback_form.is_valid():
            stars_feedback_form.save()
            return redirect('show_product', product_id=stars_feedback.product.id)
    else:
        stars_feedback_form = StarsFeedbackForm(instance=stars_feedback)

    return render(request, 'edit_stars_feedback.html', {'stars_feedback_form': stars_feedback_form})

@login_required
def delete_stars_feedback(request, stars_feedback_id):
    stars_feedback = get_object_or_404(StarsFeedback, pk=stars_feedback_id, author=request.user)
    product_id = stars_feedback.product.id
    stars_feedback.delete()
    return redirect('show_product', product_id=product_id)


@login_required
def orders(request, username, order_id=None):
    User = get_user_model()
    user = get_object_or_404(User, username=username)

    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)

    transactions = Transaction.objects.filter(seller=request.user).order_by('-timestamp')
    products = Product.objects.filter(seller=user)
    orders = Order.objects.filter(user=user)
    cart_items = CartItem.objects.filter(product__seller=user)
    category_choices = Product.CATEGORY_CHOICES

    total_sales = sum(order.total_amount for order in orders)
    total_products_sold = sum(item.quantity for order in orders for item in order.items.all())
    total_inventory = sum(item.quantity for item in cart_items)

    performance_metrics = {
        'Total Sales': total_sales,
        'Total Products Sold': total_products_sold,
        'Total Inventory': total_inventory,
    }
    # Fetch orders for each status
    confirmed_orders = Order.objects.filter(status='confirmed')
    pending_orders = Order.objects.filter(status='pending')
    shipped_orders = Order.objects.filter(status='shipped')
    delivered_orders = Order.objects.filter(status='delivered')
    canceled_orders = Order.objects.filter(status='canceled')

    # Other logic and context data as needed
    # Fetch orders for shippers and delivery drivers
    shipper_orders = Order.objects.filter(user=user, status='shipped')  # Update with your logic
    delivery_driver_orders = Order.objects.filter(user=user, status='delivered')  # Update with your logic
    # Get notifications for current user
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    join_request_notifications = []
    for notification in unread_notifications:
        if notification.message:
            message_notifications.append(notification)
        elif notification.product:
            product_notifications.append(notification)
        elif notification.stars_feedback:
            stars_feedback_notifications.append(notification)
        elif notification.comment:
            comment_notifications.append(notification)
        elif notification.join_request:
            join_request_notifications.append(notification)

        notification.is_read = True
        notification.save()
    return render(request, 'orders.html', {
        'user': user,
        'profile': profile,
        'transactions': transactions,
        'products': products,
        'orders': orders,
        'category_choices': category_choices,
        'cart_items': cart_items,
        'performance_metrics': performance_metrics,
        'messages': messages.get_messages(request),
        'confirmed_orders': confirmed_orders,
        'pending_orders': pending_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'canceled_orders': canceled_orders,
        'shipper_orders': shipper_orders,
        'delivery_driver_orders': delivery_driver_orders,
        'order_id': order_id,
        'notifications': notifications,
        'unread_notifications': unread_notifications,
        'LANGUAGES': settings.LANGUAGES,
    })

def cod_checkout(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        quantity = request.POST.get('quantity', 1)

        product = Product.objects.get(id=product_id)
        total_amount = product.price * int(quantity)

        # Check if the user is authenticated
        if request.user.is_authenticated:
            # Create a new order with Cash on Delivery (COD) as the payment method for authenticated users
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                status='pending',
                payment_method='cod',
                cod_selected=True,
            )
        else:
            # For non-authenticated users, handle order creation differently (customize as needed)
            # You should have a user with username 'anonymous'
            order = Order.objects.create(
                user=None,
                total_amount=total_amount,
                status='pending',
                payment_method='cod',
                cod_selected=True,
            )

        # Add the product to the order's items
        CartItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            user=request.user if request.user.is_authenticated else None,
        )

        # Display modal for capturing customer information
        return render(request, 'checkout.html', {'order_id': order.id})

    # Handle the case when the request method is not POST (optional)
    messages.error(request, 'Invalid request. Please try again.')
    return redirect('home')  

def confirm_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Your logic to confirm the order goes here
    order.status = 'confirmed'
    order.save()

    messages.success(request, 'Order confirmed successfully.')
    return redirect('orders')  # Adjust the URL name based on your application

def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Your logic to cancel the order goes here
    order.status = 'canceled'
    order.save()

    messages.success(request, 'Order canceled successfully.')
    return redirect('orders')         

def save_customer_info(request):
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        customer_name = request.POST.get('customer_name')
        customer_address = request.POST.get('customer_address')
        customer_city = request.POST.get('customer_city')
        customer_phone = request.POST.get('customer_phone')

        # Update the order with customer information
        order = Order.objects.get(id=order_id)
        order.customer_name = customer_name
        order.customer_address = customer_address
        order.customer_city = customer_city
        order.customer_phone = customer_phone
        order.save()

        messages.success(request, 'Thanks for choosing Cash on Delivery! Your order is in process, and we are working hard to get it to you soon.')
        return redirect('home')

    messages.error(request, 'Invalid request. Please try again.')
    return redirect('home')

# Message and Notification

@login_required
def message_thread(request, username):
    unread_messages = Message.objects.filter(recipient=request.user, is_read=False)
    recipient = get_object_or_404(get_user_model(), username=username)
    # Get all messages sent by the current user to the recipient and all messages received by the current user from the recipient
    messages_sent = Message.objects.filter(sender=request.user, recipient=recipient)
    messages_received = Message.objects.filter(sender=recipient, recipient=request.user)
    
    # Merge the sent and received messages into one queryset and order by timestamp
    conversations = (messages_sent | messages_received).order_by('timestamp')


    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.recipient = recipient
            message.save()

            # Check if a notification already exists for the recipient and the message
            existing_notification = Notification.objects.filter(
                Q(user=recipient) & Q(message=message)
            ).first()

            if existing_notification:
                existing_notification.timestamp = timezone.now()
                existing_notification.is_read = False
                existing_notification.save()
            else:
                Notification.objects.create(
                    user=recipient,
                    product=None, 
                    message=message,
                    timestamp=timezone.now(),
                    is_read=False
                )

            # Send real-time message to recipient
            channel_layer = get_channel_layer()
            if request.user.profile.image:
                sender_image = str(request.user.profile.image.url)
            else:
                sender_image = None

            async_to_sync(channel_layer.group_send)(
                f"chat_{recipient.username}",
                {
                    "type": "chat_message",
                    "message": {
                        "sender": request.user.username,
                        "sender_image": sender_image,
                        "recipient": recipient.username,
                        "content": message.content,
                        "timestamp": str(timezone.now())
                    }
                }
            )


            return redirect('message_thread', username=username)
    else:
        form = MessageForm()

    # Get notifications for current user
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    join_request_notifications = []
    for notification in unread_notifications:
        if notification.message:
            message_notifications.append(notification)
        elif notification.product:
            product_notifications.append(notification)
        elif notification.stars_feedback:
            stars_feedback_notifications.append(notification)
        elif notification.comment:
            comment_notifications.append(notification)
        elif notification.join_request:
            join_request_notifications.append(notification)

        notification.is_read = True
        notification.save()
    # Get sender user object
    sender = User.objects.get(username=request.user.username)
    return render(request, 'chat/message_thread.html', {'unread_messages': unread_messages, 'recipient': recipient, 'messages': conversations, 'form': form, 'sender': sender, 'notifications': notifications, 'messages_received':messages_received, 'unread_notifications': unread_notifications, 'LANGUAGES': settings.LANGUAGES})

@login_required
def notification(request):
    # Get unread notifications for the current user
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')

        # Mark all notifications as read
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)

     # Separate notifications by type
    message_notifications = []
    post_notifications = []
    group_message_notifications = []
    group_post_notifications = []
    emoji_reaction_notifications = []
    comment_notifications = []
    emoji_reaction_group_notifications = []
    comment_group_notifications = []
    join_request_notifications = []
    for notification in unread_notifications:
        if notification.message:
            message_notifications.append(notification)
        elif notification.post:
            post_notifications.append(notification)
        elif notification.group_post:
            group_post_notifications.append(notification)     
        elif notification.group_message:
            group_message_notifications.append(notification)
        elif notification.emoji_reaction:
            emoji_reaction_notifications.append(notification)
        elif notification.comment:
            comment_notifications.append(notification)
        elif notification.emoji_reaction_group:
            emoji_reaction_group_notifications.append(notification)
        elif notification.comment_group:
            comment_group_notifications.append(notification)
        elif notification.join_request:
            join_request_notifications.append(notification)

        notification.is_read = True
        notification.save()

    # Get the total count of unread notifications
    unread_count = len(unread_notifications)

    return render(request, 'notifications.html', {
        'message_notifications': message_notifications,
        'post_notifications': product_notifications,
        'emoji_reaction_notifications': stars_feedback_notifications,
        'comment_notifications': comment_notifications,
        'notifications': notifications,
        'unread_notifications': unread_notifications,
        'LANGUAGES': settings.LANGUAGES,
    })
@login_required
def saved_conversations(request):
    # Get notifications for current user
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    search_form = SearchForm()
    users = []
    if request.GET.get('search'):
        search_form = SearchForm(request.GET)
        if search_form.is_valid():
            query = search_form.cleaned_data['query']
            users = User.objects.filter(username__icontains=query)
            conversations = []
            for user in users:
                conversation = Message.objects.filter(Q(sender=request.user, recipient=user) | Q(sender=user, recipient=request.user)).order_by('timestamp').last()
                if conversation:
                    conversations.append(conversation)
            return render(request, 'chat/saved_conversations.html', {
                'users': users,
                'conversations': conversations,
                'search_form': search_form,
                'notifications': notifications,
                'unread_notifications': unread_notifications,
            })
    
    conversations = Message.objects.filter(Q(sender=request.user) | Q(recipient=request.user)).order_by('recipient', '-timestamp').distinct('recipient')
    search_form = SearchForm()
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')

        # Mark all notifications as read
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)

     # Separate notifications by type
    message_notifications = []
    post_notifications = []
    group_message_notifications = []
    group_post_notifications = []
    emoji_reaction_notifications = []
    comment_notifications = []
    emoji_reaction_group_notifications = []
    comment_group_notifications = []
    join_request_notifications = []
    for notification in unread_notifications:
        if notification.message:
            message_notifications.append(notification)
        elif notification.post:
            post_notifications.append(notification)
        elif notification.group_post:
            group_post_notifications.append(notification)     
        elif notification.group_message:
            group_message_notifications.append(notification)
        elif notification.emoji_reaction:
            emoji_reaction_notifications.append(notification)
        elif notification.comment:
            comment_notifications.append(notification)
        elif notification.emoji_reaction_group:
            emoji_reaction_group_notifications.append(notification)
        elif notification.comment_group:
            comment_group_notifications.append(notification)
        elif notification.join_request:
            join_request_notifications.append(notification)

        notification.is_read = True
        notification.save()
    return render(request, 'chat/saved_conversations.html', {
        'users': User.objects.none(),
        'conversations': conversations,
        'search_form': search_form,
        'notifications': notifications,
        'unread_notifications': unread_notifications,
        'LANGUAGES': settings.LANGUAGES,
    }) 

# Contact Us and Terms of Use and Mark Notification as Read

def contact_us(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        message = request.POST['message']

        # Create a multi-part message and set the headers
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = settings.ADMIN_EMAIL
        msg['Subject'] = f'New message from {name}'

        # Add body to the email
        msg.attach(MIMEText(message, 'plain'))

        # Connect to the Google SMTP server
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()

            # Login to the SMTP server
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)

            # Send the email
            smtp.sendmail(email, settings.ADMIN_EMAIL, msg.as_string())

        messages.success(request, 'Thank you for contacting us! We will get back to you as soon as possible.')
        return redirect('contact_us')
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
        notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')[:10]
    else:
        unread_notifications = []
    # Mark all notifications as read
        notifications = []
    # Separate notifications by type
    message_notifications = []
    product_notifications = []
    stars_feedback_notifications = []
    comment_notifications = []
    for notification in unread_notifications:
        if notification.message:
            message_notifications.append(notification)
        elif notification.post:
            product_notifications.append(notification)
        elif notification.stars_feedback:
            stars_feedback_notifications.append(notification)
        elif notification.comment:
            comment_notifications.append(notification)
        notification.is_read = True
        notification.save()   
    return render(request, 'about/contact_us.html', {'unread_notifications': unread_notifications, 'notifications': notifications, 'message_notifications': message_notifications, 'product_notifications': product_notifications, 'LANGUAGES': settings.LANGUAGES})
def terms_of_service(request):
    return render(request, 'about/terms_of_service.html')
def privacy_policy(request):
    return render(request, 'about/privacy_policy.html')
def about_us(request):
    return render(request, 'about/about_us.html')    
def mark_notification_as_read(request):
    notification_id = request.GET.get('notification_id')
    notification = Notification.objects.filter(id=notification_id, user=request.user).first()
    if notification:
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True, 'redirect_url': get_redirect_url(notification)})
    else:
        return JsonResponse({'success': False})