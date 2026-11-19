from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("library", "0035_job_book_mode")]

    operations = [
        migrations.AddField(
            model_name="rendition",
            name="content_issues",
            field=models.JSONField(default=list),
        ),
    ]
