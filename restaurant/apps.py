from django.apps import AppConfig


class RestaurantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurant'
    
    def ready(self):
        import restaurant.signals
        try:
            from .admin import custom_admin_site
            print(f"DEBUG: Registry keys: {[m.__name__ for m in custom_admin_site._registry.keys()]}")
        except Exception as e:
            print(f"DEBUG: Error accessing admin site: {e}")
