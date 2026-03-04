from django.db import migrations


def create_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    viewer, _ = Group.objects.get_or_create(name="Viewer")
    viewer_perms = Permission.objects.filter(codename__in=[
        "view_uisettings",
        "view_document",
        "view_tag",
        "view_correspondent",
        "view_documenttype",
        "view_storagepath",
        "view_savedview",
    ])
    viewer.permissions.set(viewer_perms)

    uploader, _ = Group.objects.get_or_create(name="Uploader")
    uploader_perms = Permission.objects.filter(codename__in=[
        "view_uisettings",
        "add_document",
        "view_document",
    ])
    uploader.permissions.set(uploader_perms)


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Viewer", "Uploader"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "1075_workflowaction_order"),
    ]

    operations = [
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
