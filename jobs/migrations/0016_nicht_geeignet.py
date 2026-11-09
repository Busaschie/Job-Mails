from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0015_status_beworben"),
    ]

    operations = [
        migrations.AddField(
            model_name="stellenanzeige",
            name="nicht_geeignet",
            field=models.BooleanField(default=False, verbose_name="Nicht geeignet"),
        ),
        migrations.CreateModel(
            name="NichtGeeignet",
            fields=[],
            options={
                "verbose_name": "Nicht geeignet",
                "verbose_name_plural": "Nicht geeignet",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("jobs.stellenanzeige",),
        ),
    ]
