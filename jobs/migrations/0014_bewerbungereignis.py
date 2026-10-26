import django.db.models.deletion
from datetime import date

from django.db import migrations, models


def uebernehmen(apps, schema_editor):
    """Bestehende Bewerbungen: Start-Eintrag + bisherige Notiz in den Verlauf uebernehmen."""
    Bewerbung = apps.get_model("jobs", "Bewerbung")
    Ereignis = apps.get_model("jobs", "BewerbungEreignis")
    for b in Bewerbung.objects.all():
        if b.beworben_am:
            Ereignis.objects.create(bewerbung=b, datum=b.beworben_am, status="gesendet", notiz="")
        if b.notizen.strip() or b.status not in ("gesendet", "vorbereitet"):
            Ereignis.objects.create(bewerbung=b, datum=date.today(), status=b.status, notiz=b.notizen.strip())
            b.notizen = ""
            b.save(update_fields=["notizen"])


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0013_interessant_anschreiben"),
    ]

    operations = [
        migrations.CreateModel(
            name="BewerbungEreignis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("datum", models.DateField(verbose_name="Datum")),
                ("status", models.CharField(choices=[("vorbereitet", "Vorbereitet"), ("gesendet", "Gesendet"),
                                                     ("antwort", "Antwort erhalten"), ("einladung", "Einladung Gespräch"),
                                                     ("absage", "Absage"), ("zurueck", "Zurückgezogen")],
                                            max_length=12, verbose_name="Status")),
                ("notiz", models.TextField(blank=True, verbose_name="Notiz")),
                ("bewerbung", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ereignisse",
                                                to="jobs.bewerbung")),
            ],
            options={"verbose_name": "Verlaufseintrag", "verbose_name_plural": "Bewerbungsverlauf",
                     "ordering": ["-datum", "-id"]},
        ),
        migrations.RunPython(uebernehmen, migrations.RunPython.noop),
    ]
