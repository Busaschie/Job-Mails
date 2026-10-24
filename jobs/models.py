from django.db import models


class Regel(models.Model):
    """Suchbegriff zum Einordnen der Mails."""

    class Typ(models.TextChoices):
        POSITIV = "positiv", "Passend (muss vorkommen)"
        NEGATIV = "negativ", "Ausschluss (darf nicht vorkommen)"

    begriff = models.CharField("Begriff", max_length=100, unique=True)
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
        PASSEND = "passend", "Kommt in Frage"
        PRUEFEN = "pruefen", "Zur Überprüfung"

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

    mail = models.OneToOneField(Mail, on_delete=models.CASCADE, related_name="bewerbung")
    beworben_am = models.DateField("Beworben am", null=True, blank=True)
    status = models.CharField("Status", max_length=12, choices=Status.choices, default=Status.VORBEREITET)
    notizen = models.TextField("Notizen", blank=True)

    class Meta:
        verbose_name = "Bewerbung"
        verbose_name_plural = "Bewerbungen"
        ordering = ["-beworben_am"]

    def __str__(self):
        return f"Bewerbung: {self.mail}"
