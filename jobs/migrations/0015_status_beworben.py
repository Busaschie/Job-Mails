from django.db import migrations, models

STATUS = [("vorbereitet", "Vorbereitet"), ("gesendet", "Beworben"), ("antwort", "Antwort erhalten"),
          ("einladung", "Einladung Gespräch"), ("absage", "Absage"), ("zurueck", "Zurückgezogen")]


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0014_bewerbungereignis"),
    ]

    operations = [
        migrations.AlterField(model_name="bewerbung", name="status",
                              field=models.CharField(choices=STATUS, default="vorbereitet", max_length=12, verbose_name="Status")),
        migrations.AlterField(model_name="bewerbungereignis", name="status",
                              field=models.CharField(choices=STATUS, max_length=12, verbose_name="Status")),
    ]
