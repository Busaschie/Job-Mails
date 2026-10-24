import re

from django.conf import settings
from django.core.management.base import BaseCommand

from jobs.llm import complete_json
from jobs.models import Regel, Stellenanzeige

KATEGORIEN = """Kategorie: frontend = Web-Frontend-Entwicklung (HTML, CSS, JavaScript, React/Vue, UX/UI);
vibecoding = KI-gestützte Entwicklung, KI-/LLM-Orchestrierung, Prompting, Automatisierung mit KI-Tools;
pruefung = passt zu keinem von beiden, unklar oder nicht belegbar."""

SYSTEM_VOLL = f"""Du extrahierst Daten aus Stellenanzeigen. Antworte NUR mit einem JSON-Objekt mit genau diesen Schlüsseln:
titel, firma, ort (strings), arbeitsmodell ("remote"|"hybrid"|"vor_ort"|"unbekannt"), anstellungsart (string),
gehalt (string oder null), erfahrung (string oder null), sprachen (Liste), skills (Liste von Technologien/Tools),
aufgaben (Liste, max. 6), anforderungen (Liste, max. 6), benefits (Liste, max. 5),
muss_anforderungen (Liste der harten Muss-Kriterien: Abschluss, Jahre Berufserfahrung, Haupt-Programmiersprache/Stack, Branchenwissen),
bonus (Liste der "Bonus"/"wünschenswert"-Punkte),
kategorie ("frontend"|"vibecoding"|"pruefung"), beleg (wörtliches Zitat aus dem Text, das die Kategorie stützt, sonst ""),
begruendung (ein kurzer Satz),
passung ("passt"|"teilweise"|"unklar"|"ausschluss") im Vergleich zum Bewerberprofil, passung_grund (ein kurzer Satz),
muss_abgleich (Liste von Objekten {{"anforderung": "...", "status": "erfuellt"|"teilweise"|"fehlt", "profil_beleg": "kurze Angabe aus dem Profil oder leer"}}),
ausschluss_art ("abschluss"|"sprache"|"zertifikat"|"hauptstack"|"berufsfeld"|"" wenn kein Ausschluss),
ausschluss_beleg (wörtliches Zitat aus der Anzeige, das den Ausschluss begründet; sonst "").
Passung: ausschluss NUR bei hartem K.-o.-Kriterium: abschluss (geforderter Abschluss/Zertifikat ohne gleichwertige Alternative im Profil),
sprache (Pflichtsprache fehlt), zertifikat, hauptstack (völlig anderer Hauptstack, z. B. Java-Backend, SAP, .NET) oder berufsfeld (ganz anderes Berufsfeld).
Einzelne fehlende Frameworks/Tools oder Jahre in EINER Technologie sind KEIN Ausschluss, sondern "teilweise".
Steht "Studium oder vergleichbare Qualifikation/Ausbildung", gelten Techniker-Abschluss plus langjährige Erfahrung als gleichwertig.
passt = Kernanforderungen decken sich mit dem Profil. teilweise = Rolle passt, aber einzelne Muss-Punkte fehlen. unklar = Text reicht nicht für ein Urteil.
{KATEGORIEN}
Verwende nur Angaben, die im Text stehen. Fehlendes = null bzw. leere Liste. Erfinde nichts."""

SYSTEM_KURZ = f"""Du bekommst nur einen sehr kurzen Auszug einer Stellenanzeige (Titel, Firma, Ort, Kurztext).
Antworte NUR mit einem JSON-Objekt mit genau diesen Schlüsseln:
titel, firma, ort (strings), arbeitsmodell ("remote"|"hybrid"|"vor_ort"|"unbekannt" – nur wenn im Text genannt),
gehalt (string oder null),
kategorie ("frontend"|"vibecoding"|"pruefung"),
beleg (wörtliches Zitat aus dem Text, das die Kategorie stützt; sonst ""),
begruendung (ein kurzer Satz),
passung ("passt"|"teilweise"|"unklar"|"ausschluss") im Vergleich zum Bewerberprofil, passung_grund (ein kurzer Satz),
ausschluss_art ("abschluss"|"sprache"|"zertifikat"|"hauptstack"|"berufsfeld"|"" wenn kein Ausschluss),
ausschluss_beleg (wörtliches Zitat aus dem Text, das den Ausschluss begründet; sonst "").
Passung: ausschluss NUR bei hartem K.-o.-Kriterium: abschluss (geforderter Abschluss/Zertifikat ohne gleichwertige Alternative im Profil),
sprache (Pflichtsprache fehlt), zertifikat, hauptstack (völlig anderer Hauptstack, z. B. Java-Backend, SAP, .NET) oder berufsfeld (ganz anderes Berufsfeld).
Einzelne fehlende Frameworks/Tools oder Jahre in EINER Technologie sind KEIN Ausschluss, sondern "teilweise".
Steht "Studium oder vergleichbare Qualifikation/Ausbildung", gelten Techniker-Abschluss plus langjährige Erfahrung als gleichwertig.
passt = Kernanforderungen decken sich mit dem Profil. teilweise = Rolle passt, aber einzelne Muss-Punkte fehlen. unklar = Text reicht nicht für ein Urteil.
{KATEGORIEN}
Wähle frontend oder vibecoding NUR, wenn im Text ein klarer Hinweis steht und du ihn in "beleg" wörtlich zitieren kannst.
Sonst pruefung. Liefere KEINE Aufgaben, Anforderungen, Skills oder Benefits und erfinde nichts."""


