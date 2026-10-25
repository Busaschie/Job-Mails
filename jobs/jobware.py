"""Parser fuer Jobware-Mails (Absender: info@jobmailer.jobware.de).

Zwei Layouts:
 A) "Job-Highlight der Woche": Liste mit Anzeigen (nur HTML sauber lesbar; Kurzdaten: Titel, Firma, Ort)
 B) "Brandneu!": eine Anzeige mit Emoji-Kurzdaten und vollem Jobprofil im Text (-> Volltext)
"""
import hashlib
import html as htmllib
import re

from bs4 import BeautifulSoup

ADV = re.compile(r"ADVERTISEMENT_ID=(\d+)")


def _schluessel(titel, firma, ort, adv=""):
    if adv:
        return f"jw-{adv}"
    return "jw-" + hashlib.sha1(f"{titel}|{firma}|{ort}".encode()).hexdigest()[:20]


def _layout_a(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs, gesehen = [], set()
    for a in soup.find_all("a", href=ADV):
        if "font-size:16px" not in (a.get("style") or "").replace(" ", ""):
            continue  # Logo-Link o. ae. ueberspringen
        adv = ADV.search(a["href"]).group(1)
        if adv in gesehen:
            continue
        gesehen.add(adv)
        firma_tag = a.find("div")
        firma = firma_tag.get_text(" ", strip=True) if firma_tag else ""
        if firma_tag:
            firma_tag.extract()
        titel = " ".join(a.get_text(" ", strip=True).split())
        span = a.find_next("span")
        ort = " ".join(span.get_text(" ", strip=True).split()) if span else ""
        jobs.append(dict(titel=titel, firma=firma, ort=ort, gehalt="", snippet="", alter="",
                         link=a["href"], jk="", url=a["href"], schluessel=_schluessel(titel, firma, ort, adv)))
    return jobs


def _layout_b(text):
    lines = [l.replace("\xa0", " ").strip() for l in text.replace("\r", "").split("\n")]
    try:
        i = next(n for n, l in enumerate(lines) if l.startswith("Bring mich zum Job"))
    except StopIteration:
        return []
    link = re.search(r"https?://\S+", lines[i])
    link = link.group(0) if link else ""
    block = []
    for l in reversed(lines[:i]):
        if not l:
            if block:
                break
            continue
        block.append(l)
    block.reverse()
    if not block:
        return []
    titel, firma, ort, meta = block[0], "", "", []
    for l in block[1:]:
        if l.startswith("\U0001F3E2"):
            firma = l.lstrip("\U0001F3E2").strip()
        elif l.startswith("\U0001F4CD"):
            ort = l.lstrip("\U0001F4CD").strip()
        else:
            meta.append(re.sub(r"^[^\w]+", "", l))
    # Volltext: ab "Vollstaendiges Jobprofil" bis "Hier geht's zum Job" bzw. Fusszeile
    start = next((n for n, l in enumerate(lines) if "Vollständiges Jobprofil" in l), None)
    ende = next((n for n, l in enumerate(lines) if n > (start or i) and (l.startswith("Hier geht") or l.startswith("Suchprofil verwalten"))), len(lines))
    volltext = ""
    if start is not None:
        roh = "\n".join(lines[start + 1:ende])
        roh = re.sub(r"</li>", "\n", roh)
        roh = re.sub(r"<li[^>]*>", "- ", roh)
        roh = re.sub(r"<[^>]+>", " ", roh)
        roh = htmllib.unescape(roh)
        volltext = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", roh)).strip()
    return [dict(titel=titel, firma=firma, ort=ort, gehalt="", snippet=" | ".join(meta), alter="",
                 link=link, jk="", url=link, schluessel=_schluessel(titel, firma, ort), volltext=volltext)]


def parse_alert(text, html=""):
    """Liefert Liste von Dicts wie indeed.parse_alert (optional mit 'volltext')."""
    if html and ADV.search(html):
        return _layout_a(html)
    if "Bring mich zum Job" in text:
        return _layout_b(text)
    return []
