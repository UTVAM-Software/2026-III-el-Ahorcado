"""Esquema inicial compatible con las tablas del servidor Express."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='Player', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=50, unique=True)),
            ('first_name', models.CharField(max_length=50)),
            ('last_name', models.CharField(max_length=50)),
            ('email', models.EmailField(max_length=100, unique=True)),
            ('password', models.CharField(default='', max_length=200)),
            ('role', models.CharField(default='student', max_length=10, choices=[('student', 'Alumno'), ('teacher', 'Profesor')])),
            ('score', models.IntegerField(default=0)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
        ], options={'db_table': 'players'}),
        migrations.CreateModel(name='Word', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('word', models.CharField(max_length=255, unique=True)),
            ('difficulty', models.CharField(max_length=10, choices=[('easy', 'Fácil'), ('medium', 'Media'), ('hard', 'Difícil')])),
            ('theme', models.CharField(default='General', max_length=50)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('created_by', models.ForeignKey(blank=True, null=True, db_column='created_by', on_delete=django.db.models.deletion.SET_NULL, to='core.player')),
        ], options={'db_table': 'words'}),
        migrations.CreateModel(name='AssignedGame', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('theme', models.CharField(default='General', max_length=50)),
            ('difficulty', models.CharField(max_length=10, choices=[('easy', 'Fácil'), ('medium', 'Media'), ('hard', 'Difícil')])),
            ('word_ids', models.JSONField(default=list)),
            ('current_index', models.IntegerField(default=0)),
            ('status', models.CharField(default='pending', max_length=12)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('student', models.ForeignKey(db_column='student_id', on_delete=django.db.models.deletion.CASCADE, related_name='assigned_as_student', to='core.player')),
            ('teacher', models.ForeignKey(db_column='teacher_id', on_delete=django.db.models.deletion.CASCADE, related_name='assigned_as_teacher', to='core.player')),
        ], options={'db_table': 'assigned_games'}),
        migrations.CreateModel(name='DailyWord', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('set_date', models.DateField(default=django.utils.timezone.localdate)),
            ('active', models.BooleanField(default=True)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('set_by', models.ForeignKey(blank=True, null=True, db_column='set_by', on_delete=django.db.models.deletion.SET_NULL, to='core.player')),
            ('word', models.ForeignKey(db_column='word_id', on_delete=django.db.models.deletion.PROTECT, to='core.word')),
        ], options={'db_table': 'daily_words'}),
        migrations.CreateModel(name='Game', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('difficulty', models.CharField(max_length=10, choices=[('easy', 'Fácil'), ('medium', 'Media'), ('hard', 'Difícil')])),
            ('guessed', models.JSONField(default=list)),
            ('wrong', models.JSONField(default=list)),
            ('wrong_attempts', models.IntegerField(default=0)),
            ('attempts', models.IntegerField(default=0)),
            ('status', models.CharField(default='playing', max_length=10)),
            ('revealed_hint', models.CharField(blank=True, max_length=1, null=True)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('finished_at', models.DateTimeField(blank=True, null=True)),
            ('assigned_game', models.ForeignKey(blank=True, null=True, db_column='assigned_game_id', on_delete=django.db.models.deletion.SET_NULL, to='core.assignedgame')),
            ('player', models.ForeignKey(db_column='player_id', on_delete=django.db.models.deletion.CASCADE, to='core.player')),
            ('word', models.ForeignKey(db_column='word_id', on_delete=django.db.models.deletion.PROTECT, to='core.word')),
        ], options={'db_table': 'games'}),
        migrations.CreateModel(name='DailyWordAnswer', fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('answer_letter', models.CharField(max_length=1)),
            ('response_time_ms', models.IntegerField()),
            ('points_earned', models.IntegerField(default=0)),
            ('is_correct', models.BooleanField()),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('daily_word', models.ForeignKey(db_column='daily_word_id', on_delete=django.db.models.deletion.CASCADE, to='core.dailyword')),
            ('player', models.ForeignKey(db_column='player_id', on_delete=django.db.models.deletion.CASCADE, to='core.player')),
        ], options={'db_table': 'daily_word_answers'}),
        migrations.AddConstraint(model_name='dailywordanswer', constraint=models.UniqueConstraint(fields=('daily_word', 'player'), name='daily_answer_unique')),
    ]
