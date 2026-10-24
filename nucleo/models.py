"""Modelos compatibles con las tablas PostgreSQL de la aplicación anterior."""
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

DIFFICULTIES = [('easy', 'Fácil'), ('medium', 'Media'), ('hard', 'Difícil')]

class Player(models.Model):
    name = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    supabase_user_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    password = models.CharField(max_length=200, default='')
    role = models.CharField(max_length=10, choices=[('student', 'Alumno'), ('teacher', 'Profesor')], default='student')
    grade = models.CharField(max_length=30, blank=True, default='')
    group_name = models.CharField(max_length=20, blank=True, default='')
    score = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'players'

    def __str__(self):
        return self.name


class PasswordResetToken(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'password_reset_tokens'

    def __str__(self):
        return f'Token de recuperación para {self.player.name} (vence {self.expires_at:%Y-%m-%d %H:%M})'


class Word(models.Model):
    word = models.TextField(unique=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    theme = models.CharField(max_length=50, default='General')
    created_by = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, db_column='created_by')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'words'

    def __str__(self):
        return self.word


class AssignedGame(models.Model):
    teacher = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='assigned_as_teacher', db_column='teacher_id')
    student = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='assigned_as_student', db_column='student_id')
    theme = models.CharField(max_length=50, default='General')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    word_ids = ArrayField(models.IntegerField(), default=list)
    current_index = models.IntegerField(default=0)
    status = models.CharField(max_length=12, default='pending')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'assigned_games'

    def __str__(self):
        return f'{self.theme} para {self.student.name}'


class Game(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column='player_id')
    word = models.ForeignKey(Word, on_delete=models.PROTECT, db_column='word_id')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    guessed = ArrayField(models.TextField(), default=list)
    wrong = ArrayField(models.TextField(), default=list)
    wrong_attempts = models.IntegerField(default=0)
    attempts = models.IntegerField(default=0)
    status = models.CharField(max_length=10, default='playing')
    revealed_hint = models.CharField(max_length=1, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    assigned_game = models.ForeignKey(AssignedGame, null=True, blank=True, on_delete=models.SET_NULL, db_column='assigned_game_id')

    class Meta:
        db_table = 'games'

    def __str__(self):
        return f'Partida de {self.player.name}: {self.word.word}'


class DailyWord(models.Model):
    word = models.ForeignKey(Word, on_delete=models.PROTECT, db_column='word_id')
    set_by = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, db_column='set_by')
    set_date = models.DateField(default=timezone.localdate)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'daily_words'

    def __str__(self):
        return f'{self.word.word} ({self.set_date})'


class DailyWordAnswer(models.Model):
    daily_word = models.ForeignKey(DailyWord, on_delete=models.CASCADE, db_column='daily_word_id')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column='player_id')
    answer_letter = models.CharField(max_length=1)
    response_time_ms = models.IntegerField()
    points_earned = models.IntegerField(default=0)
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'daily_word_answers'
        constraints = [models.UniqueConstraint(fields=['daily_word', 'player'], name='daily_answer_unique')]

    def __str__(self):
        return f'{self.player.name}: {self.answer_letter} en {self.daily_word.word.word}'
