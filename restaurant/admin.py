from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import (
    Customer, Chef, DeliveryPerson, Manager, Dish, Order, OrderItem,
    DishRating, DeliveryRating, Complaint, Compliment, DiscussionTopic,
    DiscussionPost, KnowledgeBase, DeliveryBid, Address, ForumPost,
    ForumComment, PostReaction, CommentReaction, ForumComplaint, Announcement,
    ComplaintDispute, KnowledgeBaseRating
)


# Custom AdminAuthenticationForm that allows chefs and delivery persons
class CustomAdminAuthenticationForm(AdminAuthenticationForm):
    """Custom admin authentication form that allows chefs and delivery persons"""
    
    def confirm_login_allowed(self, user):
        """
        Allow login if user is staff, superuser, or if user is a chef or delivery person.
        We override the parent method completely to avoid the is_staff check.
        """
        # Call the parent's parent (AuthenticationForm) to check if user is active
        from django.contrib.auth.forms import AuthenticationForm
        AuthenticationForm.confirm_login_allowed(self, user)
        
        # Allow staff and superusers (original behavior)
        if user.is_staff or user.is_superuser:
            return
        
        # Allow chefs and delivery persons
        if hasattr(user, 'chef') or hasattr(user, 'deliveryperson'):
            return
        
        # If none of the above, raise validation error
        raise ValidationError(
            self.error_messages["invalid_login"],
            code="invalid_login",
            params={"username": self.username_field.verbose_name},
        )


# Base Mixin for ModelAdmin to allow chef/delivery person access
class ChefDeliveryPersonMixin:
    """Mixin to allow chefs and delivery persons to view their models"""
    
    def has_module_permission(self, request):
        """Allow chefs and delivery persons to see the module"""
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return True
        return super().has_module_permission(request)
    
    def has_view_permission(self, request, obj=None):
        """Allow chefs and delivery persons to view"""
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return True
        return super().has_view_permission(request, obj)
    
    def has_add_permission(self, request):
        """Default to False for chefs/delivery persons unless overridden"""
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return False
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        """Default to False for chefs/delivery persons unless overridden"""
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Default to False for chefs/delivery persons unless overridden"""
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return False
        return super().has_delete_permission(request, obj)


# Create custom AdminSite with modified permissions
class CustomAdminSite(admin.AdminSite):
    """Custom AdminSite that allows chef and delivery person access"""
    
    login_form = CustomAdminAuthenticationForm
    
    def has_permission(self, request):
        """
        Allow access if user is staff, OR if user is a chef or delivery person
        """
        if not request.user.is_active:
            return False
        
        # Allow staff and superusers (original behavior)
        if request.user.is_staff or request.user.is_superuser:
            return True
        
        # Allow chefs and delivery persons
        if hasattr(request.user, 'chef') or hasattr(request.user, 'deliveryperson'):
            return True
        
        return False
    
    def login(self, request, extra_context=None):
        """
        Override login view to handle chef/delivery person login properly
        """
        from django.contrib.auth.views import LoginView
        from django.urls import reverse
        from django.http import HttpResponseRedirect
        
        # If user is already authenticated and has permission, redirect to index
        if request.user.is_authenticated and self.has_permission(request):
            return HttpResponseRedirect(reverse('admin:index'))
        
        # Use parent login view
        return super().login(request, extra_context)
    


# Create custom admin site instance
# Models will be registered to this site explicitly
custom_admin_site = CustomAdminSite(name='admin')


@admin.register(User, site=custom_admin_site)
class CustomUserAdmin(UserAdmin):
    """Custom User admin with additional fields"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')


