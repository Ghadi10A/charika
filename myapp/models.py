from django.contrib.auth.models import AbstractUser, User, Group, Permission
from django.db import models
from django.urls import reverse
import emojis
import datetime
from location_field.forms.plain import PlainLocationField
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    groups = models.ManyToManyField(Group, related_name='custom_groups')
    user_permissions = models.ManyToManyField(Permission, related_name='custom_permissions')
    is_active = models.BooleanField(default=False)
    is_connected = models.BooleanField(default=False)

from django.contrib.auth.models import User

class Profile(models.Model):
    SELLER = 'seller'
    WHOLESALE_SELLER = 'wholesale_seller'
    SHIPPER = 'shipper'
    DELIVERY_DRIVER = 'delivery_driver'

    PROFILE_TYPE_CHOICES = [
        (SELLER, 'Seller'),
        (WHOLESALE_SELLER, 'Wholesale Seller'),
        (SHIPPER, 'Shipper'),
        (DELIVERY_DRIVER, 'Delivery Driver'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='media/profile_pics', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=30, blank=True)
    stripe_customer_id = models.CharField(max_length=50, blank=True, null=True)
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPE_CHOICES, default=SELLER)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    def __str__(self):
        return self.user.username
    def get_order_count(self):
        # Calculate the number of orders for the seller
        return Order.objects.filter(user=self.user).count()    

class Transaction(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.seller.username} - {self.amount} - {self.timestamp}"
        
class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following', null=True, blank=True)
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers', null=True, blank=True)

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('electronic', 'Electronic'),
        ('fashion', 'Fashion'),
        ('home_appliance', 'Home Appliance'),
        ('books', 'Books'),
        ('toys', 'Toys'),
        ('beauty', 'Beauty'),
        ('sports', 'Sports'),
        ('outdoor', 'Outdoor'),
        ('automotive', 'Automotive'),
        ('grocery', 'Grocery'),
        ('health', 'Health'),
        ('furniture', 'Furniture'),
        ('jewelry', 'Jewelry'),
        ('stationery', 'Stationery'),
        ('tools', 'Tools'),
        ('food', 'Food'),
        # Add more categories as needed
    ]
    PAYMENT_CHOICES = [
        ('stripe', 'Online Payment'),
        ('cod', 'Cash on Delivery (COD)'),
    ]
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='media/product_images', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    video = models.FileField(upload_to='media/product_videos', null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=20, blank=True, null=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    color = models.CharField(max_length=20, blank=True, null=True)
    payment = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='stripe')
    # Add a COD (Cash on Delivery) field
    cod_available = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class CartItem(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.title}"
    def belongs_to_user(self, user):
        # Check if the CartItem belongs to the specified user
        return self.user == user if self.user else False
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True)
    items = models.ManyToManyField('CartItem')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Additional fields
    shipping_address = models.TextField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    # Add a COD (Cash on Delivery) field
    cod_selected = models.BooleanField(default=False)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_address = models.TextField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    # Add a field to store the shipper (if applicable)
    shipper = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='shipper_orders', null=True, blank=True)

    # Add a field to store the delivery driver (if applicable)
    delivery_driver = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='driver_orders', null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

    def mark_confirmed(self):
        if self.status == 'pending':
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()

    def mark_shipped(self):
        if self.status == 'confirmed':
            self.status = 'shipped'
            self.shipped_at = timezone.now()
            self.save()

    def mark_delivered(self):
        if self.status == 'shipped':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save()

    def cancel_order(self):
        if self.status == 'pending' or self.status == 'confirmed':
            self.status = 'canceled'
            self.save()
class Comment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.comment} {self.pk}'

    def get_absolute_url(self):
        return reverse('show_product', kwargs={
            'product_id': self.product.id,
            'author_profile_image': self.author.profile.image.url,
            'comments': self.product.comments.all(),
        })    

    def save(self, *args, **kwargs):
        """Override save method to update created_at field"""
        if not self.id:
            self.created_at = timezone.now()
        super(Comment, self).save(*args, **kwargs)

    def edit(self, new_comment):
        """Update the comment field of the comment object"""
        self.comment = new_comment
        self.save()

    def delete(self):
        """Delete the comment object"""
        super(Comment, self).delete()

class StarsFeedback(models.Model):
    STARS_CHOICES = [
        (1, '⭐'),
        (2, '⭐⭐'),
        (3, '⭐⭐⭐'),
        (4, '⭐⭐⭐⭐'),
        (5, '⭐⭐⭐⭐⭐'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stars_feedback')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_feedback')
    stars = models.IntegerField(choices=STARS_CHOICES)
    created_at = models.DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return f'{self.stars} {self.pk}'

    def get_star_display(self):
        return ' '.join(['⭐' for _ in range(self.stars)])

    def get_absolute_url(self):
        return reverse('show_product', kwargs={
            'product_id': self.product.id,
            'author_profile_image': self.author.profile.image.url,
            'stars_feedback': self.product.stars_feedback.all(),
        })

    def save(self, *args, **kwargs):
        if not self.pk and self.product:
            self.product_id = self.product.pk
        super(StarsFeedback, self).save(*args, **kwargs)

# Message and Notifications

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sender_messages')
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} to {self.recipient}"

    class Meta:
        ordering = ['-timestamp'] 

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True)
    stars_feedback = models.ForeignKey(StarsFeedback, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    
    def __str__(self):
        return f"{self.user}: {self.get_notification_type()}"

    def get_notification_type(self):
        if self.product:
            return f"New post from {self.product.seller.username}"
        elif self.message:
            return f"New message from {self.message.sender.username}"
        elif self.stars_feedback:
            return f"{self.stars_feedback.author.username} reacted to your post with {self.stars_feedback.get_emoji_display()}"
        elif self.comment:
            return f"{self.comment.author.username} commented on your post" 
        else:
            return "Unknown notification type"
    
    class Meta:
        ordering = ['-timestamp'] 
