# Custom migration to convert ArrayField to JSONField with proper data handling
from django.db import migrations, models


def convert_array_to_json(apps, schema_editor):
    """Convert existing array data to JSON format"""
    db_alias = schema_editor.connection.alias
    if db_alias == 'default':
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE directory_authoritycontact 
                SET tags = to_jsonb(tags)::jsonb 
                WHERE tags IS NOT NULL
            """)


def convert_json_to_array(apps, schema_editor):
    """Reverse: convert JSON back to array (for rollback)"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('directory', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE directory_authoritycontact ALTER COLUMN tags TYPE jsonb USING to_jsonb(tags)",
            reverse_sql="ALTER TABLE directory_authoritycontact ALTER COLUMN tags TYPE varchar[] USING ARRAY(SELECT jsonb_array_elements_text(tags))",
        ),
    ]
