"""Create the permanent General project (DECISIONS #3)."""

from django.db import migrations


def create_general(apps, schema_editor):
    Project = apps.get_model("inbox", "Project")
    Project.objects.get_or_create(
        is_general=True,
        defaults={
            "name": "General",
            "description": "Things to look into or try that will never be their own project.",
            "state": "building",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("inbox", "0001_initial")]

    # No reverse step needed: rolling back 0001 drops the table anyway.
    operations = [migrations.RunPython(create_general, migrations.RunPython.noop)]
