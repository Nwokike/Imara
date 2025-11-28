from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('directory', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE directory_authoritycontact ALTER COLUMN tags TYPE jsonb USING COALESCE(to_jsonb(tags), '[]'::jsonb)",
            reverse_sql="ALTER TABLE directory_authoritycontact ALTER COLUMN tags TYPE varchar[] USING COALESCE(ARRAY(SELECT jsonb_array_elements_text(tags)), '{}'::varchar[])",
        ),
    ]
