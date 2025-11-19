from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db.models import Count, Avg
from .models import Customer, Order, Complaint, Compliment, Chef, DeliveryPerson


@receiver(post_save, sender=Order)
def update_customer_vip_status(sender, instance, created, **kwargs):
    """Update customer VIP status after order completion"""
    if created and instance.status == 'delivered':
        customer = instance.customer
        
        # Check VIP upgrade conditions
        if not customer.is_vip:
            # Check if customer meets VIP criteria
            if customer.total_spent >= 100 or customer.order_count >= 3:
                # Check for unresolved complaints
                unresolved_complaints = Complaint.objects.filter(
                    complainant=customer,
                    status__in=['pending', 'investigating']
                ).count()
                
                if unresolved_complaints == 0:
                    customer.is_vip = True
                    customer.save()


@receiver(post_save, sender=Complaint)
def handle_customer_warnings(sender, instance, created, **kwargs):
    """Handle customer warnings and VIP downgrade"""
    if created and instance.status == 'resolved' and instance.complainant:
        customer = instance.complainant
        
        # Check if customer should be warned
        if customer.warnings >= 3:
            # Customer should be deregistered
            customer.is_blacklisted = True
            customer.save()
        elif customer.is_vip and customer.warnings >= 2:
            # VIP should be downgraded to regular customer
            customer.is_vip = False
            customer.warnings = 0  # Clear warnings
            customer.save()


@receiver(post_save, sender=Compliment)
def handle_employee_bonus(sender, instance, created, **kwargs):
    """Handle employee bonuses and demotions"""
    if created and instance.status == 'approved':
        # Handle chef bonuses
        if instance.chef:
            chef = instance.chef
            chef.bonus_count += 1
            
            # Check if chef should get bonus (3 compliments)
            if chef.bonus_count >= 3:
                # Give bonus (implement salary increase logic here)
                chef.save()
        
        # Handle delivery person bonuses
        if instance.delivery_person:
            delivery_person = instance.delivery_person
            delivery_person.bonus_count += 1
            
            # Check if delivery person should get bonus (3 compliments)
            if delivery_person.bonus_count >= 3:
                # Give bonus (implement salary increase logic here)
                delivery_person.save()


@receiver(post_save, sender=Complaint)
def handle_employee_demotion(sender, instance, created, **kwargs):
    """Handle employee demotions and firings"""
    if created and instance.status == 'resolved':
        # Handle chef demotions
        if instance.chef:
            chef = instance.chef
            chef.demotion_count += 1
            
            # Check if chef should be demoted (3 complaints or low rating)
            if chef.demotion_count >= 3:
                # Demote chef (implement salary decrease logic here)
                chef.save()
            elif chef.demotion_count >= 2:
                # Fire chef
                chef.is_active = False
                chef.save()
        
        # Handle delivery person demotions
        if instance.delivery_person:
            delivery_person = instance.delivery_person
            delivery_person.demotion_count += 1
            
            # Check if delivery person should be demoted (3 complaints or low rating)
            if delivery_person.demotion_count >= 3:
                # Demote delivery person (implement salary decrease logic here)
                delivery_person.save()
            elif delivery_person.demotion_count >= 2:
                # Fire delivery person
                delivery_person.is_active = False
                delivery_person.save()


def check_employee_ratings():
    """Check employee ratings and apply demotions/bonuses"""
    # Check chefs with low ratings
    chefs_with_low_ratings = Chef.objects.filter(is_active=True).annotate(
        avg_rating=Avg('dish__dishrating__rating')
    ).filter(avg_rating__lt=2)
    
    for chef in chefs_with_low_ratings:
        chef.demotion_count += 1
        if chef.demotion_count >= 2:
            chef.is_active = False
        chef.save()
    
    # Check chefs with high ratings
    chefs_with_high_ratings = Chef.objects.filter(is_active=True).annotate(
        avg_rating=Avg('dish__dishrating__rating')
    ).filter(avg_rating__gt=4)
    
    for chef in chefs_with_high_ratings:
        chef.bonus_count += 1
        chef.save()
    
    # Check delivery persons with low ratings
    delivery_with_low_ratings = DeliveryPerson.objects.filter(is_active=True).annotate(
        avg_rating=Avg('deliveryrating__rating')
    ).filter(avg_rating__lt=2)
    
    for delivery in delivery_with_low_ratings:
        delivery.demotion_count += 1
        if delivery.demotion_count >= 2:
            delivery.is_active = False
        delivery.save()
    
    # Check delivery persons with high ratings
    delivery_with_high_ratings = DeliveryPerson.objects.filter(is_active=True).annotate(
        avg_rating=Avg('deliveryrating__rating')
    ).filter(avg_rating__gt=4)
    
    for delivery in delivery_with_high_ratings:
        delivery.bonus_count += 1
        delivery.save()
