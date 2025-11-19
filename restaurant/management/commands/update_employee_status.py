from django.core.management.base import BaseCommand
from django.db.models import Count, Avg
from restaurant.models import Chef, DeliveryPerson, Complaint, Compliment, DishRating, DeliveryRating


class Command(BaseCommand):
    help = 'Update employee status based on performance, complaints, and compliments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Process chefs
        self.update_chefs(dry_run)
        
        # Process delivery persons
        self.update_delivery_persons(dry_run)
        
        self.stdout.write(self.style.SUCCESS('Employee status update completed'))

    def update_chefs(self, dry_run=False):
        """Update chef status based on performance"""
        self.stdout.write('Processing chefs...')
        
        chefs = Chef.objects.filter(is_active=True)
        
        for chef in chefs:
            # Get chef's performance metrics
            complaints_count = Complaint.objects.filter(
                chef=chef,
                status='resolved'
            ).count()
            
            compliments_count = Compliment.objects.filter(
                chef=chef,
                status='approved'
            ).count()
            
            # Get average rating
            avg_rating = DishRating.objects.filter(
                dish__chef=chef
            ).aggregate(avg=Avg('rating'))['avg'] or 0
            
            # Apply compliment to complaint cancellation (1:1 ratio)
            net_complaints = max(0, complaints_count - compliments_count)
            
            changes_made = []
            
            # Check for demotion conditions
            if net_complaints >= 3 or avg_rating < 2:
                if not dry_run:
                    chef.demotion_count += 1
                    chef.save()
                    changes_made.append(f"Demotion count increased to {chef.demotion_count}")
                else:
                    changes_made.append(f"Demotion count would increase to {chef.demotion_count + 1}")
                
                # Check if should be fired (2 demotions)
                if chef.demotion_count >= 2:
                    if not dry_run:
                        chef.is_active = False
                        chef.save()
                        changes_made.append("Fired due to 2 demotions")
                    else:
                        changes_made.append("Would be fired due to 2 demotions")
            
            # Check for bonus conditions
            elif compliments_count >= 3 or avg_rating > 4:
                if not dry_run:
                    chef.bonus_count += 1
                    chef.save()
                    changes_made.append(f"Bonus count increased to {chef.bonus_count}")
                else:
                    changes_made.append(f"Bonus count would increase to {chef.bonus_count + 1}")
            
            # Log changes
            if changes_made:
                self.stdout.write(f"Chef {chef.user.username}: {', '.join(changes_made)}")
                self.stdout.write(f"  - Complaints: {complaints_count}, Compliments: {compliments_count}")
                self.stdout.write(f"  - Net complaints: {net_complaints}, Avg rating: {avg_rating:.2f}")

    def update_delivery_persons(self, dry_run=False):
        """Update delivery person status based on performance"""
        self.stdout.write('Processing delivery persons...')
        
        delivery_persons = DeliveryPerson.objects.filter(is_active=True)
        
        for delivery in delivery_persons:
            # Get delivery person's performance metrics
            complaints_count = Complaint.objects.filter(
                delivery_person=delivery,
                status='resolved'
            ).count()
            
            compliments_count = Compliment.objects.filter(
                delivery_person=delivery,
                status='approved'
            ).count()
            
            # Get average rating
            avg_rating = DeliveryRating.objects.filter(
                delivery_person=delivery
            ).aggregate(avg=Avg('rating'))['avg'] or 0
            
            # Apply compliment to complaint cancellation (1:1 ratio)
            net_complaints = max(0, complaints_count - compliments_count)
            
            changes_made = []
            
            # Check for demotion conditions
            if net_complaints >= 3 or avg_rating < 2:
                if not dry_run:
                    delivery.demotion_count += 1
                    delivery.save()
                    changes_made.append(f"Demotion count increased to {delivery.demotion_count}")
                else:
                    changes_made.append(f"Demotion count would increase to {delivery.demotion_count + 1}")
                
                # Check if should be fired (2 demotions)
                if delivery.demotion_count >= 2:
                    if not dry_run:
                        delivery.is_active = False
                        delivery.save()
                        changes_made.append("Fired due to 2 demotions")
                    else:
                        changes_made.append("Would be fired due to 2 demotions")
            
            # Check for bonus conditions
            elif compliments_count >= 3 or avg_rating > 4:
                if not dry_run:
                    delivery.bonus_count += 1
                    delivery.save()
                    changes_made.append(f"Bonus count increased to {delivery.bonus_count}")
                else:
                    changes_made.append(f"Bonus count would increase to {delivery.bonus_count + 1}")
            
            # Log changes
            if changes_made:
                self.stdout.write(f"Delivery Person {delivery.user.username}: {', '.join(changes_made)}")
                self.stdout.write(f"  - Complaints: {complaints_count}, Compliments: {compliments_count}")
                self.stdout.write(f"  - Net complaints: {net_complaints}, Avg rating: {avg_rating:.2f}")
