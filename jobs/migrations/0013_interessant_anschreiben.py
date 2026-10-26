from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0012_archiv"),
    ]

    operations = [
        migrations.AddField(
            model_name="stellenanzeige",
            name="interessant",
            field=models.BooleanField(default=False, verbose_name="Interessant (Merker)"),
        ),
        migrations.AddField(
            model_name="stellenanzeige",
            name="anschreiben",
            field=models.TextField(blank=True, verbose_name="Anschreiben (Entwurf)"),
        ),
    ]
