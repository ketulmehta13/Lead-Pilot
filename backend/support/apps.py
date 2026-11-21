from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "support"
    verbose_name = "Support"

    def ready(self) -> None:
        from . import signals  # noqa: F401  (connects receivers)
