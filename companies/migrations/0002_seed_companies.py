from django.db import migrations

COMPANIES = [
    {
        "name": "Intercom",
        "slug": "intercom",
        "components": [
            {"name": "Messenger", "status": "operational"},
            {"name": "Inbox", "status": "operational"},
            {"name": "API", "status": "operational"},
        ],
    },
    {
        "name": "Globex",
        "slug": "globex",
        "components": [
            {"name": "Website", "status": "operational"},
            {"name": "Payments", "status": "degraded performance"},
        ],
    },
]


def seed(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    for company in COMPANIES:
        Company.objects.get_or_create(slug=company["slug"], defaults=company)


class Migration(migrations.Migration):
    dependencies = [("companies", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
