from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("library", "0025_reviewer_evaluation")]

    operations = [
        migrations.AddField(
            model_name="documenteditrevision",
            name="lineage",
            field=models.JSONField(default=dict),
        ),
    ]
