"""Deliver the durable push outbox without exposing endpoints in logs."""

from django.core.management.base import BaseCommand, CommandError

from starup_backend.notifications.services import dispatch_pending


class Command(BaseCommand):
    help = "Deliver up to 50 pending consented Web Push notifications."

    def handle(self, *args, **options):
        try:
            count = dispatch_pending()
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Delivered {count} notifications.")
