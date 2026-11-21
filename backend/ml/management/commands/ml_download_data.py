"""Download the public training datasets into ml/data/raw/."""

from django.core.management.base import BaseCommand

from ml.pipelines import datasets


class Command(BaseCommand):
    help = "Download the public datasets used to train the ML models."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--force", action="store_true", help="Re-download existing files.")

    def handle(self, *args, force: bool, **options) -> None:
        for key, info in datasets.DATASETS.items():
            self.stdout.write(f"- {key}: {info['about']}")
        for path in datasets.download(force=force):
            self.stdout.write(
                self.style.SUCCESS(f"  {path.name} ({path.stat().st_size // 1024} KB)")
            )
