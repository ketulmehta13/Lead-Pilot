from django.apps import AppConfig


class MlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ml"
    verbose_name = "Machine Learning"

    def ready(self) -> None:
        from . import signals  # noqa: F401  (connects receivers)
