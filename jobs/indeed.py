"""Parser für Indeed-Job-Alert-Mails (Text-Teil)."""
import hashlib
import re
from urllib.parse import parse_qs, urlparse

CLK = re.compile(r"^https?://\S*indeed\.\w+/(?:rc|pagead)/clk\S*$")
ALTER = re.compile(r"^(Gerade geschaltet|Vor \d+|Heute|Aktiv|Just posted|\d+ days? ago|Active)", re.I)
SKIP = {"schnellbewerbung", "aktiver arbeitgeber", "easily apply", "responsive employer"}


def parse_alert(text):
    """Liefert Liste von Dicts: titel, firma, ort, gehalt, snippet, alter, link, jk, url, schluessel."""
    jobs = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) < 3 or not CLK.match(lines[-1]):
            continue
        link, lines = lines[-1], lines[:-1]
        alter = lines.pop() if ALTER.match(lines[-1]) else ""
        titel = lines[0]
        firma, ort = (lines[1].rsplit(" - ", 1) + [""])[:2] if " - " in lines[1] else (lines[1], "")
        rest = [l for l in lines[2:] if l.lower() not in SKIP]
        gehalt = next((l for l in rest if "€" in l and len(l) < 80), "")
        snippet = max((l for l in rest if l != gehalt), key=len, default="")
        jk = (parse_qs(urlparse(link).query).get("jk") or [""])[0]
        url = f"https://de.indeed.com/viewjob?jk={jk}" if jk else link
        schluessel = jk or hashlib.sha1(f"{titel}|{firma}|{ort}".encode()).hexdigest()[:20]
        jobs.append(dict(titel=titel, firma=firma.strip(), ort=ort.strip(), gehalt=gehalt, snippet=snippet,
                         alter=alter, link=link, jk=jk, url=url, schluessel=schluessel))
    return jobs
