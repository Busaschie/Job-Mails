from django.core.management.base import BaseCommand
from django.db.models.functions import Lower

from jobs.models import Stellenanzeige


class Command(BaseCommand):
    help = "Markiert Anzeigen mit gleichem Titel/Firma/Ort als Duplikat der aeltesten (nichts wird geloescht)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opt):
        gruppen = {}
        for a in Stellenanzeige.objects.order_by("erstellt_am", "pk"):
            k = (a.titel.strip().lower(), a.firma.strip().lower(), a.ort.strip().lower())
            gruppen.setdefault(k, []).append(a)
        n = 0
        for lst in gruppen.values():
            if len(lst) < 2:
                continue
            # Bevorzugt eine Anzeige mit Bewerbung als Original, sonst die aelteste
            orig = next((a for a in lst if hasattr(a, "bewerbung")), lst[0])
            for a in lst:
                if a.pk != orig.pk and a.duplikat_von_id != orig.pk:
                    n += 1
                    if not opt["dry_run"]:
                        Stellenanzeige.objects.filter(pk=a.pk).update(duplikat_von=orig)
        self.stdout.write(self.style.SUCCESS(f"{n} Duplikat(e) {'gefunden' if opt['dry_run'] else 'markiert'}."))
