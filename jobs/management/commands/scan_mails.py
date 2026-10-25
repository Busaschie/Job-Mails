import email
import email.utils
import imaplib
import re
from email.header import decode_header, make_header
from email.policy import default as default_policy

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobs.models import Mail, Regel

APPLY_SENDER = "indeedapply@indeed.com"

ZIELE = {
    Mail.Ordner.INDEED: "Indeed",
    Mail.Ordner.FRONTEND: "Frontend",
    Mail.Ordner.VIBECODING: "VibeCoding",
    Mail.Ordner.PRUEFUNG: "Pruefung",
}


def _text(msg):
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    txt = part.get_content()
    if part.get_content_type() == "text/html":
        txt = re.sub(r"<(script|style).*?</\1>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt)


def klassifizieren(text):
    """Gibt (Ordner, Treffer-Liste) zurück."""
    text = text.lower()
    regeln = Regel.objects.filter(aktiv=True)
    neg = [r.begriff for r in regeln if r.typ == Regel.Typ.NEGATIV and r.begriff.lower() in text]
    if neg:
        return Mail.Ordner.PRUEFUNG, [f"-{b}" for b in neg]
    zaehler, treffer = {}, []
    for r in regeln:
        if r.typ == Regel.Typ.POSITIV and r.ziel and r.begriff.lower() in text:
            zaehler[r.ziel] = zaehler.get(r.ziel, 0) + 1
            treffer.append(r.begriff)
    if not zaehler:
        return Mail.Ordner.PRUEFUNG, []
    return max(zaehler, key=zaehler.get), treffer


class Command(BaseCommand):
    help = "Indeed-Mails per IMAP scannen, klassifizieren und in Unterordner verschieben."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Nur speichern/anzeigen, nichts verschieben")
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **opt):
        s = settings
        if not (s.IMAP_HOST and s.IMAP_USER and s.IMAP_PASSWORD):
            raise CommandError("IMAP-Zugangsdaten in .env fehlen.")
        cls = imaplib.IMAP4_SSL if s.IMAP_SSL else imaplib.IMAP4
        imap = cls(s.IMAP_HOST, s.IMAP_PORT)
        imap.login(s.IMAP_USER, s.IMAP_PASSWORD)
        try:
            self._scan(imap, opt)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _delimiter(self, imap):
        typ, data = imap.list()
        for row in data or []:
            m = re.match(rb'\(.*?\) "(.*?)" ', row)
            if m:
                return m.group(1).decode()
        return "/"

    def _beworben(self, imap, base, delim, opt):
        """Bestätigungen von indeedapply@indeed.com -> Ordner Beworben (nicht in der DB)."""
        typ, data = imap.uid("search", None, "FROM", f'"{APPLY_SENDER}"')
        uids = data[0].split() if typ == "OK" and data and data[0] else []
        self.stdout.write(f"{len(uids)} Bewerbungs-Mails von '{APPLY_SENDER}'.")
        if opt["dry_run"]:
            self.stdout.write("(dry-run: nichts verschoben)")
            return
        if not uids:
            return
        ziel = f'"{base}{delim}Beworben"'
        bewegt = 0
        for uid in uids:
            typ, antwort = imap.uid("copy", uid, ziel)
            if typ == "OK":
                imap.uid("store", uid, "+FLAGS", r"(\Deleted)")
                bewegt += 1
            else:
                self.stderr.write(f"Kopieren nach {ziel} fehlgeschlagen: {antwort}")
        imap.expunge()
        self.stdout.write(f"{bewegt} Bewerbungs-Mail(s) nach Beworben verschoben.")

    def _scan(self, imap, opt):
        s = settings
        delim = self._delimiter(imap)
        base = s.IMAP_BASE_FOLDER.replace("/", delim)
        imap.select(f'"{s.IMAP_FOLDER}"')
        self._beworben(imap, base, delim, opt)
        typ, data = imap.uid("search", None, "FROM", f'"{s.IMAP_SENDER}"')
        uids = data[0].split()[-opt["limit"]:]
        self.stdout.write(f"{len(uids)} Mails von '{s.IMAP_SENDER}' gefunden.")
        zaehler = {}
        for uid in uids:
            typ, d = imap.uid("fetch", uid, "(BODY.PEEK[])")
            if typ != "OK" or not d or not isinstance(d[0], tuple):
                continue
            msg = email.message_from_bytes(d[0][1], policy=default_policy)
            mid = (msg["Message-ID"] or f"uid-{uid.decode()}").strip()
            bekannt = Mail.objects.filter(message_id=mid).first()
            if bekannt and opt["dry_run"]:
                continue
            if bekannt:
                ordner = Mail.Ordner.INDEED
            else:
                betreff = str(make_header(decode_header(msg["Subject"] or "")))[:500]
                text = _text(msg)
                # Schritt 1: erst alles nach Indeed; Klassifizierung folgt später pro Job
                ordner, treffer = Mail.Ordner.INDEED, []
                link = re.search(r"https?://[^\s\"'<>]*indeed[^\s\"'<>]*", text)
                datum = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else timezone.now()
                Mail.objects.create(
                    message_id=mid, betreff=betreff, titel=betreff[:255],
                    absender=(msg["From"] or "")[:255], empfangen_am=datum,
                    link=link.group(0)[:1000] if link else "", ordner=ordner,
                    treffer=", ".join(treffer),
                )
                zaehler[ordner] = zaehler.get(ordner, 0) + 1
            if not opt["dry_run"]:
                ziel = f'"{base}{delim}{ZIELE[ordner]}"'
                if imap.uid("copy", uid, ziel)[0] == "OK":
                    imap.uid("store", uid, "+FLAGS", r"(\Deleted)")
                else:
                    self.stderr.write(f"Ordner {ziel} nicht gefunden – Mail bleibt im Posteingang.")
        if not opt["dry_run"]:
            imap.expunge()
        self.stdout.write(self.style.SUCCESS(f"Fertig: {zaehler or 'keine neuen Mails'}"))