def titel_ausschluss(titel, begriffe):
    """Gibt den ersten Ausschlussbegriff zurück, der als ganzes Wort im Titel steht (Java != JavaScript)."""
    for b in begriffe:
        if re.search(r"(?<![\w+#.])" + re.escape(b) + r"(?![\w+#])", titel, flags=re.I):
            return b
    return ""


def profil():
    try:
        return settings.PROFIL_DATEI.read_text(encoding="utf-8")
    except OSError:
        return ""


def normalisieren(d, quelle, kurz):
    d = dict(d)
    if "begründung" in d:
        d["begruendung"] = d.pop("begründung")
    kat = d.get("kategorie") if d.get("kategorie") in ("frontend", "vibecoding", "pruefung") else "pruefung"
    beleg = (d.get("beleg") or "").strip()
    if kat != "pruefung" and (not beleg or beleg.lower() not in " ".join(quelle.lower().split())):
        d["begruendung"] = f"Kein wörtlicher Beleg im Text (vorgeschlagen: {kat}). " + (d.get("begruendung") or "")
        kat = "pruefung"
    d["kategorie"] = kat
    p = d.get("passung") if d.get("passung") in ("passt", "teilweise", "unklar", "ausschluss") else "unklar"
    if p == "ausschluss" and d.get("ausschluss_art") not in ("abschluss", "sprache", "zertifikat", "hauptstack", "berufsfeld"):
        d["passung_grund"] = "Kein hartes K.-o.-Kriterium -> teilweise. " + (d.get("passung_grund") or "")
        p = "teilweise"
    ab = (d.get("ausschluss_beleg") or "").strip().lower()
    if p == "ausschluss" and (not ab or ab not in " ".join(quelle.lower().split())):
        d["passung_grund"] = "Ausschluss ohne wörtlichen Beleg -> unklar. " + (d.get("passung_grund") or "")
        p = "unklar"
    d["passung"] = p
    d["datenbasis"] = "mail-kurztext" if kurz else "seitentext"
    return d, kat, p


class Command(BaseCommand):
    help = "Anzeigen per LLM auswerten und als JSON speichern."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5)
        parser.add_argument("--aus-mail", action="store_true",
                            help="Auch Anzeigen ohne abgerufene Seite nur aus dem Mail-Kurztext auswerten")
        parser.add_argument("--volltext", action="store_true", help="Nur Anzeigen mit gespeichertem Seitentext")
        parser.add_argument("--suche", default="", help="Nur Anzeigen, deren Titel oder Firma diesen Text enthalten")
        parser.add_argument("--alle", action="store_true", help="Bereits ausgewertete Anzeigen erneut auswerten")

    def handle(self, *args, **opt):
        S = Stellenanzeige.Status
        stati = [S.ABGERUFEN] + ([S.NEU] if opt["aus_mail"] else []) + ([S.AUSGEWERTET] if opt["alle"] else [])
        ok = fail = regel_treffer = 0
        begriffe = list(Regel.objects.filter(aktiv=True, typ=Regel.Typ.NEGATIV).values_list("begriff", flat=True))
        qs = Stellenanzeige.objects.filter(status__in=stati)
        if opt["volltext"]:
            qs = qs.exclude(seitentext="")
        if opt["suche"]:
            from django.db.models import Q
            qs = qs.filter(Q(titel__icontains=opt["suche"]) | Q(firma__icontains=opt["suche"]))
        for a in qs[: opt["limit"]]:
            kurz = not a.seitentext
            treffer = titel_ausschluss(a.titel, begriffe)
            if treffer:
                a.daten = {"passung": "ausschluss", "ausschluss_beleg": treffer, "datenbasis": "regel",
                           "passung_grund": f"Ausschlussbegriff im Titel: {treffer}"}
                a.passung, a.kategorie, a.status, a.fehler = "ausschluss", "pruefung", S.AUSGEWERTET, ""
                a.save()
                regel_treffer += 1
                self.stdout.write(f"{a.titel[:50]} → AUSSCHLUSS (Regel: {treffer})")
                continue
            quelle = a.seitentext or f"{a.titel}\n{a.firma} - {a.ort}\n{a.gehalt}\n{a.snippet}"
            try:
                system = (SYSTEM_KURZ if kurz else SYSTEM_VOLL) + "\n\nBEWERBERPROFIL:\n" + profil()
                d = complete_json(system, quelle)
                a.daten, a.kategorie, a.passung = normalisieren(d, quelle, kurz)
                a.status, a.fehler = S.AUSGEWERTET, ""
                ok += 1
                self.stdout.write(f"{a.titel[:50]} → {a.kategorie} / {a.passung}")
            except Exception as e:
                a.status, a.fehler = S.FEHLER, str(e)[:500]
                fail += 1
                self.stderr.write(f"{a.titel[:50]}: {e}")
            a.save()
        self.stdout.write(self.style.SUCCESS(f"Per LLM: {ok}, per Regel ausgeschlossen: {regel_treffer}, Fehler: {fail}"))
