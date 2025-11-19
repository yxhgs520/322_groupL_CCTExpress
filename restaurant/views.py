from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import (
    Customer, Chef, DeliveryPerson, Manager, Dish, Order, OrderItem,
    DishRating, DeliveryRating, Complaint, Compliment, KnowledgeBase,
    DeliveryBid
)
import json
import requests
from decimal import Decimal
from django.conf import settings
from geopy.geocoders import Nominatim
from geopy.distance import geodesic


def index(request):
    """Visitor homepage - shows full menu, chat box, popular and top-rated dishes"""
    # Get all available dishes
    dishes = Dish.objects.filter(is_available=True).order_by('-created_at')
    
    # Get most popular dishes (by order count) - only show dishes with at least 1 order
    popular_dishes = Dish.objects.filter(is_available=True).annotate(
        order_count=Count('orderitem')
    ).filter(order_count__gt=0).order_by('-order_count')[:6]
    
    # Get top-rated dishes
    top_rated_dishes = Dish.objects.filter(is_available=True).annotate(
        avg_rating=Avg('dishrating__rating')
    ).filter(avg_rating__isnull=False).order_by('-avg_rating')[:6]
    
    # Get top-rated chefs
    top_chefs = Chef.objects.filter(is_active=True).annotate(
        avg_rating=Avg('dish__dishrating__rating')
    ).filter(avg_rating__isnull=False).order_by('-avg_rating')[:3]
    
    context = {
        'dishes': dishes,
        'popular_dishes': popular_dishes,
        'top_rated_dishes': top_rated_dishes,
        'top_chefs': top_chefs,
        'user': request.user,
    }
    return render(request, 'index.html', context)


@login_required
def dashboard(request):
    """User dashboard - shows personalized content based on user type"""
    user = request.user
    
    # Check user type and redirect accordingly
    if hasattr(user, 'customer'):
        return customer_dashboard(request)
    elif hasattr(user, 'chef'):
        return chef_dashboard(request)
    elif hasattr(user, 'deliveryperson'):
        return delivery_dashboard(request)
    elif hasattr(user, 'manager'):
        return manager_dashboard(request)
    else:
        # User exists but no profile - redirect to registration
        return redirect('register')


def customer_dashboard(request):
    """Customer/VIP dashboard"""
    customer = request.user.customer
    
    # Get customer's order history
    customer_orders = Order.objects.filter(customer=customer).order_by('-created_at')
    
    # Get most ordered dishes by this customer
    most_ordered = Dish.objects.filter(
        orderitem__order__customer=customer
    ).annotate(
        order_count=Count('orderitem')
    ).order_by('-order_count')[:6]
    
    # Get highest rated dishes by this customer
    highest_rated = Dish.objects.filter(
        dishrating__customer=customer
    ).annotate(
        customer_rating=Avg('dishrating__rating')
    ).filter(customer_rating__isnull=False).order_by('-customer_rating')[:6]
    
    # Get VIP exclusive dishes if customer is VIP
    vip_dishes = []
    if customer.is_vip:
        vip_dishes = Dish.objects.filter(is_vip_only=True, is_available=True)[:6]
    
    context = {
        'customer': customer,
        'most_ordered': most_ordered,
        'highest_rated': highest_rated,
        'vip_dishes': vip_dishes,
        'recent_orders': customer_orders[:5],
    }
    return render(request, 'dashboard.html', context)


def chef_dashboard(request):
    """Chef dashboard - shows chef's dishes, ratings, and complaints"""
    chef = request.user.chef
    
    # Get chef's dishes
    chef_dishes = Dish.objects.filter(chef=chef, is_available=True)
    
    # Get average rating for chef's dishes
    chef_rating = chef_dishes.annotate(
        avg_rating=Avg('dishrating__rating')
    ).aggregate(avg_rating=Avg('avg_rating'))['avg_rating'] or 0
    
    # Get complaints about chef
    chef_complaints = Complaint.objects.filter(
        chef=chef,
        status__in=['pending', 'investigating']
    ).order_by('-created_at')
    
    # Get compliments about chef
    chef_compliments = Compliment.objects.filter(
        chef=chef,
        status='approved'
    ).order_by('-created_at')
    
    # Get recent orders for chef's dishes
    recent_orders = Order.objects.filter(
        orderitem__dish__chef=chef
    ).distinct().order_by('-created_at')[:10]
    
    context = {
        'chef': chef,
        'chef_dishes': chef_dishes,
        'chef_rating': round(chef_rating, 2),
        'complaints': chef_complaints,
        'compliments': chef_compliments,
        'recent_orders': recent_orders,
    }
    return render(request, 'chef_dashboard.html', context)


