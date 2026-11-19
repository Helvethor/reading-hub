from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("library", "0034_reading_style_cascade")]

    operations = [
        migrations.AlterField(
            model_name="job",
            name="mode",
            field=models.CharField(
                choices=[
                    ("import", "Import"),
                    ("refresh", "Refresh source"),
                    ("reformat", "Reformat stored source"),
                    ("book", "Reimport as book"),
                ],
                max_length=10,
            ),
        ),
    ]
