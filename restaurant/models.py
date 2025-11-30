from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Customer(models.Model):
    """Customer model extending Django's built-in User model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="User")
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Deposit")
    warnings = models.PositiveIntegerField(default=0, verbose_name="Warnings")
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Total Spent")
    order_count = models.PositiveIntegerField(default=0, verbose_name="Order Count")
    is_vip = models.BooleanField(default=False, verbose_name="VIP Status")
    is_blacklisted = models.BooleanField(default=False, verbose_name="Blacklisted")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Registration Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ({'VIP' if self.is_vip else 'Regular Customer'})"

    def check_vip_status(self):
        """Check and update VIP status"""
        if self.total_spent >= 100 or self.order_count >= 3:
            self.is_vip = True
            self.save()
        return self.is_vip


class Chef(models.Model):
    """Chef model for restaurant employees"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="User")
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=3000.00, verbose_name="Salary")
    demotion_count = models.PositiveIntegerField(default=0, verbose_name="Demotion Count")
    bonus_count = models.PositiveIntegerField(default=0, verbose_name="Bonus Count")
    is_active = models.BooleanField(default=True, verbose_name="Active Status")
    is_terminated = models.BooleanField(default=False, verbose_name="Terminated")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Hire Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Chef"
        verbose_name_plural = "Chefs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} (Chef)"

    def get_average_rating(self):
        """Calculate average rating for chef's dishes"""
        from django.db.models import Avg
        return DishRating.objects.filter(dish__chef=self).aggregate(Avg('rating'))['rating__avg'] or 0

    def get_complaint_count(self):
        """Get total complaint count"""
        return Complaint.objects.filter(chef=self, status='pending').count()

    def get_compliment_count(self):
        """Get total compliment count"""
        return Compliment.objects.filter(chef=self, status='pending').count()


class DeliveryPerson(models.Model):
    """Delivery person model for restaurant employees"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="User")
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=2500.00, verbose_name="Salary")
    demotion_count = models.PositiveIntegerField(default=0, verbose_name="Demotion Count")
    bonus_count = models.PositiveIntegerField(default=0, verbose_name="Bonus Count")
    is_active = models.BooleanField(default=True, verbose_name="Active Status")
    is_terminated = models.BooleanField(default=False, verbose_name="Terminated")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Hire Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Delivery Person"
        verbose_name_plural = "Delivery People"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} (Delivery)"

    def get_average_rating(self):
        """Calculate average delivery rating"""
        from django.db.models import Avg
        return DeliveryRating.objects.filter(delivery_person=self).aggregate(Avg('rating'))['rating__avg'] or 0

    def get_complaint_count(self):
        """Get total complaint count"""
        return Complaint.objects.filter(delivery_person=self, status='pending').count()

    def get_compliment_count(self):
        """Get total compliment count"""
        return Compliment.objects.filter(delivery_person=self, status='pending').count()


class Manager(models.Model):
    """Manager model for restaurant management"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="User")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Hire Date")

    class Meta:
        verbose_name = "Manager"
        verbose_name_plural = "Managers"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} (Manager)"


class Dish(models.Model):
    """Dish model for restaurant menu items"""
    name = models.CharField(max_length=200, verbose_name="Dish Name")
    description = models.TextField(verbose_name="Description")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price")
    image = models.ImageField(upload_to='dishes/', blank=True, null=True, verbose_name="Image")
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, verbose_name="Chef")
    is_vip_only = models.BooleanField(default=False, verbose_name="VIP Only")
    is_available = models.BooleanField(default=True, verbose_name="Available")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Dish"
        verbose_name_plural = "Dishes"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - ${self.price}"

    def get_average_rating(self):
        """Calculate average rating for the dish"""
        from django.db.models import Avg
        return DishRating.objects.filter(dish=self).aggregate(Avg('rating'))['rating__avg'] or 0

    def get_rating_count(self):
        """Get total rating count"""
        return DishRating.objects.filter(dish=self).count()


class Order(models.Model):
    """Order model for customer orders"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Customer")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Amount")
    vip_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="VIP Discount")
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Delivery Person")
    delivery_address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Delivery Address")
    memo = models.TextField(blank=True, null=True, verbose_name="Order Memo", help_text="Customer special requests")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Delivered Time")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Order Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.customer.user.username} - ${self.total_amount}"

    def get_final_amount(self):
        """Calculate final amount after VIP discount"""
        return self.total_amount - self.vip_discount


class OrderItem(models.Model):
    """Order item model for individual items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Order")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name="Dish")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantity")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price")

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.dish.name} x {self.quantity} - ${self.price}"

    def get_total(self):
        """Calculate total for this item"""
        return self.quantity * self.price


