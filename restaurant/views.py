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
import difflib
from .models import (
    Customer, Chef, DeliveryPerson, Manager, Dish, Order, OrderItem,
    DishRating, DeliveryRating, Complaint, Compliment, KnowledgeBase,
    DeliveryBid, Address, ForumPost, ForumComment, PostReaction,
    CommentReaction, ForumComplaint, Announcement, KnowledgeBaseRating
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
    
    # Chef and Delivery Person should use Django admin, not frontend dashboard
    if hasattr(user, 'chef') or hasattr(user, 'deliveryperson'):
        return redirect('/admin/')
    
    # Check user type and redirect accordingly
    if hasattr(user, 'customer'):
        return customer_dashboard(request)
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
        items__dish__chef=chef
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
    
    # Get pending forum complaints
    pending_forum_complaints = ForumComplaint.objects.filter(status='pending').count()
    
    # Get recent orders
    recent_orders = Order.objects.order_by('-created_at')[:10]
    
    # Get customer statistics
    total_customers = Customer.objects.count()
    vip_customers = Customer.objects.filter(is_vip=True).count()
    blacklisted_customers = Customer.objects.filter(is_blacklisted=True).count()
    
    # Get recent forum complaints
    recent_forum_complaints = ForumComplaint.objects.filter(status='pending').order_by('-created_at')[:5]
    
    # Get dishes with average ratings
    dishes_with_ratings = Dish.objects.annotate(
        avg_rating=Avg('dishrating__rating')
    ).order_by('-avg_rating')[:10]
    
    context = {
        'manager': manager,
        'pending_complaints': pending_complaints,
        'pending_compliments': pending_compliments,
        'pending_forum_complaints': pending_forum_complaints,
        'recent_orders': recent_orders,
        'total_customers': total_customers,
        'vip_customers': vip_customers,
        'blacklisted_customers': blacklisted_customers,
        'recent_forum_complaints': recent_forum_complaints,
        'dishes_with_ratings': dishes_with_ratings,
    }
    return render(request, 'manager_dashboard.html', context)


def user_login(request):
    """User login view - Only for customers and managers"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Check if user is chef or delivery person - they should use Django admin login
            if hasattr(user, 'chef') or hasattr(user, 'deliveryperson'):
                messages.error(request, 'Chefs and delivery persons must login through the admin panel at /admin/')
                return render(request, 'login.html')
            
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Redirect based on user type
            if hasattr(user, 'customer') or hasattr(user, 'manager'):
                return redirect('dashboard')
            else:
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
    """AI chat functionality with Local Knowledge Base -> RAG LLM Fallback"""
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        
        if not question:
            return JsonResponse({'error': 'Please enter a question.'}, status=400)
        
        # 1. Search Local Knowledge Base
        candidates = KnowledgeBase.objects.filter(is_flagged=False)
        
        best_match = None
        highest_score = 0.0
        threshold = 0.6  # Similarity threshold
        
        # Store candidates with scores for RAG context
        scored_candidates = []
        
        for entry in candidates:
            # Calculate similarity with Question
            q_score = difflib.SequenceMatcher(None, question.lower(), entry.question.lower()).ratio()
            
            # Calculate similarity with Answer (New: Search answer field too)
            a_score = difflib.SequenceMatcher(None, question.lower(), entry.answer.lower()).ratio()
            
            # Use the better match
            base_score = max(q_score, a_score)
            
            # Bonus for keyword presence in Question
            if question.lower() in entry.question.lower():
                base_score += 0.2
            
            final_score = min(base_score, 1.0)
            
            scored_candidates.append((final_score, entry))
            
            if final_score > highest_score:
                highest_score = final_score
                best_match = entry
        
        # Sort candidates by score for RAG context
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # If good local match found (Direct Return)
        if best_match and highest_score >= threshold:
            return JsonResponse({
                'answer': best_match.answer,
                'source': 'local',
                'knowledge_id': best_match.id,
                'score': highest_score
            })
            
        # 2. Fallback to LLM with RAG (Retrieval-Augmented Generation)
        try:
            # Prepare Context from top 3 scored candidates
            context_text = ""
            if scored_candidates:
                top_context = scored_candidates[:3]
                context_items = []
                for score, entry in top_context:
                    # Include context if it has at least some relevance (>0.2)
                    if score > 0.2:
                        context_items.append(f"Q: {entry.question}\nA: {entry.answer}")
                
                if context_items:
                    context_text = "Here is some specific information about our restaurant from our database:\n" + "\n---\n".join(context_items)

            # Prepare Prompt
            system_prompt = "You are a helpful customer service AI for CCTExpress restaurant. Be polite, concise, and helpful."
            
            if context_text:
                rag_instruction = f"{context_text}\n\nUsing the specific information above, answer the following customer question. If the context doesn't answer the question, answer politely based on general restaurant knowledge, but mention you are not sure about specific details."
            else:
                rag_instruction = "Answer the following customer question politely based on general restaurant knowledge. If asking about specific order status or menu items not provided here, ask them to check their dashboard."

            user_prompt = f"{rag_instruction}\n\nCustomer Question: '{question}'"
            
            ollama_response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'llama3:8b',
                    'prompt': f"{system_prompt}\n\n{user_prompt}",
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
                    'answer': "I'm sorry, I cannot connect to the AI service right now. Please try again later.",
                    'source': 'fallback'
                })
        except requests.exceptions.RequestException:
            return JsonResponse({
                'answer': "I'm sorry, I cannot connect to the AI service right now. Please try again later.",
                'source': 'fallback'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'AI chat failed: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rate_answer(request):
    """Rate knowledge base answers (Allows Visitors)"""
    try:
        data = json.loads(request.body)
        knowledge_id = data.get('knowledge_id')
        rating = int(data.get('rating', 0))
        
        if not knowledge_id:
            return JsonResponse({'error': 'Knowledge ID is required.'}, status=400)
        
        try:
            knowledge = KnowledgeBase.objects.get(id=knowledge_id)
        except KnowledgeBase.DoesNotExist:
            return JsonResponse({'error': 'Knowledge entry not found.'}, status=404)
        
        # Get User (Authenticated or Visitor)
        if request.user.is_authenticated:
            user = request.user
        else:
            # Create or get Visitor user for anonymous ratings
            user, created = User.objects.get_or_create(username='Visitor')
            if created:
                user.set_unusable_password()
                user.save()

        # Create or Update rating
        KnowledgeBaseRating.objects.update_or_create(
            user=user,
            knowledge_base=knowledge,
            defaults={'score': rating}
        )
        
        # If rating is 0 (outrageous), flag for manager review
        if rating == 0:
            knowledge.is_flagged = True
            knowledge.save()
            return JsonResponse({
                'message': 'Answer flagged for manager review.',
                'flagged': True
            })
        
        return JsonResponse({
            'message': 'Thank you for your feedback!',
            'flagged': False
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except ValueError:
         return JsonResponse({'error': 'Invalid rating value.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Rating failed: {str(e)}'}, status=500)


@login_required
def profile(request):
    """User profile page"""
    user = request.user
    
    if hasattr(user, 'customer'):
        customer = user.customer
        orders = Order.objects.filter(customer=customer).order_by('-created_at')[:10]
        addresses = Address.objects.filter(customer=customer).order_by('-is_default', '-created_at')
        
        context = {
            'customer': customer,
            'orders': orders,
            'addresses': addresses,
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
                'error': 'Order rejected: Insufficient funds. You have received a warning for reckless ordering.',
                'warning_added': True,
                'warnings': customer.warnings,
                'required_amount': float(total_amount),
                'available_deposit': float(customer.deposit)
            }, status=400, content_type='application/json')
        
        # Get delivery address and memo
        delivery_address = None
        address_id = data.get('address_id')
        memo = data.get('memo', '').strip()
        
        if address_id:
            try:
                delivery_address = Address.objects.get(id=address_id, customer=customer)
            except Address.DoesNotExist:
                return JsonResponse({'error': 'Selected address not found.'}, status=400, content_type='application/json')
        else:
            # Try to get default address
            try:
                delivery_address = Address.objects.get(customer=customer, is_default=True)
            except Address.DoesNotExist:
                # No default address, that's okay
                pass
        
        # Create order
        order = Order.objects.create(
            customer=customer,
            total_amount=total_amount,
            status='pending',
            delivery_address=delivery_address,
            memo=memo
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
    
    # Get customer addresses
    addresses = Address.objects.filter(customer=request.user.customer).order_by('-is_default', '-created_at')
    
    context = {
        'dishes': dishes,
        'total_amount': total_amount,
        'discount': discount,
        'final_amount': total_amount,
        'is_vip': request.user.customer.is_vip,
        'customer': request.user.customer,
        'addresses': addresses
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


# ==================== ORDER DETAIL PAGE ====================

@login_required
def order_detail(request, order_id):
    """Order detail page with status-based display and rating/complaint functionality"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission - only customer who placed the order can view
    if not hasattr(request.user, 'customer') or order.customer != request.user.customer:
        messages.error(request, 'You do not have permission to view this order.')
        return redirect('dashboard')
    
    # Get order items
    order_items = order.items.all()
    
    # Get existing ratings for this order
    dish_ratings_list = []
    delivery_rating = None
    
    if order.status == 'delivered':
        # Get dish ratings for this order
        for item in order_items:
            try:
                rating = DishRating.objects.get(customer=request.user.customer, dish=item.dish)
                dish_ratings_list.append({'dish_id': item.dish.id, 'rating': rating.rating})
            except DishRating.DoesNotExist:
                dish_ratings_list.append({'dish_id': item.dish.id, 'rating': None})
        
        # Get delivery rating
        if order.delivery_person:
            try:
                delivery_rating_obj = DeliveryRating.objects.get(customer=request.user.customer, order=order)
                delivery_rating = delivery_rating_obj.rating
            except DeliveryRating.DoesNotExist:
                delivery_rating = None
        
        # Get existing complaints/compliments for this order to determine available targets
        existing_complaints = Complaint.objects.filter(order=order, complainant=request.user.customer)
        existing_compliments = Compliment.objects.filter(order=order, complimenter=request.user.customer)
        
        # Get used targets (dish IDs and 'delivery')
        used_targets = set()
        for complaint in existing_complaints:
            if complaint.chef:
                # Find which dish this chef made
                for item in order_items:
                    if item.dish.chef == complaint.chef:
                        used_targets.add(f'dish_{item.dish.id}')
            if complaint.delivery_person:
                used_targets.add('delivery')
        
        for compliment in existing_compliments:
            if compliment.chef:
                for item in order_items:
                    if item.dish.chef == compliment.chef:
                        used_targets.add(f'dish_{item.dish.id}')
            if compliment.delivery_person:
                used_targets.add('delivery')
        
        # Calculate max allowed complaints/compliments (n dishes + 1 delivery)
        max_allowed = len(order_items) + (1 if order.delivery_person else 0)
        remaining_allowed = max_allowed - len(used_targets)
        
        # Get available targets (dishes and delivery that haven't been used)
        available_targets = []
        for item in order_items:
            target_key = f'dish_{item.dish.id}'
            if target_key not in used_targets:
                available_targets.append({
                    'type': 'dish',
                    'id': item.dish.id,
                    'name': item.dish.name,
                    'chef': item.dish.chef
                })
        
        if order.delivery_person and 'delivery' not in used_targets:
            available_targets.append({
                'type': 'delivery',
                'id': order.delivery_person.id,
                'name': 'Delivery Service',
                'delivery_person': order.delivery_person
            })
    else:
        available_targets = []
        used_targets = set()
        remaining_allowed = 0
    
    # Get delivery route data if status is out_for_delivery
    route_data = None
    if order.status == 'out_for_delivery' and order.delivery_address:
        # Get coordinates for delivery address
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="restaurant_delivery_system")
        try:
            location = geolocator.geocode(order.delivery_address.get_full_address())
            if location:
                route_data = {
                    'restaurant_coords': [settings.RESTAURANT_LONGITUDE, settings.RESTAURANT_LATITUDE],
                    'delivery_coords': [location.longitude, location.latitude],
                    'restaurant_address': settings.RESTAURANT_ADDRESS,
                    'delivery_address': order.delivery_address.get_full_address()
                }
        except Exception as e:
            print(f"Geocoding error: {e}")
    
    context = {
        'order': order,
        'order_items': order_items,
        'dish_ratings': dish_ratings_list,
        'delivery_rating': delivery_rating,
        'available_targets': available_targets,
        'remaining_allowed': remaining_allowed,
        'route_data': route_data,
    }
    return render(request, 'order_detail.html', context)


