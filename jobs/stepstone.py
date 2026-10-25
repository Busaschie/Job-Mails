"""Parser fuer StepStone-Jobagent-Mails (Text-Teil). Absender: info@jobagent.stepstone.de"""
import hashlib
import re

URL = re.compile(r"^https?://click\.stepstone\.de/\S+$")
UEBERSCHRIFT = re.compile(r"^(Passt\s*(gut|hervorragend)|Andere Bewerber|Weitere passende Jobs)", re.I)
ENDE = re.compile(r"^(Weitere passende Jobs|-{10,})", re.I)


def parse_alert(text):
    """Liefert Liste von Dicts wie indeed.parse_alert: titel, firma, ort, gehalt, snippet, alter, link, url, schluessel."""
    lines = [l.replace("\xa0", " ").strip() for l in text.replace("\r", "").split("\n")]
    stop = next((i for i, l in enumerate(lines) if re.match(r"^Weitere passende Jobs", l, re.I)), len(lines))
    lines = lines[:stop]
    urls = [i for i, l in enumerate(lines) if URL.match(l)]
    jobs = []
    for n, i in enumerate(urls):
        # Titel steht direkt vor dem Link; der Link "Weitere passende Jobs anzeigen" hat davor die Ueberschrift
        titel = lines[i - 1] if i > 0 else ""
        if not titel or UEBERSCHRIFT.match(titel) or ENDE.match(titel):
            continue
        ende = (urls[n + 1] - 1) if n + 1 < len(urls) else len(lines)
        seg = []
        for l in lines[i + 1:ende]:
            if ENDE.match(l):
                break
            seg.append(l)
        # Block 1 (zusammenhaengende Zeilen): Firma, Ort; weitere Zeilen/Bloecke: Eckdaten
        block, rest, im_block = [], [], True
        for l in seg:
            if UEBERSCHRIFT.match(l):
                break
            if not l:
                im_block = False if block else im_block
                continue
            (block if im_block else rest).append(l)
        if not block:
            continue
        firma = block[0]
        ort = block[1] if len(block) > 1 else ""
        meta = block[2:] + rest
        gehalt = next((l for l in meta if "\u20ac" in l), "")
        snippet = " | ".join(l for l in meta if l != gehalt)
        schluessel = "ss-" + hashlib.sha1(f"{titel}|{firma}|{ort}".encode()).hexdigest()[:20]
        jobs.append(dict(titel=titel, firma=firma, ort=ort, gehalt=gehalt, snippet=snippet,
                         alter="", link=lines[i], jk="", url=lines[i], schluessel=schluessel))
    return jobs
