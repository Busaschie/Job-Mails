import re
from urllib.parse import parse_qs, urlparse

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Stellenanzeige

MAX_ZEICHEN = 12000


def _jk(url):
    q = parse_qs(urlparse(url).query)
    return (q.get("jk") or q.get("vjk") or [""])[0]


@staff_member_required
@require_http_methods(["GET", "POST"])
def import_text(request):
    """GET: Seite mit Lesezeichen + Empfang des Textes (aus dem URL-Fragment). POST: Text speichern."""
    if request.method == "GET":
        origin = request.build_absolute_uri("/").rstrip("/")
        js = (
            "javascript:(function(){"
            "var e=document.getElementById('jobDescriptionText')||document.querySelector('main')||document.body;"
            "var h=document.querySelector('h1');"
            "var d={u:location.href,t:((h?h.innerText+'\\n':'')+e.innerText).slice(0," + str(MAX_ZEICHEN) + ")};"
            "window.open('" + origin + "/import/#'+encodeURIComponent(JSON.stringify(d)),'_blank');"
            "})();"
        )
        return render(request, "jobs/import_text.html", {"lesezeichen": js})

    import json
    try:
        daten = json.loads(request.body)
        url, text = daten.get("u", ""), (daten.get("t") or "").strip()
    except (ValueError, AttributeError):
        return JsonResponse({"ok": False, "fehler": "Ungültige Daten."}, status=400)
    jk = _jk(url)
    if not jk or len(text) < 200:
        return JsonResponse({"ok": False, "fehler": "Keine Job-ID in der URL oder Text zu kurz."}, status=400)
    a = Stellenanzeige.objects.filter(schluessel=jk).first()
    if not a:
        return JsonResponse({"ok": False, "fehler": f"Keine Anzeige mit jk={jk} in der Datenbank."}, status=404)
    a.seitentext = re.sub(r"\n{3,}", "\n\n", text)[:MAX_ZEICHEN]
    a.status = Stellenanzeige.Status.ABGERUFEN
    a.fehler = ""
    a.save(update_fields=["seitentext", "status", "fehler"])
    naechste = (
        Stellenanzeige.objects.filter(passung__in=["passt", "teilweise", "unklar"], seitentext="", url__contains="viewjob")
        .exclude(pk=a.pk)
        .order_by("passung", "kategorie", "-erstellt_am")
        .first()
    )
    offen = Stellenanzeige.objects.filter(passung__in=["passt", "teilweise", "unklar"], seitentext="", url__contains="viewjob").exclude(pk=a.pk).count()
    return JsonResponse({
        "ok": True, "titel": a.titel, "firma": a.firma, "zeichen": len(a.seitentext), "offen": offen,
        "naechste": {"url": naechste.url, "titel": naechste.titel, "firma": naechste.firma} if naechste else None,
    })