# ==================== ADDRESS BOOK MANAGEMENT ====================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_address(request):
    """Add new address to customer's address book"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can add addresses.'}, status=403)
    
    try:
        data = json.loads(request.body)
        recipient_name = data.get('recipient_name', '').strip()
        street_address = data.get('street_address', '').strip()
        city = data.get('city', '').strip()
        state = data.get('state', '').strip()
        zip_code = data.get('zip_code', '').strip()
        country = data.get('country', 'USA').strip()
        phone = data.get('phone', '').strip()
        is_default = data.get('is_default', False)
        
        if not all([recipient_name, street_address, city, state, zip_code]):
            return JsonResponse({'error': 'All required fields must be filled.'}, status=400)
        
        customer = request.user.customer
        
        # If this is set as default, unset other default addresses
        if is_default:
            Address.objects.filter(customer=customer, is_default=True).update(is_default=False)
        
        address = Address.objects.create(
            customer=customer,
            recipient_name=recipient_name,
            street_address=street_address,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            phone=phone,
            is_default=is_default
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Address added successfully.',
            'address_id': address.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to add address: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def edit_address(request, address_id):
    """Edit existing address"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can edit addresses.'}, status=403)
    
    try:
        address = Address.objects.get(id=address_id, customer=request.user.customer)
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Address not found.'}, status=404)
    
    try:
        data = json.loads(request.body)
        recipient_name = data.get('recipient_name', '').strip()
        street_address = data.get('street_address', '').strip()
        city = data.get('city', '').strip()
        state = data.get('state', '').strip()
        zip_code = data.get('zip_code', '').strip()
        country = data.get('country', 'USA').strip()
        phone = data.get('phone', '').strip()
        is_default = data.get('is_default', False)
        
        if not all([recipient_name, street_address, city, state, zip_code]):
            return JsonResponse({'error': 'All required fields must be filled.'}, status=400)
        
        # If this is set as default, unset other default addresses
        if is_default:
            Address.objects.filter(customer=request.user.customer, is_default=True).exclude(id=address_id).update(is_default=False)
        
        address.recipient_name = recipient_name
        address.street_address = street_address
        address.city = city
        address.state = state
        address.zip_code = zip_code
        address.country = country
        address.phone = phone
        address.is_default = is_default
        address.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Address updated successfully.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to update address: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_address(request, address_id):
    """Delete address from address book"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can delete addresses.'}, status=403)
    
    try:
        address = Address.objects.get(id=address_id, customer=request.user.customer)
        address.delete()
        return JsonResponse({
            'success': True,
            'message': 'Address deleted successfully.'
        })
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Address not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete address: {str(e)}'}, status=500)


@login_required
def get_address(request, address_id):
    """Get address details"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can view addresses.'}, status=403)
    
    try:
        address = Address.objects.get(id=address_id, customer=request.user.customer)
        return JsonResponse({
            'success': True,
            'address': {
                'id': address.id,
                'recipient_name': address.recipient_name,
                'street_address': address.street_address,
                'city': address.city,
                'state': address.state,
                'zip_code': address.zip_code,
                'country': address.country,
                'phone': address.phone,
                'is_default': address.is_default
            }
        })
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Address not found.'}, status=404)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def set_default_address(request, address_id):
    """Set address as default"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can set default addresses.'}, status=403)
    
    try:
        address = Address.objects.get(id=address_id, customer=request.user.customer)
        
        # Unset other default addresses
        Address.objects.filter(customer=request.user.customer, is_default=True).exclude(id=address_id).update(is_default=False)
        
        # Set this as default
        address.is_default = True
        address.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Default address updated successfully.'
        })
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Address not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Failed to set default address: {str(e)}'}, status=500)


# ==================== FORUM FUNCTIONALITY ====================

@login_required
def forum(request):
    """Forum page - list all posts"""
    # Only manager and customer can access forum
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        messages.error(request, 'Only customers and managers can access the forum.')
        return redirect('dashboard')
    
    # Get announcements (pinned, shown first)
    announcements = Announcement.objects.filter(is_pinned=True).order_by('-created_at')
    
    posts = ForumPost.objects.all().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'announcements': announcements,
        'posts': page_obj,
        'can_post': True,  # Both manager and customer can post
        'is_manager': hasattr(request.user, 'manager')
    }
    return render(request, 'forum.html', context)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def create_forum_post(request):
    """Create a new forum post"""
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        return JsonResponse({'error': 'Only customers and managers can create posts.'}, status=403)
    
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        allow_comments = data.get('allow_comments', True)
        
        if not title or not content:
            return JsonResponse({'error': 'Title and content are required.'}, status=400)
        
        post = ForumPost.objects.create(
            author=request.user,
            title=title,
            content=content,
            allow_comments=allow_comments
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Post created successfully.',
            'post_id': post.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to create post: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_forum_post(request, post_id):
    """Delete a forum post"""
    try:
        post = ForumPost.objects.get(id=post_id)
        
        # Only author can delete
        if post.author != request.user:
            return JsonResponse({'error': 'You do not have permission to delete this post.'}, status=403)
        
        post.delete()
        return JsonResponse({
            'success': True,
            'message': 'Post deleted successfully.'
        })
    except ForumPost.DoesNotExist:
        return JsonResponse({'error': 'Post not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete post: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_forum_comment(request, post_id):
    """Add a comment to a forum post"""
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        return JsonResponse({'error': 'Only customers and managers can comment.'}, status=403)
    
    try:
        post = ForumPost.objects.get(id=post_id)
        
        if not post.allow_comments:
            return JsonResponse({'error': 'Comments are disabled for this post.'}, status=400)
        
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Comment content is required.'}, status=400)
        
        comment = ForumComment.objects.create(
            post=post,
            author=request.user,
            content=content
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Comment added successfully.',
            'comment_id': comment.id
        })
        
    except ForumPost.DoesNotExist:
        return JsonResponse({'error': 'Post not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to add comment: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_forum_comment(request, comment_id):
    """Delete a forum comment"""
    try:
        comment = ForumComment.objects.get(id=comment_id)
        
        # Only author can delete
        if comment.author != request.user:
            return JsonResponse({'error': 'You do not have permission to delete this comment.'}, status=403)
        
        comment.delete()
        return JsonResponse({
            'success': True,
            'message': 'Comment deleted successfully.'
        })
    except ForumComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete comment: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def toggle_post_reaction(request, post_id):
    """Toggle 👍 or 👎 reaction on a post"""
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        return JsonResponse({'error': 'Only customers and managers can react.'}, status=403)
    
    try:
        post = ForumPost.objects.get(id=post_id)
        data = json.loads(request.body)
        reaction_type = data.get('reaction_type')  # 'approve' or 'disapprove'
        
        if reaction_type not in ['approve', 'disapprove']:
            return JsonResponse({'error': 'Invalid reaction type.'}, status=400)
        
        # Check if user already reacted
        existing_reaction = PostReaction.objects.filter(post=post, user=request.user).first()
        
        if existing_reaction:
            if existing_reaction.reaction_type == reaction_type:
                # Remove reaction if clicking the same reaction
                existing_reaction.delete()
                action = 'removed'
            else:
                # Change reaction type
                existing_reaction.reaction_type = reaction_type
                existing_reaction.save()
                action = 'changed'
        else:
            # Create new reaction
            PostReaction.objects.create(
                post=post,
                user=request.user,
                reaction_type=reaction_type
            )
            action = 'added'
        
        approve_count = post.get_approve_count()
        disapprove_count = post.get_disapprove_count()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'approve_count': approve_count,
            'disapprove_count': disapprove_count
        })
        
    except ForumPost.DoesNotExist:
        return JsonResponse({'error': 'Post not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to toggle reaction: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def toggle_comment_reaction(request, comment_id):
    """Toggle 👍 or 👎 reaction on a comment"""
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        return JsonResponse({'error': 'Only customers and managers can react.'}, status=403)
    
    try:
        comment = ForumComment.objects.get(id=comment_id)
        data = json.loads(request.body)
        reaction_type = data.get('reaction_type')  # 'approve' or 'disapprove'
        
        if reaction_type not in ['approve', 'disapprove']:
            return JsonResponse({'error': 'Invalid reaction type.'}, status=400)
        
        # Check if user already reacted
        existing_reaction = CommentReaction.objects.filter(comment=comment, user=request.user).first()
        
        if existing_reaction:
            if existing_reaction.reaction_type == reaction_type:
                # Remove reaction if clicking the same reaction
                existing_reaction.delete()
                action = 'removed'
            else:
                # Change reaction type
                existing_reaction.reaction_type = reaction_type
                existing_reaction.save()
                action = 'changed'
        else:
            # Create new reaction
            CommentReaction.objects.create(
                comment=comment,
                user=request.user,
                reaction_type=reaction_type
            )
            action = 'added'
        
        approve_count = comment.get_approve_count()
        disapprove_count = comment.get_disapprove_count()
        
        return JsonResponse({
            'success': True,
            'action': action,
            'approve_count': approve_count,
            'disapprove_count': disapprove_count
        })
        
    except ForumComment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to toggle reaction: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def file_forum_complaint(request):
    """File a complaint about a forum post or comment"""
    if not (hasattr(request.user, 'customer') or hasattr(request.user, 'manager')):
        return JsonResponse({'error': 'Only customers and managers can file complaints.'}, status=403)
    
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        comment_id = data.get('comment_id')
        reported_user_id = data.get('reported_user_id')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        
        if not title or not description:
            return JsonResponse({'error': 'Title and description are required.'}, status=400)
        
        if not reported_user_id:
            return JsonResponse({'error': 'Reported user ID is required.'}, status=400)
        
        try:
            reported_user = User.objects.get(id=reported_user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Reported user not found.'}, status=404)
        
        # Get post or comment
        post = None
        comment = None
        if post_id:
            try:
                post = ForumPost.objects.get(id=post_id)
            except ForumPost.DoesNotExist:
                return JsonResponse({'error': 'Post not found.'}, status=404)
        elif comment_id:
            try:
                comment = ForumComment.objects.get(id=comment_id)
                post = comment.post  # Also reference the post
            except ForumComment.DoesNotExist:
                return JsonResponse({'error': 'Comment not found.'}, status=404)
        else:
            return JsonResponse({'error': 'Either post_id or comment_id is required.'}, status=400)
        
        complaint = ForumComplaint.objects.create(
            complainant=request.user,
            post=post,
            comment=comment,
            reported_user=reported_user,
            title=title,
            description=description,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Complaint filed successfully. It will be reviewed by management.',
            'complaint_id': complaint.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to file complaint: {str(e)}'}, status=500)


# ==================== ANNOUNCEMENT MANAGEMENT ====================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def create_announcement(request):
    """Create a new announcement (Manager only)"""
    if not hasattr(request.user, 'manager'):
        return JsonResponse({'error': 'Only managers can create announcements.'}, status=403)
    
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title or not content:
            return JsonResponse({'error': 'Title and content are required.'}, status=400)
        
        # Create announcement
        announcement = Announcement.objects.create(
            author=request.user,
            title=title,
            content=content,
            is_pinned=True
        )
        
        # Add to knowledge base
        KnowledgeBase.objects.create(
            question=f"Announcement: {title}",
            answer=content,
            author=None,  # Announcements don't have customer authors
            is_announcement=True,
            is_flagged=False
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Announcement created successfully and added to knowledge base.',
            'announcement_id': announcement.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to create announcement: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_announcement(request, announcement_id):
    """Update an announcement (Manager only)"""
    if not hasattr(request.user, 'manager'):
        return JsonResponse({'error': 'Only managers can update announcements.'}, status=403)
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
    except Announcement.DoesNotExist:
        return JsonResponse({'error': 'Announcement not found.'}, status=404)
    
    try:
        data = json.loads(request.body)
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title or not content:
            return JsonResponse({'error': 'Title and content are required.'}, status=400)
        
        announcement.title = title
        announcement.content = content
        announcement.save()
        
        # Update knowledge base entry
        kb_entry = KnowledgeBase.objects.filter(
            question__startswith=f"Announcement: {announcement.title}",
            is_announcement=True
        ).first()
        
        if kb_entry:
            kb_entry.question = f"Announcement: {title}"
            kb_entry.answer = content
            kb_entry.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Announcement updated successfully.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to update announcement: {str(e)}'}, status=500)


@login_required
def get_announcement(request, announcement_id):
    """Get announcement details"""
    if not hasattr(request.user, 'manager'):
        return JsonResponse({'error': 'Only managers can view announcement details.'}, status=403)
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        return JsonResponse({
            'success': True,
            'announcement': {
                'id': announcement.id,
                'title': announcement.title,
                'content': announcement.content
            }
        })
    except Announcement.DoesNotExist:
        return JsonResponse({'error': 'Announcement not found.'}, status=404)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def delete_announcement(request, announcement_id):
    """Delete an announcement (Manager only)"""
    if not hasattr(request.user, 'manager'):
        return JsonResponse({'error': 'Only managers can delete announcements.'}, status=403)
    
    try:
        announcement = Announcement.objects.get(id=announcement_id)
        
        # Delete related knowledge base entry
        KnowledgeBase.objects.filter(
            question__startswith=f"Announcement: {announcement.title}",
            is_announcement=True
        ).delete()
        
        announcement.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Announcement deleted successfully.'
        })
    except Announcement.DoesNotExist:
        return JsonResponse({'error': 'Announcement not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Failed to delete announcement: {str(e)}'}, status=500)


# ==================== ORDER RATING AND COMPLAINT/COMPLIMENT ====================

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def rate_dish(request):
    """Rate a dish from an order"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can rate dishes.'}, status=403)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        dish_id = data.get('dish_id')
        rating = int(data.get('rating', 0))
        
        if not order_id or not dish_id or rating < 1 or rating > 5:
            return JsonResponse({'error': 'Invalid rating data.'}, status=400)
        
        order = Order.objects.get(id=order_id, customer=request.user.customer)
        
        if order.status != 'delivered':
            return JsonResponse({'error': 'You can only rate dishes from delivered orders.'}, status=400)
        
        dish = Dish.objects.get(id=dish_id)
        
        # Check if dish is in this order
        if not OrderItem.objects.filter(order=order, dish=dish).exists():
            return JsonResponse({'error': 'This dish is not in this order.'}, status=400)
        
        # Create or update rating
        dish_rating, created = DishRating.objects.get_or_create(
            customer=request.user.customer,
            dish=dish,
            defaults={'rating': rating}
        )
        
        if not created:
            dish_rating.rating = rating
            dish_rating.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Dish rated successfully.'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found.'}, status=404)
    except Dish.DoesNotExist:
        return JsonResponse({'error': 'Dish not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to rate dish: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def rate_delivery(request):
    """Rate delivery service from an order"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can rate delivery.'}, status=403)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        delivery_person_id = data.get('delivery_person_id')
        rating = int(data.get('rating', 0))
        
        if not order_id or not delivery_person_id or rating < 1 or rating > 5:
            return JsonResponse({'error': 'Invalid rating data.'}, status=400)
        
        order = Order.objects.get(id=order_id, customer=request.user.customer)
        
        if order.status != 'delivered':
            return JsonResponse({'error': 'You can only rate delivery from delivered orders.'}, status=400)
        
        if order.delivery_person.id != delivery_person_id:
            return JsonResponse({'error': 'This delivery person is not assigned to this order.'}, status=400)
        
        # Create or update rating
        delivery_rating, created = DeliveryRating.objects.get_or_create(
            customer=request.user.customer,
            order=order,
            defaults={'rating': rating, 'delivery_person': order.delivery_person}
        )
        
        if not created:
            delivery_rating.rating = rating
            delivery_rating.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Delivery rated successfully.'
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to rate delivery: {str(e)}'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def file_order_complaint_compliment(request):
    """File complaint or compliment for an order (dish or delivery)"""
    if not hasattr(request.user, 'customer'):
        return JsonResponse({'error': 'Only customers can file complaints/compliments.'}, status=403)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        target_type = data.get('target_type')  # 'dish' or 'delivery'
        target_id = data.get('target_id')
        complaint_type = data.get('type')  # 'complaint' or 'compliment'
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        
        if not all([order_id, target_type, target_id, complaint_type, title, description]):
            return JsonResponse({'error': 'All fields are required.'}, status=400)
        
        order = Order.objects.get(id=order_id, customer=request.user.customer)
        
        if order.status != 'delivered':
            return JsonResponse({'error': 'You can only file complaints/compliments for delivered orders.'}, status=400)
        
        # Check if max allowed reached
        existing_complaints = Complaint.objects.filter(order=order, complainant=request.user.customer).count()
        existing_compliments = Compliment.objects.filter(order=order, complimenter=request.user.customer).count()
        max_allowed = len(order.items.all()) + (1 if order.delivery_person else 0)
        
        if existing_complaints + existing_compliments >= max_allowed:
            return JsonResponse({'error': 'You have reached the maximum number of complaints/compliments for this order.'}, status=400)
        
        # Check if this target was already used
        chef = None
        delivery_person = None
        
        if target_type == 'dish':
            dish = Dish.objects.get(id=target_id)
            chef = dish.chef
            
            # Check if already filed for this chef
            if complaint_type == 'complaint':
                if Complaint.objects.filter(order=order, complainant=request.user.customer, chef=chef).exists():
                    return JsonResponse({'error': 'You have already filed a complaint/compliment for this dish.'}, status=400)
            else:
                if Compliment.objects.filter(order=order, complimenter=request.user.customer, chef=chef).exists():
                    return JsonResponse({'error': 'You have already filed a complaint/compliment for this dish.'}, status=400)
        elif target_type == 'delivery':
            delivery_person = DeliveryPerson.objects.get(id=target_id)
            
            # Check if already filed for this delivery person
            if complaint_type == 'complaint':
                if Complaint.objects.filter(order=order, complainant=request.user.customer, delivery_person=delivery_person).exists():
                    return JsonResponse({'error': 'You have already filed a complaint/compliment for this delivery service.'}, status=400)
            else:
                if Compliment.objects.filter(order=order, complimenter=request.user.customer, delivery_person=delivery_person).exists():
                    return JsonResponse({'error': 'You have already filed a complaint/compliment for this delivery service.'}, status=400)
        else:
            return JsonResponse({'error': 'Invalid target type.'}, status=400)
        
        # Create complaint or compliment
        if complaint_type == 'complaint':
            complaint = Complaint.objects.create(
                complainant=request.user.customer,
                chef=chef,
                delivery_person=delivery_person,
                order=order,
                title=title,
                description=description,
                status='pending'
            )
            message = 'Complaint filed successfully. It will be reviewed by management.'
        else:  # compliment
            compliment = Compliment.objects.create(
                complimenter=request.user.customer,
                chef=chef,
                delivery_person=delivery_person,
                order=order,
                title=title,
                description=description,
                status='pending'
            )
            message = 'Compliment submitted successfully. It will be reviewed by management.'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found.'}, status=404)
    except Dish.DoesNotExist:
        return JsonResponse({'error': 'Dish not found.'}, status=404)
    except DeliveryPerson.DoesNotExist:
        return JsonResponse({'error': 'Delivery person not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Failed to file complaint/compliment: {str(e)}'}, status=500)