@admin.register(Customer, site=custom_admin_site)
class CustomerAdmin(admin.ModelAdmin):
    """Customer management for registration and warnings"""
    list_display = ('user', 'deposit', 'warnings', 'total_spent', 'order_count', 'is_vip', 'is_blacklisted', 'created_at')
    list_filter = ('is_vip', 'is_blacklisted', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'total_spent', 'order_count')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'created_at', 'updated_at')
        }),
        ('Financial Information', {
            'fields': ('deposit', 'total_spent', 'order_count')
        }),
        ('Status Information', {
            'fields': ('is_vip', 'is_blacklisted', 'warnings')
        }),
    )
    actions = ['approve_registration', 'blacklist_customer', 'clear_warnings', 'grant_vip_status']

    def approve_registration(self, request, queryset):
        """Approve customer registration"""
        for customer in queryset:
            customer.is_blacklisted = False
            customer.save()
        self.message_user(request, f"Approved {queryset.count()} customer registrations.")
    approve_registration.short_description = "Approve selected registrations"

    def blacklist_customer(self, request, queryset):
        """Blacklist customers"""
        for customer in queryset:
            customer.is_blacklisted = True
            customer.save()
        self.message_user(request, f"Blacklisted {queryset.count()} customers.")
    blacklist_customer.short_description = "Blacklist selected customers"

    def clear_warnings(self, request, queryset):
        """Clear customer warnings"""
        for customer in queryset:
            customer.warnings = 0
            customer.save()
        self.message_user(request, f"Cleared warnings for {queryset.count()} customers.")
    clear_warnings.short_description = "Clear warnings for selected customers"

    def grant_vip_status(self, request, queryset):
        """Grant VIP status to customers"""
        for customer in queryset:
            customer.is_vip = True
            customer.save()
        self.message_user(request, f"Granted VIP status to {queryset.count()} customers.")
    grant_vip_status.short_description = "Grant VIP status to selected customers"


@admin.register(Chef, site=custom_admin_site)
class ChefAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Chef management for HR functions"""
    list_display = ('user', 'salary', 'demotion_count', 'is_active', 'is_terminated', 'created_at')
    list_filter = ('is_active', 'is_terminated', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'created_at', 'updated_at')
        }),
        ('Employment Information', {
            'fields': ('salary', 'demotion_count', 'is_active', 'is_terminated')
        }),
    )
    actions = ['activate_chef', 'deactivate_chef', 'give_bonus', 'demote_chef', 'fire_chef', 'raise_salary']
    
    def get_readonly_fields(self, request, obj=None):
        """Make salary and demotion_count readonly for chefs viewing their own profile"""
        if obj and request.user == obj.user:
            return self.readonly_fields + ('salary', 'demotion_count', 'is_active', 'is_terminated')
        return self.readonly_fields
    
    def get_queryset(self, request):
        """Filter queryset based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show their own profile
        if hasattr(request.user, 'chef'):
            return qs.filter(user=request.user)
        return qs

    def activate_chef(self, request, queryset):
        """Activate chefs"""
        for chef in queryset:
            chef.is_active = True
            chef.is_terminated = False
            chef.save()
        self.message_user(request, f"Activated {queryset.count()} chefs.")
    activate_chef.short_description = "Activate selected chefs"

    def deactivate_chef(self, request, queryset):
        """Deactivate chefs"""
        for chef in queryset:
            chef.is_active = False
            chef.save()
        self.message_user(request, f"Deactivated {queryset.count()} chefs.")
    deactivate_chef.short_description = "Deactivate selected chefs"

    def give_bonus(self, request, queryset):
        """Give bonus to chefs"""
        for chef in queryset:
            chef.salary += 500
            chef.save()
        self.message_user(request, f"Gave bonus to {queryset.count()} chefs.")
    give_bonus.short_description = "Give bonus to selected chefs"

    def demote_chef(self, request, queryset):
        """Demote chefs"""
        for chef in queryset:
            chef.demotion_count += 1
            chef.salary -= 200
            chef.save()
        self.message_user(request, f"Demoted {queryset.count()} chefs.")
    demote_chef.short_description = "Demote selected chefs"

    def fire_chef(self, request, queryset):
        """Fire chefs"""
        for chef in queryset:
            chef.is_terminated = True
            chef.is_active = False
            chef.save()
        self.message_user(request, f"Fired {queryset.count()} chefs.")
    fire_chef.short_description = "Fire selected chefs"

    def raise_salary(self, request, queryset):
        """Raise salary for chefs"""
        for chef in queryset:
            chef.salary += 300
            chef.save()
        self.message_user(request, f"Raised salary for {queryset.count()} chefs.")
    raise_salary.short_description = "Raise salary for selected chefs"


