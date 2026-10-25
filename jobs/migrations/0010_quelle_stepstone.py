from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0009_stellenanzeige_duplikat_von"),
    ]

    operations = [
        migrations.AddField(
            model_name="stellenanzeige",
            name="quelle",
            field=models.CharField(choices=[("indeed", "Indeed"), ("stepstone", "StepStone")], default="indeed",
                                   max_length=12, verbose_name="Quelle"),
        ),
        migrations.AlterField(
            model_name="mail",
            name="ordner",
            field=models.CharField(choices=[("eingang", "Posteingang"), ("indeed", "Indeed"), ("stepstone", "StepStone"),
                                            ("frontend", "Frontend"), ("vibecoding", "VibeCoding"), ("pruefung", "Pruefung")],
                                   default="eingang", max_length=10, verbose_name="Ordner"),
        ),
    ]
