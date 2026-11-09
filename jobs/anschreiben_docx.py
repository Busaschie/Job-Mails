"""Anschreiben als Word-Datei im Design des Lebenslaufs (Teal-Kopfband, Calibri, Abschnitts-Linien).

Kopfdaten (Name, Titelzeile, Kontaktzeilen) stehen NICHT im Code, sondern in der lokalen Datei briefkopf.md
(in .gitignore, wird nie an ein LLM gesendet). Format, eine Angabe pro Zeile:
    Name: Vorname Nachname
    Titel: Senior IT- & Webentwickler | Business Analyst | KI & Automation
    Zeile1: Ort | Telefon | E-Mail
    Zeile2: LinkedIn | GitHub
"""
import io
import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TEAL = "1F4E5F"
HELL = "D9E6EA"
TEXT = "222222"

STANDARD = {
    "name": "[]",
    #"titel": "[]",
    "zeile1": "[]",
    "zeile2": "",
}


def kopfdaten():
    daten = dict(STANDARD)
    pfad = Path(getattr(settings, "BRIEFKOPF_DATEI", settings.BASE_DIR / "briefkopf.md"))
    try:
        for zeile in pfad.read_text(encoding="utf-8").splitlines():
            #m = re.match(r"^\s*(name|titel|zeile1|zeile2)\s*:\s*(.*)$", zeile, re.I)
            m = re.match(r"^\s*(name|zeile1|zeile2)\s*:\s*(.*)$", zeile, re.I)
            if m:
                daten[m.group(1).lower()] = m.group(2).strip()
    except OSError:
        pass
    return daten


def _rgb(hexwert):
    return RGBColor.from_string(hexwert)


def _run(p, text, groesse, farbe, fett=False, abstand=None):
    r = p.add_run(text)
    r.font.name = "Calibri"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    r.font.size = Pt(groesse)
    r.font.color.rgb = _rgb(farbe)
    r.bold = fett
    if abstand:
        sp = OxmlElement("w:spacing")
        sp.set(qn("w:val"), str(abstand))
        r._element.rPr.append(sp)
    return r


def _abstaende(p, davor=0, danach=0, zeilen=None):
    f = p.paragraph_format
    f.space_before, f.space_after = Pt(davor), Pt(danach)
    if zeilen:
        f.line_spacing = zeilen


def _zelle(zelle, fill=None, oben=0, links=0, unten=0, rechts=0):
    tcPr = zelle._tc.get_or_add_tcPr()
    if fill:
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)
    mar = OxmlElement("w:tcMar")
    for seite, wert in (("top", oben), ("start", links), ("bottom", unten), ("end", rechts)):
        e = OxmlElement(f"w:{seite}")
        e.set(qn("w:w"), str(wert))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tcPr.append(mar)


def _linie_unten(p):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "6"), ("space", "4"), ("color", TEAL)):
        b.set(qn(f"w:{k}"), v)
    bdr.append(b)
    pPr.append(bdr)


def baue(anzeige, text):
    """Gibt die .docx als Bytes zurueck."""
    k = kopfdaten()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = sec.top_margin = Cm(0)
    sec.bottom_margin = Cm(1.5)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    # Tabelle ueber die ganze Seitenbreite: Zeile 1 = Kopfband, Zeile 2 = Inhalt
    tab = doc.add_table(rows=2, cols=1)
    tab.autofit = False
    tab.columns[0].width = Cm(21.0)
    for z in tab.rows:
        z.cells[0].width = Cm(21.0)
    kopf, inhalt = tab.rows[0].cells[0], tab.rows[1].cells[0]
    _zelle(kopf, fill=TEAL, oben=260, links=400, unten=260, rechts=400)
    _zelle(inhalt, oben=300, links=620, unten=300, rechts=620)

    p = kopf.paragraphs[0]
    _run(p, k["name"], 15, "FFFFFF", fett=True, abstand=10)
    _abstaende(p, 0, 8)
    for schluessel, davor in (("zeile1", 0), ("zeile2", 3)):
        if k[schluessel]:
            p = kopf.add_paragraph()
            _run(p, k[schluessel], 9, "FFFFFF")
            _abstaende(p, davor, 0)

    # Anschrift + Datum
    p = inhalt.paragraphs[0]
    _run(p, anzeige.firma or "", 10.5, TEXT, fett=True)
    _abstaende(p, 14, 0)
    if anzeige.ort:
        p = inhalt.add_paragraph()
        _run(p, anzeige.ort, 10.5, TEXT)
        _abstaende(p, 0, 0)
    p = inhalt.add_paragraph()
    _run(p, f"{timezone.localdate():%d.%m.%Y}", 10.5, "555555")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _abstaende(p, 0, 6)

    # Betreff als Abschnittsueberschrift (wie im Lebenslauf)
    p = inhalt.add_paragraph()
    _run(p, f"Bewerbung als {anzeige.titel}", 11, TEAL, fett=True, abstand=12)
    _linie_unten(p)
    _abstaende(p, 10, 8)

    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        p = inhalt.add_paragraph()
        _run(p, block.replace("\n", " ") if not block.lower().startswith(("mit freundlichen", "sehr geehrte")) else block,
             10.5, TEXT)
        _abstaende(p, 0, 7, zeilen=1.15)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # leerer Absatz hinter der Tabelle ist in Word zwingend; so klein wie moeglich
    schluss = doc.paragraphs[-1] if doc.paragraphs else doc.add_paragraph()
    for r in schluss.runs:
        r.font.size = Pt(1)
    _abstaende(schluss, 0, 0)

    puffer = io.BytesIO()
    doc.save(puffer)
    return puffer.getvalue()