@admin.register(DeliveryPerson, site=custom_admin_site)
class DeliveryPersonAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Delivery person management for HR functions"""
    list_display = ('user', 'salary', 'demotion_count', 'is_active', 'is_terminated', 'created_at')
    list_filter = ('is_active', 'is_terminated', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_module_permission(self, request):
        """Hide from chefs"""
        if hasattr(request.user, 'chef'):
            return False
        return super().has_module_permission(request)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'created_at', 'updated_at')
        }),
        ('Employment Information', {
            'fields': ('salary', 'demotion_count', 'is_active', 'is_terminated')
        }),
    )
    actions = ['activate_delivery', 'deactivate_delivery', 'give_bonus', 'demote_delivery', 'fire_delivery', 'raise_salary']

    def activate_delivery(self, request, queryset):
        """Activate delivery persons"""
        for delivery in queryset:
            delivery.is_active = True
            delivery.is_terminated = False
            delivery.save()
        self.message_user(request, f"Activated {queryset.count()} delivery persons.")
    activate_delivery.short_description = "Activate selected delivery persons"

    def deactivate_delivery(self, request, queryset):
        """Deactivate delivery persons"""
        for delivery in queryset:
            delivery.is_active = False
            delivery.save()
        self.message_user(request, f"Deactivated {queryset.count()} delivery persons.")
    deactivate_delivery.short_description = "Deactivate selected delivery persons"

    def give_bonus(self, request, queryset):
        """Give bonus to delivery persons"""
        for delivery in queryset:
            delivery.salary += 300
            delivery.save()
        self.message_user(request, f"Gave bonus to {queryset.count()} delivery persons.")
    give_bonus.short_description = "Give bonus to selected delivery persons"

    def demote_delivery(self, request, queryset):
        """Demote delivery persons"""
        for delivery in queryset:
            delivery.demotion_count += 1
            delivery.salary -= 150
            delivery.save()
        self.message_user(request, f"Demoted {queryset.count()} delivery persons.")
    demote_delivery.short_description = "Demote selected delivery persons"

    def fire_delivery(self, request, queryset):
        """Fire delivery persons"""
        for delivery in queryset:
            delivery.is_terminated = True
            delivery.is_active = False
            delivery.save()
        self.message_user(request, f"Fired {queryset.count()} delivery persons.")
    fire_delivery.short_description = "Fire selected delivery persons"

    def raise_salary(self, request, queryset):
        """Raise salary for delivery persons"""
        for delivery in queryset:
            delivery.salary += 200
            delivery.save()
        self.message_user(request, f"Raised salary for {queryset.count()} delivery persons.")
    raise_salary.short_description = "Raise salary for selected delivery persons"


@admin.register(Manager, site=custom_admin_site)
class ManagerAdmin(admin.ModelAdmin):
    """Manager management"""
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at',)


@admin.register(Dish, site=custom_admin_site)
class DishAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Dish management"""
    list_display = ('name', 'price', 'chef', 'average_rating', 'is_vip_only', 'is_available', 'created_at')
    list_filter = ('is_vip_only', 'is_available', 'chef', 'created_at')
    search_fields = ('name', 'description', 'chef__user__username')
    readonly_fields = ('created_at', 'updated_at', 'average_rating')
    
    def average_rating(self, obj):
        """Calculate and display average rating"""
        avg = obj.get_average_rating()
        return f"{avg:.2f}" if avg else "N/A"
    average_rating.short_description = 'Average Rating'
    
    def has_add_permission(self, request):
        """Allow chefs to add dishes"""
        if hasattr(request.user, 'chef'):
            return True
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        """Allow chefs to change dishes"""
        if hasattr(request.user, 'chef'):
            return True
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Allow chefs to delete dishes"""
        if hasattr(request.user, 'chef'):
            return True
        return super().has_delete_permission(request, obj)
    
    def get_queryset(self, request):
        """Filter dishes based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show their own dishes
        if hasattr(request.user, 'chef'):
            return qs.filter(chef=request.user.chef)
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        """Make chef field readonly for chefs"""
        if hasattr(request.user, 'chef'):
            return self.readonly_fields + ('chef',)
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Auto-assign chef on save"""
        if not obj.pk and hasattr(request.user, 'chef'):
            obj.chef = request.user.chef
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        """Hide chef field for chefs"""
        form = super().get_form(request, obj, **kwargs)
        if hasattr(request.user, 'chef'):
            if 'chef' in form.base_fields:
                form.base_fields['chef'].disabled = True
                form.base_fields['chef'].initial = request.user.chef
        return form


@admin.register(Order, site=custom_admin_site)
class OrderAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Order management"""
    list_display = ('id', 'customer', 'status', 'total_amount', 'vip_discount', 'delivery_person', 'memo_short', 'created_at')
    list_filter = ('status', 'created_at', 'customer__is_vip')
    search_fields = ('customer__user__username', 'customer__user__email', 'memo')
    readonly_fields = ('created_at', 'updated_at', 'customer', 'total_amount', 'vip_discount', 'memo')
    list_editable = ('status',)
    actions = ['set_status_pending', 'set_status_confirmed', 'set_status_ready', 'set_status_out_for_delivery', 'set_status_delivered', 'set_status_cancelled']
    
    def memo_short(self, obj):
        """Truncate memo for list display"""
        return (obj.memo[:30] + '...') if obj.memo and len(obj.memo) > 30 else obj.memo
    memo_short.short_description = "Memo"

    def get_queryset(self, request):
        """Filter orders based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show orders with their dishes
        if hasattr(request.user, 'chef'):
            return qs.filter(items__dish__chef=request.user.chef).distinct()
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        """Make status editable for chefs on their orders"""
        readonly = list(self.readonly_fields)
        if obj and hasattr(request.user, 'chef'):
            # Chef can change status from pending to confirmed or ready
            if obj.status == 'pending' and obj.items.filter(dish__chef=request.user.chef).exists():
                return readonly  # Allow status change
        return readonly
    
    def get_list_editable(self, request):
        """Allow chefs to edit status in list view"""
        if hasattr(request.user, 'chef'):
            return ('status',)
        return self.list_editable
    
    def set_status_pending(self, request, queryset):
        """Set selected orders to pending"""
        queryset.update(status='pending')
        self.message_user(request, f"Set {queryset.count()} orders to pending.")
    set_status_pending.short_description = "Set status to Pending"
    
    def set_status_confirmed(self, request, queryset):
        """Set selected orders to confirmed"""
        queryset.update(status='confirmed')
        self.message_user(request, f"Set {queryset.count()} orders to confirmed.")
    set_status_confirmed.short_description = "Set status to Confirmed"
    
    def set_status_ready(self, request, queryset):
        """Set selected orders to ready"""
        queryset.update(status='ready')
        self.message_user(request, f"Set {queryset.count()} orders to ready.")
    set_status_ready.short_description = "Set status to Ready"
    
    def set_status_out_for_delivery(self, request, queryset):
        """Set selected orders to out for delivery"""
        queryset.update(status='out_for_delivery')
        self.message_user(request, f"Set {queryset.count()} orders to out for delivery.")
    set_status_out_for_delivery.short_description = "Set status to Out for Delivery"
    
    def set_status_delivered(self, request, queryset):
        """Set selected orders to delivered"""
        queryset.update(status='delivered')
        self.message_user(request, f"Set {queryset.count()} orders to delivered.")
    set_status_delivered.short_description = "Set status to Delivered"
    
    def set_status_cancelled(self, request, queryset):
        """Set selected orders to cancelled"""
        queryset.update(status='cancelled')
        self.message_user(request, f"Set {queryset.count()} orders to cancelled.")
    set_status_cancelled.short_description = "Set status to Cancelled"


@admin.register(OrderItem, site=custom_admin_site)
class OrderItemAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Order item management"""
    list_display = ('order', 'dish', 'quantity', 'price', 'order_status', 'chef_actions')
    list_filter = ('order__status', 'dish__chef')
    search_fields = ('order__customer__user__username', 'dish__name')
    readonly_fields = ('order', 'dish', 'quantity', 'price')
    
    def order_status(self, obj):
        """Display order status"""
        return obj.order.get_status_display()
    order_status.short_description = 'Order Status'
    
    def chef_actions(self, obj):
        """Display action buttons for chef"""
        return format_html(
            '<a class="button" href="/admin/restaurant/order/{}/change/">View Order</a>',
            obj.order.id
        )
    chef_actions.short_description = 'Actions'
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist to handle status changes"""
        if 'status' in request.GET and 'order_id' in request.GET:
            order_id = request.GET.get('order_id')
            new_status = request.GET.get('status')
            try:
                order = Order.objects.get(id=order_id)
                if hasattr(request.user, 'chef') and order.items.filter(dish__chef=request.user.chef).exists():
                    if new_status == 'confirmed':
                        order.status = 'confirmed'
                        order.save()
                        self.message_user(request, f"Order #{order_id} status changed to Confirmed.")
                    elif new_status == 'ready':
                        order.status = 'ready'
                        order.save()
                        self.message_user(request, f"Order #{order_id} status changed to Ready.")
            except Order.DoesNotExist:
                pass
        return super().changelist_view(request, extra_context)
    
    def get_queryset(self, request):
        """Filter order items based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show order items for their dishes
        if hasattr(request.user, 'chef'):
            return qs.filter(dish__chef=request.user.chef)
        return qs


