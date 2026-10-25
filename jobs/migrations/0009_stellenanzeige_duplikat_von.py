import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0008_pipelinelauf"),
    ]

    operations = [
        migrations.AddField(
            model_name="stellenanzeige",
            name="duplikat_von",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="duplikate", to="jobs.stellenanzeige", verbose_name="Duplikat von"),
        ),
    ]
