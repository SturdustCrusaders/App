from django.db import migrations


def create_template_manager_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    template_manager, _ = Group.objects.get_or_create(name="TemplateManager")
    template_manager_perms = Permission.objects.filter(codename__in=[
        "view_uisettings",
        "view_document",
        "view_documenttype",
        "add_documenttypetemplate",
        "change_documenttypetemplate",
        "delete_documenttypetemplate",
        "view_documenttypetemplate",
        "add_documenttypetemplatefield",
        "change_documenttypetemplatefield",
        "delete_documenttypetemplatefield",
        "view_documenttypetemplatefield",
    ])
    template_manager.permissions.set(template_manager_perms)


def remove_template_manager_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="TemplateManager").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1077_documenttypetemplate_and_fields"),
    ]
    operations = [
        migrations.RunPython(
            create_template_manager_group,
            remove_template_manager_group,
        ),
    ]
