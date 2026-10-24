"""Prüft, wie viele Indeed-Anzeigen auch in der Jobbörse der Bundesagentur für Arbeit stehen (nur Anzeige, kein Speichern)."""
import difflib
import time

import requests
from django.core.management.base import BaseCommand

from jobs.models import Stellenanzeige

BASIS = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
PFADE = ["/pc/v6/jobs", "/pc/v4/app/jobs", "/pc/v4/jobs"]
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}  # öffentlicher Schlüssel der Schnittstelle (bundesAPI)


def feld(eintrag, *teile):
    """Erster Textwert, dessen Schlüssel einen der Teile enthält (v6-Felder sind nicht stabil benannt)."""
    for k, v in eintrag.items():
        if isinstance(v, str) and any(t in k.lower() for t in teile):
            return v
    return ""


def aehnlich(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


class Command(BaseCommand):
    help = "Trefferquote Indeed-Anzeigen in der Bundesagentur-Jobbörse prüfen."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **opt):
        treffer = geprueft = 0
        for a in Stellenanzeige.objects.exclude(firma="").order_by("?")[: opt["limit"]]:
            geprueft += 1
            was = " ".join(a.titel.split()[:5])
            stellen, fehler = None, ""
            for pfad in ([self.pfad] if getattr(self, "pfad", None) else PFADE):
                try:
                    r = requests.get(BASIS + pfad, headers=HEADERS, timeout=20,
                                     params={"was": was, "size": 50})
                    r.raise_for_status()
                    daten = r.json()
                    stellen = daten.get("ergebnisliste") or daten.get("stellenangebote") or daten.get("jobs") or daten.get("results") or []
                    if not stellen and not getattr(self, "_dbg", False):
                        self._dbg = True
                        self.stdout.write(f"DIAGNOSE Schlüssel: {list(daten)[:10]} | maxErgebnisse={daten.get('maxErgebnisse')} | Auszug: {str(daten)[:300]}")
                    if not getattr(self, "pfad", None):
                        self.pfad = pfad
                        self.stdout.write(f"Schnittstelle erreichbar über {pfad}")
                    break
                except Exception as e:
                    fehler = str(e)[:150]
            if stellen is None:
                self.stderr.write(f"{a.titel[:40]}: {fehler}")
                continue
            gut = [s for s in stellen if aehnlich(feld(s, "firma", "arbeitgeber"), a.firma) > 0.8]
            if stellen and not getattr(self, "_dbg2", False):
                self._dbg2 = True
                self.stdout.write(f"Felder je Eintrag: {sorted(stellen[0])[:25]}")
            treffer += bool(gut)
            self.stdout.write(f"{'✔' if gut else '✘'} {a.titel[:45]} – {a.firma[:30]} ({len(stellen)} Kandidaten)")
            time.sleep(2.5)
        self.stdout.write(self.style.SUCCESS(f"Treffer: {treffer} von {geprueft}"))
