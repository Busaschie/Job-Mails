from django.db import models


class Regel(models.Model):
    """Suchbegriff zum Einordnen der Mails."""

    class Typ(models.TextChoices):
        POSITIV = "positiv", "Passend (muss vorkommen)"
        NEGATIV = "negativ", "Ausschluss (darf nicht vorkommen)"

    begriff = models.CharField("Begriff", max_length=100, unique=True)
    ziel = models.CharField(
        "Zielordner (nur bei „Passend“)", max_length=10, blank=True,
        choices=[("frontend", "Frontend"), ("vibecoding", "VibeCoding")],
    )
    typ = models.CharField("Typ", max_length=10, choices=Typ.choices, default=Typ.POSITIV)
    aktiv = models.BooleanField("Aktiv", default=True)

    class Meta:
        verbose_name = "Regel"
        verbose_name_plural = "Regeln"
        ordering = ["typ", "begriff"]

    def __str__(self):
        return f"{self.get_typ_display()}: {self.begriff}"


class Mail(models.Model):
    class Ordner(models.TextChoices):
        EINGANG = "eingang", "Posteingang"
        INDEED = "indeed", "Indeed"
        STEPSTONE = "stepstone", "StepStone"
        JOBWARE = "jobware", "Jobware"
        FRONTEND = "frontend", "Frontend"
        VIBECODING = "vibecoding", "VibeCoding"
        PRUEFUNG = "pruefung", "Pruefung"

    message_id = models.CharField("Message-ID", max_length=255, unique=True)
    betreff = models.CharField("Betreff", max_length=500)
    absender = models.CharField("Absender", max_length=255)
    empfangen_am = models.DateTimeField("Empfangen am")
    # Jobdaten aus der Mail (z. B. Indeed)
    titel = models.CharField("Jobtitel", max_length=255, blank=True)
    firma = models.CharField("Firma", max_length=255, blank=True)
    link = models.URLField("Link", max_length=1000, blank=True)
    ordner = models.CharField("Ordner", max_length=10, choices=Ordner.choices, default=Ordner.EINGANG)
    treffer = models.TextField("Gefundene Begriffe", blank=True)
    geparst = models.BooleanField("Jobs extrahiert", default=False)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mail"
        verbose_name_plural = "Mails"
        ordering = ["-empfangen_am"]

    def __str__(self):
        return self.titel or self.betreff


class Bewerbung(models.Model):
    class Status(models.TextChoices):
        VORBEREITET = "vorbereitet", "Vorbereitet"
        GESENDET = "gesendet", "Gesendet"
        ANTWORT = "antwort", "Antwort erhalten"
        EINLADUNG = "einladung", "Einladung Gespräch"
        ABSAGE = "absage", "Absage"
        ZURUECK = "zurueck", "Zurückgezogen"

    anzeige = models.OneToOneField("Stellenanzeige", on_delete=models.CASCADE, related_name="bewerbung",
                                   null=True, verbose_name="Stellenanzeige")
    beworben_am = models.DateField("Beworben am", null=True, blank=True)
    status = models.CharField("Status", max_length=12, choices=Status.choices, default=Status.VORBEREITET)
    notizen = models.TextField("Notizen", blank=True)

    class Meta:
        verbose_name = "Bewerbung"
        verbose_name_plural = "Bewerbungen"
        ordering = ["-beworben_am"]

    def __str__(self):
        return f"Bewerbung: {self.anzeige}"


class Stellenanzeige(models.Model):
    class Status(models.TextChoices):
        NEU = "neu", "Neu (nur Mail-Daten)"
        ABGERUFEN = "abgerufen", "Seite abgerufen"
        AUSGEWERTET = "ausgewertet", "Per LLM ausgewertet"
        FEHLER = "fehler", "Fehler"

    quelle = models.CharField("Quelle", max_length=12, default="indeed",
                              choices=[("indeed", "Indeed"), ("stepstone", "StepStone"), ("jobware", "Jobware")])
    schluessel = models.CharField("Schlüssel (Indeed-jk oder Hash)", max_length=64, unique=True)
    mail = models.ForeignKey(Mail, on_delete=models.SET_NULL, null=True, related_name="anzeigen", verbose_name="Erste Mail")
    titel = models.CharField("Titel", max_length=300)
    firma = models.CharField("Firma", max_length=255, blank=True)
    ort = models.CharField("Ort", max_length=255, blank=True)
    gehalt = models.CharField("Gehalt (laut Mail)", max_length=100, blank=True)
    snippet = models.TextField("Kurztext", blank=True)
    alter_text = models.CharField("Alter laut Mail", max_length=50, blank=True)
    url = models.TextField("Anzeigen-URL")
    status = models.CharField("Status", max_length=12, choices=Status.choices, default=Status.NEU)
    seitentext = models.TextField("Abgerufener Seitentext", blank=True)
    daten = models.JSONField("Strukturierte Daten (LLM)", null=True, blank=True)
    fehler = models.TextField("Fehler", blank=True)
    kategorie = models.CharField("Kategorie", max_length=10, blank=True,
                                 choices=[("frontend", "Frontend"), ("vibecoding", "VibeCoding"), ("pruefung", "Pruefung")])
    passung = models.CharField("Passung zum Profil", max_length=10, blank=True,
                               choices=[("passt", "Passt"), ("teilweise", "Teilweise"), ("unklar", "Unklar"), ("ausschluss", "Ausschluss")])
    erstellt_am = models.DateTimeField(auto_now_add=True)
    duplikat_von = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="duplikate", verbose_name="Duplikat von")

    class Meta:
        verbose_name = "Stellenanzeige"
        verbose_name_plural = "Stellenanzeigen"
        ordering = ["-erstellt_am"]

    def __str__(self):
        return f"{self.titel} – {self.firma}"


class Shortlist(Stellenanzeige):
    """Ansicht auf Anzeigen, die zum Profil passen oder noch unklar sind."""

    class Meta:
        proxy = True
        verbose_name = "Shortlist"
        verbose_name_plural = "Shortlist"


class PipelineLauf(models.Model):
    class Status(models.TextChoices):
        LAEUFT = "laeuft", "Läuft"
        OK = "ok", "Erfolgreich"
        FEHLER = "fehler", "Mit Fehlern"

    gestartet = models.DateTimeField("Gestartet", auto_now_add=True)
    beendet = models.DateTimeField("Beendet", null=True, blank=True)
    status = models.CharField("Status", max_length=10, choices=Status.choices, default=Status.LAEUFT)
    mails_neu = models.IntegerField("Neue Mails", default=0)
    anzeigen_neu = models.IntegerField("Neue Anzeigen", default=0)
    ausgewertet = models.IntegerField("Ausgewertet", default=0)
    fehler = models.IntegerField("Anzeigen mit Fehler (neu)", default=0)
    meldung = models.TextField("Meldungen", blank=True)

    class Meta:
        verbose_name = "Pipeline-Lauf"
        verbose_name_plural = "Pipeline-Läufe"
        ordering = ["-gestartet"]

    def __str__(self):
        return f"Lauf {self.gestartet:%d.%m.%Y %H:%M}"
