from django.db import migrations


def initialize_attachments(apps, schema_editor):
    # We can’t import the Result model directly as it may be a newer version
    # than this migration expects.  We use the historical version.
    Result = apps.get_model("samples", "Result")
    for result in Result.objects.all():
        if result.image_type != "none":
            result.attachments = [{"type": result.image_type, "description": result.title}]
            result.save()


class Migration(migrations.Migration):
    dependencies = [
        ("samples", "0011_result_attachments"),
    ]

    operations = [
        migrations.RunPython(initialize_attachments),
    ]