class DishRating(models.Model):
    """Dish rating model for customer ratings"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Customer")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name="Dish")
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Rating"
    )
    review = models.TextField(blank=True, verbose_name="Review")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Rating Time")

    class Meta:
        verbose_name = "Dish Rating"
        verbose_name_plural = "Dish Ratings"
        unique_together = ['customer', 'dish']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.user.username} rated {self.dish.name} {self.rating}/5"


class DeliveryRating(models.Model):
    """Delivery rating model for delivery service ratings"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Customer")
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.CASCADE, verbose_name="Delivery Person")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Order")
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Rating"
    )
    review = models.TextField(blank=True, verbose_name="Review")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Rating Time")

    class Meta:
        verbose_name = "Delivery Rating"
        verbose_name_plural = "Delivery Ratings"
        unique_together = ['customer', 'order']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.user.username} rated {self.delivery_person.user.username} {self.rating}/5"


class Complaint(models.Model):
    """Complaint model for user complaints"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    complainant = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='complaints_made', verbose_name="Complainant")
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Chef")
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Delivery Person")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='complaints_received', verbose_name="Customer")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Order")
    title = models.CharField(max_length=200, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    manager_response = models.TextField(blank=True, verbose_name="Manager Response")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Complaint Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Complaint"
        verbose_name_plural = "Complaints"
        ordering = ['-created_at']

    def __str__(self):
        return f"Complaint: {self.title} - {self.complainant.user.username}"


class ComplaintDispute(models.Model):
    """Complaint dispute model for chef/delivery person responses"""
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='disputes', verbose_name="Complaint")
    disputer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Disputer")
    response = models.TextField(verbose_name="Dispute Response")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dispute Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Complaint Dispute"
        verbose_name_plural = "Complaint Disputes"
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute for Complaint #{self.complaint.id} by {self.disputer.username}"


class Compliment(models.Model):
    """Compliment model for user compliments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('dismissed', 'Dismissed'),
    ]

    complimenter = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='compliments_made', verbose_name="Complimenter")
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Chef")
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Delivery Person")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='compliments_received', verbose_name="Customer")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Order")
    title = models.CharField(max_length=200, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    manager_response = models.TextField(blank=True, verbose_name="Manager Response")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Compliment Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Compliment"
        verbose_name_plural = "Compliments"
        ordering = ['-created_at']

    def __str__(self):
        return f"Compliment: {self.title} - {self.complimenter.user.username}"


class DiscussionTopic(models.Model):
    """Discussion topic model for forum discussions"""
    title = models.CharField(max_length=200, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    author = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Author")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Discussion Topic"
        verbose_name_plural = "Discussion Topics"
        ordering = ['-created_at']

    def __str__(self):
        return f"Topic: {self.title} - {self.author.user.username}"


class DiscussionPost(models.Model):
    """Discussion post model for forum posts"""
    topic = models.ForeignKey(DiscussionTopic, on_delete=models.CASCADE, related_name='posts', verbose_name="Topic")
    author = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="Author")
    content = models.TextField(verbose_name="Content")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Post Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Discussion Post"
        verbose_name_plural = "Discussion Posts"
        ordering = ['created_at']

    def __str__(self):
        return f"Post by {self.author.user.username} in {self.topic.title}"


class KnowledgeBase(models.Model):
    """Knowledge base model for AI customer service"""
    SOURCE_TYPES = [
        ('manual', 'Manual Entry'),
        ('announcement', 'Announcement'),
        ('post', 'Forum Post'),
    ]

    question = models.CharField(max_length=500, verbose_name="Question")
    answer = models.TextField(verbose_name="Answer")
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Author")
    is_announcement = models.BooleanField(default=False, verbose_name="Is Announcement")
    is_flagged = models.BooleanField(default=False, verbose_name="Flagged")
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='manual', verbose_name="Source Type")
    source_id = models.IntegerField(null=True, blank=True, verbose_name="Source ID")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Knowledge Base Item"
        verbose_name_plural = "Knowledge Base Items"
        ordering = ['-created_at']

    def __str__(self):
        return f"Q: {self.question[:50]}..."

