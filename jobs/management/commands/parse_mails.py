import email
import email.utils
import imaplib
import re
from email.header import decode_header, make_header
from email.policy import default as default_policy

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobs import indeed, jobware, stepstone
from jobs.models import Mail, Stellenanzeige


class Command(BaseCommand):
    help = "Mails im Ordner Indeed lesen und die einzelnen Jobs als Stellenanzeige speichern (ohne Duplikate)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Auch bereits geparste Mails erneut lesen")
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **opt):
        s = settings
        if not (s.IMAP_HOST and s.IMAP_USER and s.IMAP_PASSWORD):
            raise CommandError("IMAP-Zugangsdaten in .env fehlen.")
        imap = (imaplib.IMAP4_SSL if s.IMAP_SSL else imaplib.IMAP4)(s.IMAP_HOST, s.IMAP_PORT)
        imap.login(s.IMAP_USER, s.IMAP_PASSWORD)
        try:
            self._run(imap, opt)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _delimiter(self, imap):
        for row in imap.list()[1] or []:
            m = re.match(rb'\(.*?\) "(.*?)" ', row)
            if m:
                return m.group(1).decode()
        return "/"

    def _run(self, imap, opt):
        delim = self._delimiter(imap)
        for name, parser, quelle in [
            ("Indeed", lambda t, h: indeed.parse_alert(t), "indeed"),
            ("StepStone", lambda t, h: stepstone.parse_alert(t), "stepstone"),
            ("Jobware", jobware.parse_alert, "jobware"),
        ]:
            folder = settings.IMAP_BASE_FOLDER.replace("/", delim) + delim + name
            typ, _ = imap.select(f'"{folder}"', readonly=True)
            if typ != "OK":
                if name == "Indeed":
                    raise CommandError(f"Ordner {folder} nicht gefunden.")
                self.stdout.write(f"Ordner {folder} nicht vorhanden - uebersprungen.")
                continue
            self._ordner(imap, opt, name, parser, quelle)

    def _ordner(self, imap, opt, name, parser, quelle):
        uids = imap.uid("search", None, "ALL")[1][0].split()[-opt["limit"]:]
        neu = dup = mails = 0
        for uid in uids:
            typ, d = imap.uid("fetch", uid, "(BODY.PEEK[])")
            if typ != "OK" or not d or not isinstance(d[0], tuple):
                continue
            msg = email.message_from_bytes(d[0][1], policy=default_policy)
            mid = (msg["Message-ID"] or f"uid-{uid.decode()}").strip()
            mail = Mail.objects.filter(message_id=mid).first()
            if mail and mail.geparst and not opt["all"]:
                continue
            if not mail:
                datum = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else timezone.now()
                betreff = str(make_header(decode_header(msg["Subject"] or "")))[:500]
                mail = Mail.objects.create(
                    message_id=mid, betreff=betreff, titel=betreff[:255], absender=(msg["From"] or "")[:255],
                    empfangen_am=datum, ordner=Mail.Ordner(quelle),
                )
            body = msg.get_body(preferencelist=("plain",))
            text = body.get_content() if body else ""
            hbody = msg.get_body(preferencelist=("html",))
            html = hbody.get_content() if hbody else ""
            for j in parser(text, html):
                if not Stellenanzeige.objects.filter(schluessel=j["schluessel"]).exists() and Stellenanzeige.objects.filter(
                        titel__iexact=j["titel"][:300].strip(), firma__iexact=j["firma"][:255].strip(),
                        ort__iexact=j["ort"][:255].strip()).exists():
                    dup += 1  # gleiche Anzeige mit neuer Indeed-ID (erneut ausgespielt)
                    continue
                extra = {}
                if j.get("volltext"):  # z. B. Jobware "Brandneu": voller Anzeigentext in der Mail
                    extra = dict(seitentext=j["volltext"], status=Stellenanzeige.Status.ABGERUFEN)
                _, created = Stellenanzeige.objects.get_or_create(
                    schluessel=j["schluessel"],
                    defaults=dict(mail=mail, quelle=quelle, titel=j["titel"][:300], firma=j["firma"][:255], ort=j["ort"][:255],
                                  gehalt=j["gehalt"][:100], snippet=j["snippet"], alter_text=j["alter"][:50], url=j["url"], **extra),
                )
                neu += created
                dup += not created
            mail.geparst = True
            mail.save(update_fields=["geparst"])
            mails += 1
        self.stdout.write(self.style.SUCCESS(f"[{name}] {mails} Mails gelesen: {neu} neue Anzeigen, {dup} Duplikate."))
