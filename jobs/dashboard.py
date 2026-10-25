from django.db.models import Count

from .models import Bewerbung, Mail, Stellenanzeige


def dashboard_callback(request, context):
    ordner = dict(Mail.Ordner.choices)
    nach_ordner = {r["ordner"]: r["n"] for r in Mail.objects.values("ordner").annotate(n=Count("id"))}
    status = dict(Bewerbung.Status.choices)
    nach_status = {r["status"]: r["n"] for r in Bewerbung.objects.values("status").annotate(n=Count("id"))}
    context.update(
        {
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
