"""Anschreiben-Entwurf per LLM aus Profil (profil.md) und Auswertung der Anzeige."""
from django.conf import settings

from .llm import complete_json

SYSTEM = """Du schreibst einen Entwurf für ein Bewerbungsanschreiben auf Deutsch.
Regeln:
- Kurz und prägnant, sachlich und persönlich, keine Floskeln wie "hiermit bewerbe ich mich".
- Nutze AUSSCHLIESSLICH Fakten aus dem BEWERBERPROFIL. Erfinde nichts: keine Zahlen, Projekte, Arbeitgeber, Zertifikate oder Kenntnisse.
- Beziehe dich konkret auf Rolle, Firma und die wichtigsten Anforderungen der Anzeige, soweit das Profil sie stützt.
- WAHRHEIT UND ZUORDNUNG: Jede Aussage über Aufgaben, Rollen oder Verantwortung gehört genau zu der Station, unter der sie im Profil steht. Vermische nie Stationen, Skills oder Aufgaben, fasse sie nicht zusammen und schreibe einer Station nichts zu, was dort nicht steht (z. B. keine technische Leitung bei einem Arbeitgeber, bei dem sie nicht belegt ist).
- Formuliere nah am Wortlaut des Profils. Keine Ausschmückungen, keine eigenen Schlussfolgerungen und keine Sätze wie "entspricht den Anforderungen", "korrespondiert mit" oder "ideal für Ihre Stelle".
- Das Anschreiben darf NICHT wie eine Wiederholung des Lebenslaufs klingen: keine Aufzählung von Aufgaben je Station.
- Aufbau (ein Absatz pro Punkt, 200 bis 260 Wörter insgesamt): (1) Einstieg: warum die Stelle interessiert, nur aus der Anzeige ableitbar, keine erfundenen Aussagen über die Firma. (2) Rahmen in EINEM Satz: die drei letzten Stationen nur mit Arbeitgeber und Rolle, ohne Aufgabenlisten: Sky Deutschland (2017-2023), NewMoove (2012-2017), Garmin (2007-2012); die Druckerei nie. (3) Passung: zwei bis drei Sätze dazu, welche Anforderungen der Anzeige das Profil belegt; wähle dafür die passendste Station oder die allgemeinen Skills und nenne nur dort belegte Aufgaben, ohne die Stationen zu verbinden. (4) Weiterbildung und aktuelle Projekte als eigener Absatz (siehe unten). (5) Schluss: Wunsch nach einem Gespräch; deutschlandweite Umzugsbereitschaft darf erwähnt werden.
- Internationale Zusammenarbeit gab es NUR bei Garmin (Global Webteam, Österreich/Polen); nie bei Sky oder NewMoove. NewMoove wurde später von Fitness First übernommen: das ist nur eine Zusatzangabe zu NewMoove; schreibe nie, jemand sei "durch Fitness First" verantwortlich gewesen. Allgemeine Skills (HTML, CSS, JavaScript, PHP, CMS usw.) nenne ohne Stationszuordnung, außer das Profil nennt sie bei der Station.
- Kompetenzen, die im Profil nicht belegt sind, werden im Anschreiben GAR NICHT erwähnt (weder behauptet noch als "lerne ich schnell" oder "verwandte Erfahrung" umschrieben).
- Beachte die Hinweise im Abschnitt "NUR FÜR ANSCHREIBEN" des Profils (z. B. Stationen, die nicht erwähnt werden dürfen).
- KI-Agentensysteme (Flowise, n8n, LLM-Orchestrierung) und Vibe-Coding NICHT als Argument für die ausgeschriebene Stelle verwenden, solange die Anzeige sie nicht selbst verlangt (sonst ist es irreführend). Keine Aussagen wie "diese Kompetenzen ermöglichen ... in Ihrem Umfeld".
- Stattdessen ein eigener kurzer Absatz, sachlich und ohne Bezug zur Stelle: aktuelle Weiterbildung (KI-Manager) und aktuelle Projekte aus dem Profil, dabei KI-Agentensysteme und Vibe-Coding nennen. Nur Fakten aus dem Profil; gibt es keine Projekte im Profil, nur die Weiterbildung nennen.
- Verlangt die Anzeige selbst KI, Automatisierung oder Vibe-Coding, dürfen diese Punkte im Hauptteil als Passung stehen.
- Keine Adresse, kein Gehalt, keine Anrede mit erfundenem Namen: "Sehr geehrte Damen und Herren,".
- Am Ende "Mit freundlichen Grüßen" und die Zeile "[Dein Name]".
Antworte NUR mit einem JSON-Objekt: {"anschreiben": "<Text mit Zeilenumbrüchen>"}."""


def _profil():
    try:
        return settings.PROFIL_DATEI.read_text(encoding="utf-8")
    except OSError:
        return ""


def _anzeigentext(a):
    d = a.daten or {}
    teile = [f"Titel: {a.titel}", f"Firma: {a.firma}", f"Ort: {a.ort}"]
    if a.seitentext:
        teile.append("ANZEIGENTEXT:\n" + a.seitentext[:6000])
    else:
        teile.append("KURZTEXT:\n" + (a.snippet or ""))
    abgleich = [z for z in (d.get("muss_abgleich") or []) if isinstance(z, dict)]
    if abgleich:
        teile.append("ABGLEICH MIT PROFIL (für die Gewichtung):\n" + "\n".join(
            f"- {z.get('anforderung', '')}: {z.get('status', '')} {z.get('profil_beleg', '')}".strip() for z in abgleich))
    return "\n\n".join(teile)


def erstelle(a):
    """Gibt den Entwurf als Text zurück (RateLimitError/Fehler werden nicht abgefangen)."""
    d = complete_json(SYSTEM + "\n\nBEWERBERPROFIL:\n" + _profil(), _anzeigentext(a))
    return str(d.get("anschreiben", "")).strip()
