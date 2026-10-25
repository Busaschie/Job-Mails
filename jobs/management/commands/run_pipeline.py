import os
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobs.models import Mail, PipelineLauf, Stellenanzeige

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
        vorher = (Mail.objects.count(), Stellenanzeige.objects.count(),
                  Stellenanzeige.objects.filter(status="ausgewertet").count(), Stellenanzeige.objects.filter(status="fehler").count())
        lauf = PipelineLauf.objects.create()
        meldungen = []
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
                    self.stderr.write(f"{name} fehlgeschlagen: {e}".encode("ascii", "replace").decode())
                    meldungen.append(f"{name}: {e}"[:300])
        finally:
            nachher = (Mail.objects.count(), Stellenanzeige.objects.count(),
                       Stellenanzeige.objects.filter(status="ausgewertet").count(), Stellenanzeige.objects.filter(status="fehler").count())
            lauf.mails_neu = max(nachher[0] - vorher[0], 0)
            lauf.anzeigen_neu = max(nachher[1] - vorher[1], 0)
            lauf.ausgewertet = max(nachher[2] - vorher[2], 0)
            lauf.fehler = max(nachher[3] - vorher[3], 0)
            lauf.meldung = "\n".join(meldungen)
            lauf.status = PipelineLauf.Status.FEHLER if meldungen or lauf.fehler else PipelineLauf.Status.OK
            lauf.beendet = timezone.now()
            lauf.save()
            LOCK.unlink(missing_ok=True)