class KnowledgeBaseRating(models.Model):
    """Rating for Knowledge Base items"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User")
    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name='ratings', verbose_name="Knowledge Base Item")
    score = models.IntegerField(choices=[(i, i) for i in range(6)], verbose_name="Score (0-5)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Rating Time")

    class Meta:
        verbose_name = "Knowledge Base Rating"
        verbose_name_plural = "Knowledge Base Ratings"
        ordering = ['-created_at']
        unique_together = ['user', 'knowledge_base']

    def __str__(self):
        return f"{self.user.username} rated {self.score} for KB#{self.knowledge_base.id}"



class Announcement(models.Model):
    """Announcement model for Forum announcements (managed by manager)"""
    title = models.CharField(max_length=200, verbose_name="Title")
    content = models.TextField(verbose_name="Content")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Author")
    is_pinned = models.BooleanField(default=True, verbose_name="Pinned")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"Announcement: {self.title}"


class DeliveryBid(models.Model):
    """Delivery bid model for competitive delivery"""
    delivery_person = models.ForeignKey(DeliveryPerson, on_delete=models.CASCADE, verbose_name="Delivery Person")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Order")
    bid_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Bid Amount")
    is_selected = models.BooleanField(default=False, verbose_name="Selected")
    justification = models.TextField(blank=True, verbose_name="Manager Justification")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Bid Time")

    class Meta:
        verbose_name = "Delivery Bid"
        verbose_name_plural = "Delivery Bids"
        ordering = ['bid_amount', 'created_at']

    def __str__(self):
        return f"{self.delivery_person.user.username} bid ${self.bid_amount} for Order #{self.order.id}"


class Address(models.Model):
    """Address model for customer address book"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses', verbose_name="Customer")
    recipient_name = models.CharField(max_length=100, verbose_name="Recipient Name")
    street_address = models.CharField(max_length=200, verbose_name="Street Address")
    city = models.CharField(max_length=100, verbose_name="City")
    state = models.CharField(max_length=100, verbose_name="State/Province")
    zip_code = models.CharField(max_length=20, verbose_name="ZIP/Postal Code")
    country = models.CharField(max_length=100, default="USA", verbose_name="Country")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Phone Number")
    is_default = models.BooleanField(default=False, verbose_name="Default Address")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.recipient_name} - {self.street_address}, {self.city}"

    def get_full_address(self):
        """Get full formatted address"""
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}, {self.country}"


class ForumPost(models.Model):
    """Forum post model for manager and customer posts"""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts', verbose_name="Author")
    title = models.CharField(max_length=200, verbose_name="Title")
    content = models.TextField(verbose_name="Content")
    allow_comments = models.BooleanField(default=True, verbose_name="Allow Comments")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Forum Post"
        verbose_name_plural = "Forum Posts"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.author.username}"

    def get_approve_count(self):
        """Get total approve (👍) count"""
        return self.post_reactions.filter(reaction_type='approve').count()

    def get_disapprove_count(self):
        """Get total disapprove (👎) count"""
        return self.post_reactions.filter(reaction_type='disapprove').count()

    def can_delete(self, user):
        """Check if user can delete this post"""
        return self.author == user


class ForumComment(models.Model):
    """Forum comment model for post replies"""
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='comments', verbose_name="Post")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_comments', verbose_name="Author")
    content = models.TextField(verbose_name="Content")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Forum Comment"
        verbose_name_plural = "Forum Comments"
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"

    def get_approve_count(self):
        """Get total approve (👍) count"""
        return self.comment_reactions.filter(reaction_type='approve').count()

    def get_disapprove_count(self):
        """Get total disapprove (👎) count"""
        return self.comment_reactions.filter(reaction_type='disapprove').count()

    def can_delete(self, user):
        """Check if user can delete this comment"""
        return self.author == user


class PostReaction(models.Model):
    """Post reaction model for 👍 and 👎"""
    REACTION_CHOICES = [
        ('approve', '👍 Approve'),
        ('disapprove', '👎 Disapprove'),
    ]

    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='post_reactions', verbose_name="Post")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User")
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES, verbose_name="Reaction Type")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")

    class Meta:
        verbose_name = "Post Reaction"
        verbose_name_plural = "Post Reactions"
        unique_together = ['post', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} {self.get_reaction_type_display()} {self.post.title}"


class CommentReaction(models.Model):
    """Comment reaction model for 👍 and 👎"""
    REACTION_CHOICES = [
        ('approve', '👍 Approve'),
        ('disapprove', '👎 Disapprove'),
    ]

    comment = models.ForeignKey(ForumComment, on_delete=models.CASCADE, related_name='comment_reactions', verbose_name="Comment")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User")
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES, verbose_name="Reaction Type")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")

    class Meta:
        verbose_name = "Comment Reaction"
        verbose_name_plural = "Comment Reactions"
        unique_together = ['comment', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} {self.get_reaction_type_display()} comment #{self.comment.id}"


class ForumComplaint(models.Model):
    """Forum complaint model for reporting posts or comments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    complainant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_complaints_made', verbose_name="Complainant")
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, null=True, blank=True, related_name='forum_complaints', verbose_name="Post")
    comment = models.ForeignKey(ForumComment, on_delete=models.CASCADE, null=True, blank=True, related_name='forum_complaints', verbose_name="Comment")
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_complaints_received', verbose_name="Reported User")
    title = models.CharField(max_length=200, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    manager_response = models.TextField(blank=True, verbose_name="Manager Response")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Complaint Time")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        verbose_name = "Forum Complaint"
        verbose_name_plural = "Forum Complaints"
        ordering = ['-created_at']

    def __str__(self):
        return f"Forum Complaint: {self.title} - Reported by {self.complainant.username}"


