from django.apps import AppConfig

class GroceryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'grocery'

    def ready(self):
        import grocery.signals  # noqa: F401
