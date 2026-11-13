from django.db import migrations


ARRAY_COLUMNS = {
    'assigned_games': ('word_ids',),
    'games': ('guessed', 'wrong'),
}


def convert_legacy_postgresql_arrays(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return

    with connection.cursor() as cursor:
        for table_name, columns in ARRAY_COLUMNS.items():
            cursor.execute(
                'SELECT column_name, udt_name FROM information_schema.columns '
                'WHERE table_schema = current_schema() AND table_name = %s',
                [table_name],
            )
            column_types = dict(cursor.fetchall())
            for column_name in columns:
                if column_types.get(column_name, '').startswith('_'):
                    cursor.execute(
                        f'ALTER TABLE {connection.ops.quote_name(table_name)} '
                        f'ALTER COLUMN {connection.ops.quote_name(column_name)} '
                        f'TYPE jsonb USING to_jsonb({connection.ops.quote_name(column_name)})'
                    )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_player_role_supervisor'),
    ]

    operations = [
        migrations.RunPython(convert_legacy_postgresql_arrays, migrations.RunPython.noop),
    ]
