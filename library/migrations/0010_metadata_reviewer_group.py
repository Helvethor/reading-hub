from django.db import migrations


def create_metadata_review_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="library", model="metadatasuggestion"
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename="review_metadata",
        defaults={"name": "Can review catalogue metadata suggestions"},
    )
    group, _ = Group.objects.get_or_create(name="Metadata reviewers")
    group.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("library", "0009_canonicalauthor_metadatasuggestion_catalogueauthor_and_more"),
    ]

    operations = [migrations.RunPython(create_metadata_review_group, migrations.RunPython.noop)]
