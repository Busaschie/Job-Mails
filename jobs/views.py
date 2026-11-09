import re
from urllib.parse import parse_qs, urlparse

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Stellenanzeige

MAX_ZEICHEN = 12000


def _jk(url):
    q = parse_qs(urlparse(url).query)
    return (q.get("jk") or q.get("vjk") or [""])[0]


def _per_titel(text):
    """Erste Zeile = Seitentitel (h1). Eindeutiger Treffer nach Titel, bei mehreren zusaetzlich Firma im Kopf des Textes."""
    kopf = text[:600].lower()
    titel = re.sub(r"\s*-\s*job post.*$", "", text.split("\n", 1)[0].strip(), flags=re.I).strip()
    if len(titel) < 5:
        return None
    treffer = list(Stellenanzeige.objects.filter(titel__iexact=titel, duplikat_von__isnull=True).order_by("-erstellt_am"))
    if len(treffer) > 1:
        mit_firma = [t for t in treffer if t.firma and t.firma.lower() in kopf]
        treffer = mit_firma or treffer
    return treffer[0] if len(treffer) == 1 or (treffer and treffer[0].firma and treffer[0].firma.lower() in kopf) else None


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
    zugeordnet = ""
    if not a:
        # Werbe-Link aus der Mail (pagead/clk): derselbe "ad"-Parameter steht in der viewjob-URL
        ad = (parse_qs(urlparse(url).query).get("ad") or [""])[0]
        if len(ad) > 40:
            a = Stellenanzeige.objects.filter(url__contains=ad[:80]).first()
            if a:
                zugeordnet = "per Werbe-Link-Kennung"
                a.url = f"https://de.indeed.com/viewjob?jk={jk}"  # ab jetzt direkter Link + passende ID
                a.schluessel = jk
                a.save(update_fields=["url", "schluessel"])
    if not a:
        # Indeed vergibt bei erneut ausgespielten Anzeigen neue IDs: dann ueber Titel (+ Firma) zuordnen
        a = _per_titel(text)
        zugeordnet = "per Titel/Firma"
    if not a:
        return JsonResponse({"ok": False, "fehler": f"Keine Anzeige mit jk={jk} und keine mit passendem Titel in der Datenbank."}, status=404)
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
        "ok": True, "zugeordnet": zugeordnet, "nr": a.pk, "titel": a.titel, "firma": a.firma, "zeichen": len(a.seitentext), "offen": offen,
        "naechste": {"url": naechste.url, "titel": naechste.titel, "firma": naechste.firma} if naechste else None,
    })


@staff_member_required
def anschreiben_download(request, pk):
    """Anschreiben zur Anzeige als Word-Datei: vorhandenen Entwurf nutzen oder per LLM erstellen (?neu=1 = neu erstellen)."""
    from . import anschreiben as modul
    from .llm import RateLimitError

    a = get_object_or_404(Stellenanzeige, pk=pk)
    if not a.anschreiben or request.GET.get("neu"):
        try:
            a.anschreiben = modul.erstelle(a)
        except RateLimitError as e:
            messages.error(request, f"Anschreiben nicht erstellt (Limit): {e}")
            return redirect("admin:jobs_stellenanzeige_change", a.pk)
        except Exception as e:
            messages.error(request, f"Anschreiben nicht erstellt: {str(e)[:200]}")
            return redirect("admin:jobs_stellenanzeige_change", a.pk)
        if not a.anschreiben:
            messages.error(request, "Das Modell hat keinen Text geliefert.")
            return redirect("admin:jobs_stellenanzeige_change", a.pk)
        a.save(update_fields=["anschreiben"])

    name = re.sub(r"[^\w\-]+", "_", f"Anschreiben_{a.firma}_{a.titel}")[:80].strip("_")
    try:
        from .anschreiben_docx import baue
    except ImportError:
        antwort = HttpResponse(a.anschreiben, content_type="text/plain; charset=utf-8")
        antwort["Content-Disposition"] = f'attachment; filename="{name}.txt"'
        return antwort  # Fallback ohne python-docx

    antwort = HttpResponse(
        baue(a, a.anschreiben), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    antwort["Content-Disposition"] = f'attachment; filename="{name}.docx"'
    return antwort
