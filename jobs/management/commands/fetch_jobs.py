import random
import time

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from jobs.models import Stellenanzeige

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml",
}
MAX_ZEICHEN = 12000


def seitentext(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    h1 = soup.find("h1")
    beschr = soup.find(id="jobDescriptionText")
    teile = [h1.get_text(" ", strip=True)] if h1 else []
    teile.append((beschr or soup.body or soup).get_text("\n", strip=True))
    return "\n".join(teile)[:MAX_ZEICHEN]


class Command(BaseCommand):
    help = "Seiten der Stellenanzeigen (Status 'neu') abrufen und Text speichern."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)
        parser.add_argument("--retry", action="store_true", help="Auch Anzeigen mit Status Fehler erneut versuchen")
        parser.add_argument("--delay", type=float, default=4.0, help="Basis-Pause zwischen Abrufen (s)")

    def handle(self, *args, **opt):
        qs = Stellenanzeige.objects.filter(status=Stellenanzeige.Status.NEU, url__contains="viewjob")
        if opt["retry"]:
            qs = Stellenanzeige.objects.filter(status__in=[Stellenanzeige.Status.NEU, Stellenanzeige.Status.FEHLER], url__contains="viewjob")
        qs = qs[: opt["limit"]]
        ok = fail = 0
        for a in qs:
            try:
                r = requests.get(a.url, headers=HEADERS, timeout=30)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                text = seitentext(r.text)
                if len(text) < 200 or "captcha" in r.text.lower()[:5000] or "just a moment" in r.text.lower()[:2000]:
                    raise RuntimeError("Seite leer oder durch Captcha/Bot-Schutz blockiert")
                a.seitentext, a.status, a.fehler = text, Stellenanzeige.Status.ABGERUFEN, ""
                ok += 1
            except Exception as e:
                a.status, a.fehler = Stellenanzeige.Status.FEHLER, str(e)[:500]
                fail += 1
                self.stderr.write(f"{a.titel[:50]}: {e}")
                if "HTTP 403" in str(e) or "blockiert" in str(e):
                    a.save()
                    self.stderr.write("Bot-Schutz erkannt – Abbruch, um keine Sperre zu riskieren.")
                    break
            a.save()
            time.sleep(opt["delay"] + random.random() * 3)
        self.stdout.write(self.style.SUCCESS(f"Abgerufen: {ok}, Fehler: {fail}"))
