from django.db import migrations, models


def add_is_active_if_missing(apps, schema_editor):
    Player = apps.get_model('core', 'Player')
    field = models.BooleanField(default=True)
    field.set_attributes_from_name('is_active')
    field.model = Player

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, Player._meta.db_table
            )
        }

    if field.column not in columns:
        schema_editor.add_field(Player, field)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_player_supabase_user_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_is_active_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='player',
                    name='is_active',
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
    ]
