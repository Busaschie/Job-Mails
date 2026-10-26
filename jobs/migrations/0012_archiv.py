from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0011_jobware"),
    ]

    operations = [
        migrations.CreateModel(
            name="Archiv",
            fields=[],
            options={
                "verbose_name": "Archiv",
                "verbose_name_plural": "Archiv",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("jobs.stellenanzeige",),
        ),
    ]
