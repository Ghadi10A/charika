from django.urls import include, path, re_path
from django.views.generic.base import RedirectView
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('stripe_checkout/', views.stripe_checkout, name='stripe_checkout'),
    path('stripe_checkout_from_cart/', views.stripe_checkout_from_cart, name='stripe_checkout_from_cart'),
    path('success/<int:product_id>/', views.success, name='success'),
    path('success-checkout/', views.success_checkout, name='success_checkout'),
    path('cancel/', views.cancel, name='cancel'),
    path('product/<int:product_id>/', views.show_product, name='show_product'),
    path('comment/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('product/<int:product_id>/add_stars_feedback/', views.add_stars_feedback, name='add_stars_feedback'),
    path('stars_feedback/<int:stars_feedback_id>/edit/', views.edit_stars_feedback, name='edit_stars_feedback'),
    path('stars_feedback/<int:stars_feedback_id>/delete/', views.delete_stars_feedback, name='delete_stars_feedback'),
    path('confirm_order/<int:order_id>/', views.confirm_order, name='confirm_order'),
    path('cancel_order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    # User authentication URLs
    path('accounts/profile/<str:username>', include('django.contrib.auth.urls')),
    path('signup/', views.signup, name='signup'),
    path('activate/<str:uidb64>/<str:token>/', views.activate_account, name='activate_account'),
    path('login/', views.user_login, name='user_login'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/', views.reset_password, name='reset_password'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='auth/password_reset.html', email_template_name='auth/password_reset_email.html', subject_template_name='auth/password_reset_subject.txt', success_url='/password-reset/done/'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='auth/password_reset_done.html'), name='password_reset_done'),
    path('reset/<str:uidb64>/<str:token>/', auth_views.PasswordResetConfirmView.as_view(template_name='auth/password_reset_confirm.html', success_url='/reset/done/'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='auth/password_reset_complete.html'), name='password_reset_complete'),  # Replace with your actual login view
    path('logout/', views.user_logout, name='user_logout'),  # Replace with your actual logout view
    path('verification-email/', views.verification_email_sent, name='verification_email_sent'),
    path('verification-email-resend/<str:user>/', views.verification_email_resend, name='verification_email_resend'),
    path('product/<int:product_id>/update/', views.update_product, name='update_product'),
    path('product/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    # Profile related URLs
    path('orders/<str:username>', views.orders, name='orders'),
    path('orders/<str:username>/<int:order_id>/', views.orders, name='orders_with_id'),
    path('save_customer_info/', views.save_customer_info, name='save_customer_info'),
    path('profile/<str:username>', views.profile, name='profile'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('withdraw/', views.withdraw, name='withdraw'),
    # Product related URLs
    path('cod_checkout/', views.cod_checkout, name='cod_checkout'),
    path('sell_product/', views.sell_product, name='sell_product'),
    path('search/', views.search, name='search'),
    # Cart related URLs
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    # Follow and Unfollow
    path('follow/<str:username>/', views.follow_user, name='follow'),
    path('unfollow/<str:username>/', views.unfollow_user, name='unfollow'),
    # Checkout and order related URLs
    path('checkout/', views.checkout, name='checkout'),
    path('order_confirmation/', views.order_confirmation, name='order_confirmation'),
    # Message
    path('messages/<str:username>/', views.message_thread, name='message_thread'),
    path('messages-and-conversations/', views.saved_conversations, name='saved_conversations'),
    # About us
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('about-us/', views.about_us, name='about_us'),
    path('contact-us/', views.contact_us, name='contact_us'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('notifications/', views.notification, name='notification'),
    path('mark-notification-as-read/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('<str:language_code>/', views.switch_language, name='switch_language'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)