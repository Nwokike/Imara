from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from datetime import timedelta
from triage.models import ChatSession, ChatMessage, UserFeedback


class Command(BaseCommand):
    help = 'Prunes old chat sessions, messages, and feedback data based on retention policy (default: 90 days)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to retain data (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)

        self.stdout.write(f"Pruning chat data older than {days} days (before {cutoff_date.date()})...")

        # Prune old messages
        old_messages = ChatMessage.objects.filter(created_at__lt=cutoff_date)
        message_count = old_messages.count()
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would delete {message_count} old messages'))
        else:
            deleted_messages = old_messages.delete()[0]
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_messages} old messages'))

        # Prune old feedback
        old_feedback = UserFeedback.objects.filter(created_at__lt=cutoff_date)
        feedback_count = old_feedback.count()
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would delete {feedback_count} old feedback entries'))
        else:
            deleted_feedback = old_feedback.delete()[0]
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_feedback} old feedback entries'))

        # Prune old sessions (only if they have no messages)
        old_sessions = ChatSession.objects.filter(
            created_at__lt=cutoff_date
        ).annotate(
            message_count=models.Count('messages')
        ).filter(message_count=0)
        
        session_count = old_sessions.count()
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would delete {session_count} old empty sessions'))
        else:
            deleted_sessions = old_sessions.delete()[0]
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_sessions} old empty sessions'))

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No data was actually deleted'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nPruning complete!'))