def delivery_dashboard(request):
    """Delivery person dashboard - shows delivery person's ratings and complaints"""
    delivery_person = request.user.deliveryperson
    
    # Get delivery person's average rating
    delivery_rating = DeliveryRating.objects.filter(
        delivery_person=delivery_person
    ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
    
    # Get complaints about delivery person
    delivery_complaints = Complaint.objects.filter(
        delivery_person=delivery_person,
        status__in=['pending', 'investigating']
    ).order_by('-created_at')
    
    # Get compliments about delivery person
    delivery_compliments = Compliment.objects.filter(
        delivery_person=delivery_person,
        status='approved'
    ).order_by('-created_at')
    
    # Get recent deliveries
    recent_deliveries = Order.objects.filter(
        delivery_person=delivery_person
    ).order_by('-created_at')[:10]
    
    context = {
        'delivery_person': delivery_person,
        'delivery_rating': round(delivery_rating, 2),
        'complaints': delivery_complaints,
        'compliments': delivery_compliments,
        'recent_deliveries': recent_deliveries,
    }
    return render(request, 'delivery_dashboard.html', context)


def manager_dashboard(request):
    """Manager dashboard - shows management overview"""
    manager = request.user.manager
    
    # Get pending complaints
    pending_complaints = Complaint.objects.filter(status='pending').count()
    
    # Get pending compliments
    pending_compliments = Compliment.objects.filter(status='pending').count()
    
    # Get recent orders
    recent_orders = Order.objects.order_by('-created_at')[:10]
    
    # Get customer statistics
    total_customers = Customer.objects.count()
    vip_customers = Customer.objects.filter(is_vip=True).count()
    blacklisted_customers = Customer.objects.filter(is_blacklisted=True).count()
    
    context = {
        'manager': manager,
        'pending_complaints': pending_complaints,
        'pending_compliments': pending_compliments,
        'recent_orders': recent_orders,
        'total_customers': total_customers,
        'vip_customers': vip_customers,
        'blacklisted_customers': blacklisted_customers,
    }
    return render(request, 'manager_dashboard.html', context)


def user_login(request):
    """User login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')


def user_logout(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('index')


def user_register(request):
    """User registration view - Only for customers"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Validate passwords match
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register.html')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'register.html')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create customer profile (default for registration page)
        Customer.objects.create(user=user)
        messages.success(request, 'Customer account created successfully!')
        
        # Auto login user
        login(request, user)
        return redirect('dashboard')
    
    return render(request, 'register.html')


@csrf_exempt
@require_http_methods(["POST"])
def ai_chat(request):
    """AI chat functionality for restaurant questions"""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'error': 'Please enter a question.'}, status=400)
        
        # First, search in local knowledge base
        knowledge_entries = KnowledgeBase.objects.filter(
            Q(question__icontains=question) | Q(answer__icontains=question),
            is_flagged=False
        ).order_by('-created_at')[:3]
        
        if knowledge_entries.exists():
            best_answer = knowledge_entries.first()
            return JsonResponse({
                'answer': best_answer.answer,
                'source': 'local',
                'knowledge_id': best_answer.id
            })
        else:
            # If no local knowledge, delegate to Ollama LLM
            try:
                ollama_response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': 'llama3:8b',
                        'prompt': f"You are a helpful restaurant assistant. Answer this customer question about our restaurant: {question}. Be friendly and helpful.",
                        'stream': False
                    },
                    timeout=30
                )
                
                if ollama_response.status_code == 200:
                    llm_data = ollama_response.json()
                    answer = llm_data.get('response', 'I apologize, but I cannot provide an answer at this time.')
                    return JsonResponse({
                        'answer': answer,
                        'source': 'LLM',
                        'model': 'llama3:8b'
                    })
                else:
                    return JsonResponse({
                        'answer': "I'm sorry, I don't have specific information about that in our knowledge base, and our AI assistant is currently unavailable. Please contact our staff for assistance.",
                        'source': 'fallback'
                    })
            except requests.exceptions.RequestException:
                return JsonResponse({
                    'answer': "I'm sorry, I don't have specific information about that in our knowledge base, and our AI assistant is currently unavailable. Please contact our staff for assistance.",
                    'source': 'fallback'
                })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'AI chat failed: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rate_answer(request):
    """Rate knowledge base answers"""
    try:
        data = json.loads(request.body)
        knowledge_id = data.get('knowledge_id')
        rating = data.get('rating', 0)
        
        if not knowledge_id:
            return JsonResponse({'error': 'Knowledge ID is required.'}, status=400)
        
        try:
            knowledge = KnowledgeBase.objects.get(id=knowledge_id)
        except KnowledgeBase.DoesNotExist:
            return JsonResponse({'error': 'Knowledge entry not found.'}, status=404)
        
        # If rating is 0 (outrageous), flag for manager review
        if rating == 0:
            knowledge.is_flagged = True
            knowledge.save()
            return JsonResponse({
                'message': 'Answer flagged for manager review.',
                'flagged': True
            })
        
        # Update rating (simplified - you might want to track individual user ratings)
        # For now, we'll just acknowledge the feedback
        return JsonResponse({
            'message': 'Thank you for your feedback!',
            'flagged': False
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Rating failed: {str(e)}'}, status=500)


@login_required
def profile(request):
    """User profile page"""
    user = request.user
    
    if hasattr(user, 'customer'):
        customer = user.customer
        orders = Order.objects.filter(customer=customer).order_by('-created_at')[:10]
        
        context = {
            'customer': customer,
            'orders': orders,
        }
        return render(request, 'profile.html', context)
    
    return redirect('dashboard')


@login_required
@require_http_methods(["POST"])
def add_deposit(request):
    """Add deposit to customer account"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can add deposits.'}, status=403)
    
    try:
        amount = Decimal(str(request.POST.get('amount', 0)))
        
        if amount <= 0:
            return JsonResponse({'error': 'Amount must be greater than 0.'}, status=400)
        
        customer = request.user.customer
        customer.deposit += amount
        customer.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Deposit of ${amount} added successfully.',
            'new_balance': float(customer.deposit)
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': 'Invalid amount format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to add deposit: {str(e)}'}, status=500)


def dish_detail(request, dish_id):
    """Dish detail page"""
    dish = get_object_or_404(Dish, id=dish_id)
    
    # Get dish ratings
    ratings = DishRating.objects.filter(dish=dish).order_by('-created_at')
    
    # Get average rating
    avg_rating = ratings.aggregate(avg=Avg('rating'))['avg'] or 0
    
    context = {
        'dish': dish,
        'ratings': ratings,
        'avg_rating': round(avg_rating, 2),
    }
    return render(request, 'dish_detail.html', context)


# ==================== STAGE 3: ORDER, FINANCE & AI CUSTOMER SERVICE ====================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def create_order(request):
    """Create order with financial validation and VIP discount"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can place orders.'}, status=403)
    
    try:
        data = json.loads(request.body)
        dish_items = data.get('items', [])  # [{'dish_id': 1, 'quantity': 2}, ...]
        
        if not dish_items:
            return JsonResponse({'error': 'No items in order.'}, status=400)
        
        customer = request.user.customer
        
        # Calculate total amount
        total_amount = Decimal('0.00')
        order_items = []
        
        for item in dish_items:
            dish_id = item.get('dish_id')
            quantity = int(item.get('quantity', 1))
            
            if quantity <= 0:
                return JsonResponse({'error': f'Invalid quantity for dish {dish_id}.'}, status=400)
            
            try:
                dish = Dish.objects.get(id=dish_id, is_available=True)
            except Dish.DoesNotExist:
                return JsonResponse({'error': f'Dish {dish_id} not available.'}, status=400)
            
            # Check VIP access for VIP-only dishes
            if dish.is_vip_only and not customer.is_vip:
                return JsonResponse({'error': f'Dish "{dish.name}" is VIP exclusive.'}, status=403)
            
            item_total = dish.price * quantity
            total_amount += item_total
            
            order_items.append({
                'dish': dish,
                'quantity': quantity,
                'price': dish.price,
                'subtotal': item_total
            })
        
        # Apply VIP discount (5%)
        if customer.is_vip:
            discount = total_amount * Decimal('0.05')
            total_amount -= discount
            discount_applied = True
        else:
            discount = Decimal('0.00')
            discount_applied = False
        
        # Check if customer has enough deposit
        if total_amount > customer.deposit:
            # Add warning for insufficient funds
            customer.warnings += 1
            customer.save()
            
            return JsonResponse({
                'error': 'Insufficient funds. Order rejected.',
                'warning_added': True,
                'warnings': customer.warnings,
                'required_amount': float(total_amount),
                'available_deposit': float(customer.deposit)
            }, status=400, content_type='application/json')
        
        # Create order
        order = Order.objects.create(
            customer=customer,
            total_amount=total_amount,
            status='pending'
        )
        
        # Create order items
        for item in order_items:
            OrderItem.objects.create(
                order=order,
                dish=item['dish'],
                quantity=item['quantity'],
                price=item['price']
            )
        
        # Update customer deposit and spending
        customer.deposit -= total_amount
        customer.total_spent += total_amount
        customer.order_count += 1
        customer.save()
        
        # Check for VIP status upgrade
        customer.check_vip_status()
        
        # Clear cart after successful order
        request.session['cart'] = []
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'total_amount': float(total_amount),
            'discount_applied': discount_applied,
            'discount_amount': float(discount),
            'remaining_deposit': float(customer.deposit),
            'is_vip': customer.is_vip
        }, content_type='application/json')
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400, content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': f'Order creation failed: {str(e)}'}, status=500, content_type='application/json')


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def cancel_order(request, order_id):
    """Cancel order - only if status is pending"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can cancel orders.'}, status=403, content_type='application/json')
    
    try:
        order = Order.objects.get(id=order_id, customer=request.user.customer)
        
        # Only allow cancellation if order status is pending
        if order.status != 'pending':
            return JsonResponse({
                'error': f'Order cannot be cancelled. Current status: {order.get_status_display()}. Only pending orders can be cancelled.'
            }, status=400, content_type='application/json')
        
        # Refund deposit to customer
        customer = request.user.customer
        customer.deposit += order.total_amount
        customer.order_count = max(0, customer.order_count - 1)  # Decrease order count
        customer.save()
        
        # Update order status
        order.status = 'cancelled'
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Order #{order.id} has been cancelled. Deposit refunded.',
            'refunded_amount': float(order.total_amount),
            'new_balance': float(customer.deposit)
        }, content_type='application/json')
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found or you do not have permission to cancel this order.'}, status=404, content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': f'Failed to cancel order: {str(e)}'}, status=500, content_type='application/json')


@login_required
def cart(request):
    """Shopping cart page"""
    if not hasattr(request.user, 'customer'):
        return redirect('index')
    
    # Get cart items from session (simplified implementation)
    cart_items = request.session.get('cart', [])
    dishes = []
    total_amount = Decimal('0.00')
    
    for item in cart_items:
        try:
            dish = Dish.objects.get(id=item['dish_id'], is_available=True)
            quantity = int(item['quantity'])
            
            # Check VIP access
            if dish.is_vip_only and not request.user.customer.is_vip:
                continue
            
            item_total = dish.price * quantity
            total_amount += item_total
            
            dishes.append({
                'dish': dish,
                'quantity': quantity,
                'subtotal': item_total
            })
        except Dish.DoesNotExist:
            continue
    
    # Apply VIP discount
    discount = Decimal('0.00')
    if request.user.customer.is_vip:
        discount = total_amount * Decimal('0.05')
        total_amount -= discount
    
    context = {
        'dishes': dishes,
        'total_amount': total_amount,
        'discount': discount,
        'final_amount': total_amount,
        'is_vip': request.user.customer.is_vip,
        'customer': request.user.customer
    }
    return render(request, 'cart.html', context)


@login_required
def get_cart_data(request):
    """Get cart data as JSON for sidebar"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'items': [], 'total': 0, 'count': 0})
    
    cart_items = request.session.get('cart', [])
    dishes = []
    total = Decimal('0.00')
    
    for item in cart_items:
        try:
            dish = Dish.objects.get(id=item['dish_id'], is_available=True)
            quantity = int(item['quantity'])
            if quantity <= 0:
                continue
            
            if dish.is_vip_only and not request.user.customer.is_vip:
                continue
            
            item_total = dish.price * quantity
            total += item_total
            
            dishes.append({
                'id': dish.id,
                'name': dish.name,
                'price': float(dish.price),
                'quantity': quantity,
                'subtotal': float(item_total),
                'image_url': dish.image.url if dish.image else ''
            })
        except Dish.DoesNotExist:
            continue
    
    # Apply VIP discount
    if request.user.customer.is_vip:
        discount = total * Decimal('0.05')
        total -= discount
    
    return JsonResponse({
        'items': dishes,
        'total': float(total),
        'count': len(dishes)
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_to_cart(request, dish_id):
    """Add dish to cart"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can add to cart.'}, status=403)
    
    try:
        dish = Dish.objects.get(id=dish_id, is_available=True)
        customer = request.user.customer
        
        # Check VIP access
        if dish.is_vip_only and not customer.is_vip:
            return JsonResponse({'error': 'This dish is VIP exclusive.'}, status=403)
        
        # Get or create cart
        cart = request.session.get('cart', [])
        
        # Check if item already in cart
        item_found = False
        for item in cart:
            if item['dish_id'] == dish_id:
                item['quantity'] += 1
                item_found = True
                break
        
        if not item_found:
            cart.append({'dish_id': dish_id, 'quantity': 1})
        
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'message': f'{dish.name} added to cart.',
            'cart_count': len(cart)
        }, content_type='application/json')
        
    except Dish.DoesNotExist:
        return JsonResponse({'error': 'Dish not found or not available.'}, status=404, content_type='application/json')
    except Exception as e:
        return JsonResponse({'error': f'Failed to add to cart: {str(e)}'}, status=500, content_type='application/json')


# ==================== STAGE 4: DELIVERY BIDDING, REPUTATION & VIP/WARNING LOGIC ====================

@login_required
@require_http_methods(["POST"])
def bid_on_delivery(request):
    """Delivery person bidding on delivery orders"""
    if not hasattr(request.user, 'deliveryperson'):
        return JsonResponse({'error': 'Only delivery persons can bid on deliveries.'}, status=403)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        bid_amount = Decimal(str(data.get('bid_amount', 0)))
        
        if bid_amount <= 0:
            return JsonResponse({'error': 'Bid amount must be greater than 0.'}, status=400)
        
        try:
            order = Order.objects.get(id=order_id, status='confirmed')
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found or not available for delivery.'}, status=404)
        
        delivery_person = request.user.deliveryperson
        
        # Check if delivery person is active
        if not delivery_person.is_active:
            return JsonResponse({'error': 'Your delivery account is not active.'}, status=403)
        
        # Create or update bid
        bid, created = DeliveryBid.objects.get_or_create(
            delivery_person=delivery_person,
            order=order,
            defaults={'bid_amount': bid_amount}
        )
        
        if not created:
            bid.bid_amount = bid_amount
            bid.save()
            message = 'Bid updated successfully.'
        else:
            message = 'Bid submitted successfully.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'bid_amount': float(bid_amount),
            'order_id': order_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Bidding failed: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def file_complaint_compliment(request):
    """File complaints or compliments"""
    try:
        data = json.loads(request.body)
        complaint_type = data.get('type')  # 'complaint' or 'compliment'
        target_type = data.get('target_type')  # 'chef', 'delivery', 'customer'
        target_id = data.get('target_id')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        order_id = data.get('order_id')
        
        if not title or not description:
            return JsonResponse({'error': 'Title and description are required.'}, status=400)
        
        # Only customers can submit via portal (delivery feedback handled via manager portal)
        if not hasattr(request.user, 'customer'):
            return JsonResponse({'error': 'Only customers can file complaints or compliments here.'}, status=403)

        complainant = request.user.customer
        
        # Get order first (required)
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, customer=complainant)
            except Order.DoesNotExist:
                return JsonResponse({'error': 'Order not found or you do not have permission to access this order.'}, status=404)
        else:
            return JsonResponse({'error': 'Order ID is required.'}, status=400)
        
        # Get target objects based on order
        target_chef = None
        target_delivery = None
        target_customer = None
        
        # Determine target based on order
        if target_type == 'chef':
            # Get chef from order items
            order_items = OrderItem.objects.filter(order=order)
            if order_items.exists():
                # Get the chef from the first dish (assuming all dishes from same chef for simplicity)
                target_chef = order_items.first().dish.chef
            else:
                return JsonResponse({'error': 'No dishes found in this order.'}, status=400)
        elif target_type == 'delivery':
            # Get delivery person from order
            if order.delivery_person:
                target_delivery = order.delivery_person
            else:
                return JsonResponse({'error': 'This order does not have a delivery person assigned yet.'}, status=400)
        elif target_type == 'customer':
            # For customer complaints, use target_id if provided
            if target_id:
                try:
                    target_customer = Customer.objects.get(id=target_id)
                except Customer.DoesNotExist:
                    return JsonResponse({'error': 'Customer not found.'}, status=404)
            else:
                return JsonResponse({'error': 'Target customer ID is required when target type is customer.'}, status=400)
        else:
            return JsonResponse({'error': 'Invalid target type. Must be chef or delivery.'}, status=400)
        
        # Create complaint or compliment
        if complaint_type == 'complaint':
            complaint = Complaint.objects.create(
                complainant=complainant,
                chef=target_chef,
                delivery_person=target_delivery,
                customer=target_customer,
                order=order,
                title=title,
                description=description,
                status='pending'
            )
            message = 'Complaint filed successfully. It will be reviewed by management.'
        else:  # compliment
            compliment = Compliment.objects.create(
                complimenter=complainant,
                chef=target_chef,
                delivery_person=target_delivery,
                customer=target_customer,
                order=order,
                title=title,
                description=description,
                status='pending'
            )
            message = 'Compliment submitted successfully. It will be reviewed by management.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'type': complaint_type
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to file {complaint_type}: {str(e)}'}, status=500)


@login_required
def delivery_orders(request):
    """View available delivery orders for bidding"""
    if not hasattr(request.user, 'deliveryperson'):
        return redirect('dashboard')
    
    delivery_person = request.user.deliveryperson
    
    # Get orders available for delivery (confirmed status)
    available_orders = Order.objects.filter(
        status='confirmed',
        delivery_person__isnull=True
    ).order_by('-created_at')
    
    # Get orders where this delivery person has bid
    my_bids = DeliveryBid.objects.filter(
        delivery_person=delivery_person
    ).select_related('order').order_by('-created_at')
    
    context = {
        'available_orders': available_orders,
        'my_bids': my_bids,
        'delivery_person': delivery_person
    }
    return render(request, 'delivery_orders.html', context)


@login_required
def my_complaints_compliments(request):
    """View user's complaints and compliments"""
    user = request.user
    
    complaints = []
    compliments = []
    
    if hasattr(user, 'customer'):
        complaints = Complaint.objects.filter(complainant=user.customer).order_by('-created_at')
        compliments = Compliment.objects.filter(complimenter=user.customer).order_by('-created_at')
    elif hasattr(user, 'deliveryperson'):
        complaints = Complaint.objects.filter(delivery_person=user.deliveryperson).order_by('-created_at')
        compliments = Compliment.objects.filter(delivery_person=user.deliveryperson).order_by('-created_at')
    elif hasattr(user, 'chef'):
        complaints = Complaint.objects.filter(chef=user.chef).order_by('-created_at')
        compliments = Compliment.objects.filter(chef=user.chef).order_by('-created_at')
    
    context = {
        'complaints': complaints,
        'compliments': compliments
    }
    return render(request, 'my_complaints_compliments.html', context)


# ==================== STAGE 5: CREATIVE FEATURE - DELIVERY ROUTE PLANNING ====================

def get_coordinates_from_address(address):
    """Get coordinates from address using geopy"""
    try:
        geolocator = Nominatim(user_agent="restaurant_delivery_system")
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None


@login_required
def get_delivery_route(request, order_id):
    """Get delivery route for an order using OpenRouteService API"""
    try:
        # Get the order
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission to view this order
        if not (hasattr(request.user, 'customer') and order.customer == request.user.customer) and \
           not (hasattr(request.user, 'deliveryperson') and order.delivery_person == request.user.deliveryperson) and \
           not (hasattr(request.user, 'manager')):
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        
        # Get restaurant coordinates
        restaurant_lat = settings.RESTAURANT_LATITUDE
        restaurant_lon = settings.RESTAURANT_LONGITUDE
        
        # Get customer address (you might need to add address field to Customer model)
        # For now, we'll use a default customer address or get it from order
        customer_address = getattr(order.customer, 'address', 'New York, NY')  # Default address
        
        # Get customer coordinates
        customer_lat, customer_lon = get_coordinates_from_address(customer_address)
        
        if not customer_lat or not customer_lon:
            return JsonResponse({
                'error': 'Could not find customer address coordinates.',
                'customer_address': customer_address
            }, status=400)
        
        # Check if API key is configured
        if not settings.OPENROUTESERVICE_API_KEY:
            return JsonResponse({
                'error': 'OpenRouteService API key not configured.',
                'restaurant_coords': [restaurant_lon, restaurant_lat],
                'customer_coords': [customer_lon, customer_lat],
                'distance_km': round(geodesic((restaurant_lat, restaurant_lon), (customer_lat, customer_lon)).kilometers, 2)
            }, status=400)
        
        # Call OpenRouteService API
        api_url = f"{settings.OPENROUTESERVICE_BASE_URL}/driving-car/json"
        
        headers = {
            'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
            'Authorization': settings.OPENROUTESERVICE_API_KEY,
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        body = {
            "coordinates": [
                [restaurant_lon, restaurant_lat],  # Start: Restaurant
                [customer_lon, customer_lat]        # End: Customer
            ],
            "format": "json"
        }
        
        response = requests.post(api_url, json=body, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'features' in data and len(data['features']) > 0:
                feature = data['features'][0]
                properties = feature.get('properties', {})
                summary = properties.get('summary', {})
                
                # Extract route information
                distance_meters = summary.get('distance', 0)
                duration_seconds = summary.get('duration', 0)
                
                # Convert to more readable units
                distance_km = round(distance_meters / 1000, 2)
                duration_minutes = round(duration_seconds / 60, 1)
                
                # Get route geometry for map display
                geometry = feature.get('geometry', {})
                coordinates = geometry.get('coordinates', [])
                
                return JsonResponse({
                    'success': True,
                    'route': {
                        'distance_km': distance_km,
                        'distance_meters': distance_meters,
                        'duration_minutes': duration_minutes,
                        'duration_seconds': duration_seconds,
                        'coordinates': coordinates,
                        'restaurant_coords': [restaurant_lon, restaurant_lat],
                        'customer_coords': [customer_lon, customer_lat]
                    },
                    'order_info': {
                        'order_id': order.id,
                        'customer': order.customer.user.username,
                        'restaurant_address': settings.RESTAURANT_ADDRESS,
                        'customer_address': customer_address
                    }
                })
            else:
                return JsonResponse({'error': 'No route found.'}, status=404)
        else:
            return JsonResponse({
                'error': f'OpenRouteService API error: {response.status_code}',
                'response': response.text
            }, status=response.status_code)
            
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'API request failed: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Route calculation failed: {str(e)}'}, status=500)


@login_required
def delivery_route_map(request, order_id):
    """Display delivery route on interactive map"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permissions
    if not (hasattr(request.user, 'customer') and order.customer == request.user.customer) and \
       not (hasattr(request.user, 'deliveryperson') and order.delivery_person == request.user.deliveryperson) and \
       not (hasattr(request.user, 'manager')):
        return redirect('dashboard')
    
    context = {
        'order': order,
        'order_id': order_id
    }
    return render(request, 'delivery_route_map.html', context)


@login_required
def optimize_delivery_routes(request):
    """Optimize delivery routes for multiple orders (Manager only)"""
    if not hasattr(request.user, 'manager'):
        return redirect('dashboard')
    
    # Get pending orders
    pending_orders = Order.objects.filter(
        status__in=['confirmed', 'ready'],
        delivery_person__isnull=True
    ).order_by('-created_at')[:10]
    
    context = {
        'pending_orders': pending_orders
    }
    return render(request, 'optimize_routes.html', context)
