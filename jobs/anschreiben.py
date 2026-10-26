"""Anschreiben-Entwurf per LLM aus Profil (profil.md) und Auswertung der Anzeige."""
from django.conf import settings

from .llm import complete_json

SYSTEM = """Du schreibst einen Entwurf für ein Bewerbungsanschreiben auf Deutsch.
Regeln:
- 150 bis 220 Wörter, sachlich und persönlich, keine Floskeln wie "hiermit bewerbe ich mich".
- Nutze AUSSCHLIESSLICH Fakten aus dem BEWERBERPROFIL. Erfinde nichts: keine Zahlen, Projekte, Arbeitgeber, Zertifikate oder Kenntnisse.
- Beziehe dich konkret auf Rolle, Firma und die wichtigsten Anforderungen der Anzeige, soweit das Profil sie stützt.
- Fehlende Anforderungen NICHT behaupten; ehrlich auf verwandte Erfahrung verweisen oder weglassen.
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
