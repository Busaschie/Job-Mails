import os
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

LOCK = settings.BASE_DIR / ".pipeline.lock"
LOCK_MAX_ALTER = 6 * 3600  # veraltete Sperre nach 6 h ignorieren


class Command(BaseCommand):
    help = "Gesamtlauf: Mails scannen/verschieben → Jobs extrahieren → per LLM auswerten."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=40, help="Max. Anzeigen pro Lauf für die LLM-Auswertung")

    def handle(self, *args, **opt):
        if LOCK.exists() and time.time() - LOCK.stat().st_mtime < LOCK_MAX_ALTER:
            raise CommandError("Ein anderer Lauf ist noch aktiv (.pipeline.lock) – übersprungen.")
        LOCK.write_text(str(os.getpid()))
        try:
            for name, kwargs in [
                ("scan_mails", {}),
                ("parse_mails", {}),
                ("extract_jobs", {"aus_mail": True, "limit": opt["limit"]}),
            ]:
                self.stdout.write(self.style.MIGRATE_HEADING(f"== {name} =="))
                try:
                    call_command(name, **kwargs)
                except Exception as e:  # ein Schritt darf die folgenden nicht verhindern
                    self.stderr.write(f"{name} fehlgeschlagen: {e}")
        finally:
            LOCK.unlink(missing_ok=True)
