"""Train ML models, save them to ml/models/, and apply them to the CRM."""

import json

from django.core.management.base import BaseCommand, CommandError

from ml import services


class Command(BaseCommand):
    help = "Train models (all by default), then rescore leads and refresh segments/churn."

    def add_arguments(self, parser) -> None:
        # No `choices=`: Python 3.11's argparse rejects an empty nargs="*" list that has choices.
        parser.add_argument(
            "models", nargs="*", help=f"Models to train (default: all): {services.MODEL_NAMES}"
        )

    def handle(self, *args, models: list[str], **options) -> None:
        unknown = sorted(set(models) - set(services.MODEL_NAMES))
        if unknown:
            raise CommandError(f"Unknown model(s): {', '.join(unknown)}")
        results = services.retrain(models or None)
        self.stdout.write(json.dumps(results, indent=2, default=str))
        self.stdout.write(self.style.SUCCESS("Models trained and applied."))
