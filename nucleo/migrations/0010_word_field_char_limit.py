from django.db import migrations


WORD_MAX_LENGTH = 255


def convert_legacy_word_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor not in ('mysql', 'postgresql'):
        return

    table_name = connection.ops.quote_name('words')
    column_name = connection.ops.quote_name('word')
    with connection.cursor() as cursor:
        if connection.vendor == 'mysql':
            cursor.execute(
                'SELECT data_type FROM information_schema.columns '
                'WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s',
                ['words', 'word'],
            )
            row = cursor.fetchone()
            if not row or row[0].lower() not in ('text', 'tinytext', 'mediumtext', 'longtext'):
                return
        else:
            cursor.execute(
                'SELECT data_type FROM information_schema.columns '
                'WHERE table_schema = current_schema() AND table_name = %s AND column_name = %s',
                ['words', 'word'],
            )
            row = cursor.fetchone()
            if not row or row[0].lower() != 'text':
                return

        cursor.execute(
            f'SELECT COUNT(*) FROM {table_name} '
            f'WHERE CHAR_LENGTH({column_name}) > %s',
            [WORD_MAX_LENGTH],
        )
        too_long_count = cursor.fetchone()[0]
        if too_long_count:
            raise RuntimeError(
                f'No se puede limitar words.word a {WORD_MAX_LENGTH} caracteres: '
                f'{too_long_count} registro(s) exceden el límite.'
            )

        if connection.vendor == 'mysql':
            cursor.execute(
                f'ALTER TABLE {table_name} MODIFY COLUMN {column_name} '
                f'VARCHAR({WORD_MAX_LENGTH}) NOT NULL'
            )
        else:
            cursor.execute(
                f'ALTER TABLE {table_name} ALTER COLUMN {column_name} '
                f'TYPE VARCHAR({WORD_MAX_LENGTH})'
            )


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_portable_list_fields'),
    ]

    operations = [
        migrations.RunPython(convert_legacy_word_column, migrations.RunPython.noop),
    ]
