from django.apps import AppConfig


class GenaiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "genai"
    verbose_name = "Generative AI"

    def ready(self) -> None:
        from . import signals  # noqa: F401  (connects receivers)