@admin.register(DishRating, site=custom_admin_site)
class DishRatingAdmin(admin.ModelAdmin):
    """Dish rating management"""
    list_display = ('customer', 'dish', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__user__username', 'dish__name')
    readonly_fields = ('created_at',)


@admin.register(DeliveryRating, site=custom_admin_site)
class DeliveryRatingAdmin(admin.ModelAdmin):
    """Delivery rating management"""
    list_display = ('customer', 'delivery_person', 'order', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__user__username', 'delivery_person__user__username')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        """Disable add permission - ratings should only be created by customers"""
        return False


@admin.register(Complaint, site=custom_admin_site)
class ComplaintAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Complaint management"""
    list_display = ('title', 'complainant', 'chef', 'delivery_person', 'status', 'has_dispute', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'complainant__user__username', 'description')
    readonly_fields = ('created_at', 'updated_at', 'disputes_display')
    actions = ['investigate_complaint', 'resolve_complaint', 'dismiss_complaint']
    
    def has_add_permission(self, request):
        """Disable add permission - complaints should only be created by customers"""
        return False
    
    def has_dispute(self, obj):
        """Check if complaint has dispute"""
        return obj.disputes.exists()
    has_dispute.boolean = True
    has_dispute.short_description = 'Has Dispute'
    
    def disputes_display(self, obj):
        """Display disputes for this complaint"""
        disputes = obj.disputes.all()
        if disputes:
            html = '<ul>'
            for dispute in disputes:
                html += f'<li><strong>{dispute.disputer.username}</strong> ({dispute.created_at.strftime("%Y-%m-%d %H:%M")}): {dispute.response[:100]}...</li>'
            html += '</ul>'
            return format_html(html)
        return 'No disputes'
    disputes_display.short_description = 'Disputes'
    
    def get_queryset(self, request):
        """Filter complaints based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show complaints about their dishes
        if hasattr(request.user, 'chef'):
            return qs.filter(chef=request.user.chef, order__isnull=False)
        return qs
    
    def get_readonly_fields(self, request, obj=None):
        """Make most fields readonly for chefs"""
        if obj and hasattr(request.user, 'chef'):
            return self.readonly_fields + ('title', 'description', 'complainant', 'chef', 'delivery_person', 'order', 'status', 'manager_response')
        return self.readonly_fields
    
    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on user type"""
        if obj and hasattr(request.user, 'chef'):
            # Chef view - readonly fields with dispute option
            return (
                ('Complaint Information', {
                    'fields': ('title', 'description', 'complainant', 'order', 'status', 'created_at', 'updated_at')
                }),
                ('Disputes', {
                    'fields': ('disputes_display',)
                }),
            )
        else:
            # Manager view - full access
            return (
                ('Complaint Information', {
                    'fields': ('title', 'description', 'complainant', 'chef', 'delivery_person', 'order', 'status', 'created_at', 'updated_at')
                }),
                ('Manager Response', {
                    'fields': ('manager_response',)
                }),
                ('Disputes', {
                    'fields': ('disputes_display',)
                }),
            )
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Override changeform to add dispute form for chefs"""
        extra_context = extra_context or {}
        if object_id and hasattr(request.user, 'chef'):
            try:
                complaint = Complaint.objects.get(id=object_id, chef=request.user.chef)
                extra_context['can_dispute'] = True
                extra_context['has_dispute'] = complaint.disputes.filter(disputer=request.user).exists()
                extra_context['dispute_url'] = f'/admin/restaurant/complaintdispute/{complaint.id}/dispute/'
            except Complaint.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def get_urls(self):
        """Add custom URLs for dispute creation"""
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('<int:complaint_id>/dispute/', self.admin_site.admin_view(self.add_dispute), name='restaurant_complaint_dispute'),
        ]
        return custom_urls + urls
    
    def add_dispute(self, request, complaint_id):
        """Handle dispute creation"""
        complaint = get_object_or_404(Complaint, id=complaint_id)
        
        # Check if user is the chef for this complaint
        if not hasattr(request.user, 'chef') or complaint.chef != request.user.chef:
            messages.error(request, 'You do not have permission to dispute this complaint.')
            return redirect('admin:restaurant_complaint_changelist')
        
        # Check if dispute already exists
        if ComplaintDispute.objects.filter(complaint=complaint, disputer=request.user).exists():
            messages.warning(request, 'You have already disputed this complaint.')
            return redirect('admin:restaurant_complaint_change', complaint.id)
        
        if request.method == 'POST':
            response_text = request.POST.get('response', '').strip()
            if not response_text:
                messages.error(request, 'Dispute response cannot be empty.')
            else:
                ComplaintDispute.objects.create(
                    complaint=complaint,
                    disputer=request.user,
                    response=response_text
                )
                messages.success(request, 'Dispute submitted successfully.')
                return redirect('admin:restaurant_complaint_change', complaint.id)
        
        return render(request, 'admin/restaurant/complaint/dispute_form.html', {
            'complaint': complaint,
            'opts': self.model._meta,
            'has_view_permission': True,
        })
    
    def investigate_complaint(self, request, queryset):
        """Mark complaints as investigating"""
        for complaint in queryset:
            complaint.status = 'investigating'
            complaint.save()
        self.message_user(request, f"Marked {queryset.count()} complaints as investigating.")
    investigate_complaint.short_description = "Mark as investigating"

    def resolve_complaint(self, request, queryset):
        """Resolve complaints"""
        for complaint in queryset:
            complaint.status = 'resolved'
            complaint.save()
        self.message_user(request, f"Resolved {queryset.count()} complaints.")
    resolve_complaint.short_description = "Resolve selected complaints"

    def dismiss_complaint(self, request, queryset):
        """Dismiss complaints"""
        for complaint in queryset:
            complaint.status = 'dismissed'
            complaint.save()
        self.message_user(request, f"Dismissed {queryset.count()} complaints.")
    dismiss_complaint.short_description = "Dismiss selected complaints"


@admin.register(Compliment, site=custom_admin_site)
class ComplimentAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Compliment management"""
    list_display = ('title', 'complimenter', 'chef', 'delivery_person', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'complimenter__user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        """Disable add permission - compliments should only be created by customers"""
        return False
    
    def get_queryset(self, request):
        """Filter compliments based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show compliments about their dishes
        if hasattr(request.user, 'chef'):
            return qs.filter(chef=request.user.chef, order__isnull=False)
        return qs


@admin.register(DiscussionTopic, site=custom_admin_site)
class DiscussionTopicAdmin(admin.ModelAdmin):
    """Discussion topic management"""
    list_display = ('title', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'author__user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DiscussionPost, site=custom_admin_site)
class DiscussionPostAdmin(admin.ModelAdmin):
    """Discussion post management"""
    list_display = ('topic', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'author__user__username', 'topic__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(KnowledgeBase, site=custom_admin_site)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    """Knowledge base management"""
    list_display = ('question', 'author', 'source_type', 'source_id', 'is_flagged', 'created_at')
    list_filter = ('is_flagged', 'source_type', 'created_at')
    search_fields = ('question', 'answer', 'author__username')
    readonly_fields = ('created_at', 'updated_at', 'source_type', 'source_id')


@admin.register(KnowledgeBaseRating, site=custom_admin_site)
class KnowledgeBaseRatingAdmin(admin.ModelAdmin):
    """Knowledge base rating management"""
    list_display = ('knowledge_base', 'user', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('knowledge_base__question', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(DeliveryBid, site=custom_admin_site)
class DeliveryBidAdmin(ChefDeliveryPersonMixin, admin.ModelAdmin):
    """Delivery bid management with automatic selection"""
    list_display = ('delivery_person', 'order', 'bid_amount', 'is_selected', 'created_at')
    list_filter = ('is_selected', 'created_at')
    search_fields = ('delivery_person__user__username', 'order__customer__user__username')
    readonly_fields = ('created_at',)
    actions = ['auto_select_lowest_bid', 'select_bids', 'deselect_bids']
    
    def has_module_permission(self, request):
        """Hide from chefs"""
        if hasattr(request.user, 'chef'):
            return False
        return super().has_module_permission(request)

    def auto_select_lowest_bid(self, request, queryset):
        """Automatically select the lowest bid for each order"""
        from django.db.models import Min
        
        orders_processed = 0
        for order in queryset.values_list('order', flat=True).distinct():
            order_bids = queryset.filter(order_id=order)
            if order_bids.exists():
                order_bids.update(is_selected=False)
                
                lowest_bid = order_bids.order_by('bid_amount', 'created_at').first()
                if lowest_bid:
                    lowest_bid.is_selected = True
                    lowest_bid.justification = "Automatically selected as lowest bid"
                    lowest_bid.save()
                    orders_processed += 1
        
        self.message_user(request, f"Automatically selected lowest bids for {orders_processed} orders.")
    auto_select_lowest_bid.short_description = "Auto-select lowest bids"

    def select_bids(self, request, queryset):
        """Manually select bids"""
        for bid in queryset:
            bid.is_selected = True
            bid.save()
        self.message_user(request, f"Selected {queryset.count()} bids.")
    select_bids.short_description = "Select selected bids"

    def deselect_bids(self, request, queryset):
        """Deselect bids"""
        for bid in queryset:
            bid.is_selected = False
            bid.save()
        self.message_user(request, f"Deselected {queryset.count()} bids.")
    deselect_bids.short_description = "Deselect selected bids"


@admin.register(Address, site=custom_admin_site)
class AddressAdmin(admin.ModelAdmin):
    """Address management"""
    list_display = ('customer', 'recipient_name', 'city', 'state', 'is_default', 'created_at')
    list_filter = ('is_default', 'city', 'state', 'created_at')
    search_fields = ('customer__user__username', 'recipient_name', 'street_address', 'city')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ForumPost, site=custom_admin_site)
class ForumPostAdmin(admin.ModelAdmin):
    """Forum post management"""
    list_display = ('title', 'author', 'allow_comments', 'created_at')
    list_filter = ('allow_comments', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ForumComment, site=custom_admin_site)
class ForumCommentAdmin(admin.ModelAdmin):
    """Forum comment management"""
    list_display = ('post', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'author__username', 'post__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PostReaction, site=custom_admin_site)
class PostReactionAdmin(admin.ModelAdmin):
    """Post reaction management"""
    list_display = ('post', 'user', 'reaction_type', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('post__title', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(CommentReaction, site=custom_admin_site)
class CommentReactionAdmin(admin.ModelAdmin):
    """Comment reaction management"""
    list_display = ('comment', 'user', 'reaction_type', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('comment__content', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(Announcement, site=custom_admin_site)
class AnnouncementAdmin(admin.ModelAdmin):
    """Announcement management (Manager only)"""
    list_display = ('title', 'author', 'is_pinned', 'created_at')
    list_filter = ('is_pinned', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        """Only managers can see announcements"""
        qs = super().get_queryset(request)
        if not hasattr(request.user, 'manager'):
            return qs.none()
        return qs
    
    def has_add_permission(self, request):
        """Only managers can add announcements"""
        return hasattr(request.user, 'manager')
    
    def has_change_permission(self, request, obj=None):
        """Only managers can change announcements"""
        return hasattr(request.user, 'manager')
    
    def has_delete_permission(self, request, obj=None):
        """Only managers can delete announcements"""
        return hasattr(request.user, 'manager')


@admin.register(ComplaintDispute, site=custom_admin_site)
class ComplaintDisputeAdmin(admin.ModelAdmin):
    """Complaint dispute management"""
    list_display = ('complaint', 'disputer', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('complaint__title', 'disputer__username', 'response')
    readonly_fields = ('created_at', 'updated_at', 'complaint', 'disputer', 'response')
    
    def get_queryset(self, request):
        """Filter disputes based on user type"""
        qs = super().get_queryset(request)
        # If user is a chef, only show disputes they created
        if hasattr(request.user, 'chef'):
            return qs.filter(disputer=request.user)
        return qs
    
    def has_add_permission(self, request):
        """Disable add permission - disputes should be created via complaint detail page"""
        return False


@admin.register(ForumComplaint, site=custom_admin_site)
class ForumComplaintAdmin(admin.ModelAdmin):
    """Forum complaint management"""
    list_display = ('title', 'complainant', 'reported_user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'complainant__username', 'reported_user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['investigate_complaint', 'resolve_complaint_with_warning', 'dismiss_complaint']
    
    def has_add_permission(self, request):
        """Disable add permission - complaints should only be created by users"""
        return False

    def investigate_complaint(self, request, queryset):
        """Mark complaints as investigating"""
        for complaint in queryset:
            complaint.status = 'investigating'
            complaint.save()
        self.message_user(request, f"Marked {queryset.count()} complaints as investigating.")
    investigate_complaint.short_description = "Mark as investigating"

    def resolve_complaint_with_warning(self, request, queryset):
        """Resolve complaints and add warning to reported user"""
        warnings_added = 0
        for complaint in queryset:
            complaint.status = 'resolved'
            complaint.save()
            
            # Add warning to reported user if they are a customer
            try:
                reported_customer = Customer.objects.get(user=complaint.reported_user)
                reported_customer.warnings += 1
                reported_customer.save()
                warnings_added += 1
            except Customer.DoesNotExist:
                pass  # User is not a customer, skip warning
        
        self.message_user(request, f"Resolved {queryset.count()} complaints and added warnings to {warnings_added} users.")
    resolve_complaint_with_warning.short_description = "Resolve and add warning to reported user"

    def dismiss_complaint(self, request, queryset):
        """Dismiss complaints"""
        for complaint in queryset:
            complaint.status = 'dismissed'
            complaint.save()
        self.message_user(request, f"Dismissed {queryset.count()} complaints.")
    dismiss_complaint.short_description = "Dismiss selected complaints"