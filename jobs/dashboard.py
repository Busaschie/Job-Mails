from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import Bewerbung, Mail, PipelineLauf, Stellenanzeige
from .shortlist import shortlist_basis


def dashboard_callback(request, context):
    ordner = dict(Mail.Ordner.choices)
    nach_ordner = {r["ordner"]: r["n"] for r in Mail.objects.values("ordner").annotate(n=Count("id"))}
    status = dict(Bewerbung.Status.choices)
    nach_status = {r["status"]: r["n"] for r in Bewerbung.objects.values("status").annotate(n=Count("id"))}
    gestern = timezone.now() - timedelta(days=1)
    kat = dict(Stellenanzeige._meta.get_field("kategorie").choices)
    nach_kat = {r["kategorie"]: r["n"] for r in Stellenanzeige.objects.exclude(kategorie="").values("kategorie").annotate(n=Count("id"))}
    context.update(
        {
            "shortlist_anzahl": shortlist_basis(Stellenanzeige.objects.all()).count(),
            "neu_anzeigen": Stellenanzeige.objects.filter(erstellt_am__gte=gestern).count(),
            "neu_mails": Mail.objects.filter(erstellt_am__gte=gestern).count(),
            "kategorie_karten": [(label, nach_kat.get(key, 0)) for key, label in kat.items()],
            "laeufe": PipelineLauf.objects.all()[:5],
            "anzeigen_gesamt": Stellenanzeige.objects.count(),
            "anzeigen_ausgewertet": Stellenanzeige.objects.filter(status="ausgewertet").count(),
            "passung_karten": [(l, Stellenanzeige.objects.filter(passung=k).count()) for k, l in [("passt", "Passt"), ("teilweise", "Teilweise"), ("unklar", "Unklar"), ("ausschluss", "Ausschluss")]],
            "mails_gesamt": Mail.objects.count(),
            "ordner_karten": [(label, nach_ordner.get(key, 0)) for key, label in ordner.items()],
            "status_karten": [(label, nach_status.get(key, 0)) for key, label in status.items()],
            "letzte_bewerbungen": Bewerbung.objects.select_related("anzeige")[:10],
        }
    )
    return context
