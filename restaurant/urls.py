"""
URL configuration for restaurant project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .admin import custom_admin_site

urlpatterns = [
    # Admin
    path('admin/', custom_admin_site.urls),
    
    # Authentication
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.user_register, name='register'),
    
    # Main pages
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('add-deposit/', views.add_deposit, name='add_deposit'),
    
    # Dish pages
    path('dish/<int:dish_id>/', views.dish_detail, name='dish_detail'),
    
    # AI Chat
    path('chat/', views.ai_chat, name='ai_chat'),
    path('rate-answer/', views.rate_answer, name='rate_answer'),
    
    # Order and Cart
    path('cart/', views.cart, name='cart'),
    path('cart-data/', views.get_cart_data, name='get_cart_data'),
    path('add-to-cart/<int:dish_id>/', views.add_to_cart, name='add_to_cart'),
    path('create-order/', views.create_order, name='create_order'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/rate-dish/', views.rate_dish, name='rate_dish'),
    path('order/rate-delivery/', views.rate_delivery, name='rate_delivery'),
    path('order/file-complaint-compliment/', views.file_order_complaint_compliment, name='file_order_complaint_compliment'),
    
    # Stage 4: Delivery Bidding and Reputation
    path('delivery-orders/', views.delivery_orders, name='delivery_orders'),
    path('bid-on-delivery/', views.bid_on_delivery, name='bid_on_delivery'),
    
    # Stage 5: Creative Feature - Route Planning
    path('delivery-route/<int:order_id>/', views.get_delivery_route, name='get_delivery_route'),
    path('delivery-route-map/<int:order_id>/', views.delivery_route_map, name='delivery_route_map'),
    path('optimize-routes/', views.optimize_delivery_routes, name='optimize_delivery_routes'),
    
    # Address Book Management
    path('address/add/', views.add_address, name='add_address'),
    path('address/<int:address_id>/', views.get_address, name='get_address'),
    path('address/<int:address_id>/edit/', views.edit_address, name='edit_address'),
    path('address/<int:address_id>/delete/', views.delete_address, name='delete_address'),
    path('address/<int:address_id>/set-default/', views.set_default_address, name='set_default_address'),
    
    # Forum
    path('forum/', views.forum, name='forum'),
    path('forum/post/create/', views.create_forum_post, name='create_forum_post'),
    path('forum/post/<int:post_id>/delete/', views.delete_forum_post, name='delete_forum_post'),
    path('forum/post/<int:post_id>/comment/', views.add_forum_comment, name='add_forum_comment'),
    path('forum/post/<int:post_id>/reaction/', views.toggle_post_reaction, name='toggle_post_reaction'),
    path('forum/comment/<int:comment_id>/delete/', views.delete_forum_comment, name='delete_forum_comment'),
    path('forum/comment/<int:comment_id>/reaction/', views.toggle_comment_reaction, name='toggle_comment_reaction'),
    path('forum/complaint/', views.file_forum_complaint, name='file_forum_complaint'),
    path('forum/announcement/create/', views.create_announcement, name='create_announcement'),
    path('forum/announcement/<int:announcement_id>/', views.get_announcement, name='get_announcement'),
    path('forum/announcement/<int:announcement_id>/update/', views.update_announcement, name='update_announcement'),
    path('forum/announcement/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
