"""Bewerbungsverlauf: Status + Datum + Notiz buchen und anzeigen."""
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Bewerbung, BewerbungEreignis


def buche(bewerbung, alter_status, datum=None, notiz=""):
    """Legt einen Verlaufseintrag an, wenn sich der Status geaendert hat (oder neu) oder eine Notiz vorliegt."""
    notiz = (notiz or "").strip()
    if alter_status == bewerbung.status and not notiz:
        return None
    return BewerbungEreignis.objects.create(
        bewerbung=bewerbung, datum=datum or timezone.localdate(), status=bewerbung.status, notiz=notiz)


def verlauf_html(bewerbung):
    if bewerbung is None or not bewerbung.pk:
        return "–"
    zeilen = []
    for n, e in enumerate(bewerbung.ereignisse.all()):
        notiz = f"<div style='white-space:pre-wrap;margin:.1rem 0 .5rem 0'>{escape(e.notiz)}</div>" if e.notiz else ""
        link = reverse("admin:jobs_bewerbungereignis_change", args=[e.pk])
        linie = "border-top:1px solid rgba(128,128,128,.45);padding-top:.7rem;" if n else ""
        zeilen.append(f"<div style='margin:.7rem 0 0;{linie}'><strong>{e.datum:%d.%m.%Y}</strong> &middot; {escape(e.get_status_display())}"
                      f" &middot; <a href='{link}' style='opacity:.7;text-decoration:underline'>bearbeiten</a>{notiz}</div>")
    return mark_safe("".join(zeilen)) if zeilen else "–"
