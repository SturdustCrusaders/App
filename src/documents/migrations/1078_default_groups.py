from django.db import migrations


def create_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    viewer, _ = Group.objects.get_or_create(name="Viewer")
    viewer.permissions.set(Permission.objects.filter(codename__in=[
        "view_uisettings",
        "view_document",
        "view_tag",
        "view_correspondent",
        "view_documenttype",
        "view_storagepath",
        "view_savedview",
        "view_documenttypetemplate",
        "view_documenttypetemplatefield",
        "view_documentfieldvalue",
    ]))

    uploader, _ = Group.objects.get_or_create(name="Uploader")
    uploader.permissions.set(Permission.objects.filter(codename__in=[
        "view_uisettings",
        "add_document",
        "view_document",
    ]))

    template_manager, _ = Group.objects.get_or_create(name="TemplateManager")
    template_manager.permissions.set(Permission.objects.filter(codename__in=[
    "view_uisettings",
    "view_document",
    "view_documenttype",
    "add_documenttype",
    "change_documenttype",
    "delete_documenttype",
    "view_documenttypetemplate",
    "add_documenttypetemplate",
    "change_documenttypetemplate",
    "delete_documenttypetemplate",
    "view_documenttypetemplatefield",
    "add_documenttypetemplatefield",
    "change_documenttypetemplatefield",
    "delete_documenttypetemplatefield",
    "view_documentfieldvalue",
]))


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Viewer", "Uploader", "TemplateManager"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1077_documenttypetemplate_and_fields"),
    ]
    operations = [
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
