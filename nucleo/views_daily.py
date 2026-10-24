from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone

from .api import body, endpoint, error, integer
from .models import DailyWord, DailyWordAnswer, Player, Word
from .views_words import sanitize_word


@endpoint(['GET', 'POST'], auth=True)
def daily_word(request):
    if request.method == 'GET':
        daily = DailyWord.objects.select_related('word').filter(set_date=timezone.localdate(), active=True).order_by('-id').first()
        if not daily:
            return JsonResponse({'message': 'No hay palabra del día disponible'}, status=404)
        answer = DailyWordAnswer.objects.filter(daily_word=daily, player=request.player).first()
        return JsonResponse({'id': daily.id, 'wordId': daily.word_id, 'word': '*' * len(daily.word.word),
                             'difficulty': daily.word.difficulty,
                             'user_answer': answer.answer_letter if answer else None,
                             'is_correct': answer.is_correct if answer else None,
                             'points_earned': answer.points_earned if answer else None,
                             'response_time_ms': answer.response_time_ms if answer else None})
    if request.player.role != 'teacher':
        return error('Solo profesores pueden establecer palabra del día', 403)
    data = body(request)
    word_id = integer(data.get('wordId'))
    new_word = sanitize_word(data.get('word'))
    if not word_id and not new_word:
        return error('Selecciona una palabra o escribe una nueva.')
    with transaction.atomic():
        if word_id:
            word = Word.objects.filter(pk=word_id).first()
            if not word:
                return error('Debes seleccionar una palabra válida')
        else:
            difficulty = data.get('difficulty') if data.get('difficulty') in ('easy', 'medium', 'hard') else 'easy'
            word, _ = Word.objects.update_or_create(word=new_word, defaults={
                'difficulty': difficulty, 'theme': str(data.get('theme') or '').strip()[:50] or 'General',
                'created_by': request.player})
        DailyWord.objects.filter(set_date=timezone.localdate()).update(active=False)
        daily = DailyWord.objects.create(word=word, set_by=request.player)
    return JsonResponse({'message': 'Palabra del Día establecida correctamente.', 'id': daily.id})


@endpoint(['POST'], auth=True)
def answer(request):
    data = body(request)
    daily_id = integer(data.get('dailyWordId'))
    letter = data.get('answerLetter')
    if not daily_id or not isinstance(letter, str) or len(letter.strip()) != 1:
        return error('Datos de respuesta inválidos o incompletos')
    letter = letter.strip().lower()
    with transaction.atomic():
        daily = DailyWord.objects.select_for_update().select_related('word').filter(
            pk=daily_id, set_date=timezone.localdate(), active=True).first()
        if not daily:
            return error('La palabra del día no está disponible o ya expiró', 404)
        if DailyWordAnswer.objects.filter(daily_word=daily, player=request.player).exists():
            return error('Ya has respondido a la palabra del día de hoy')
        correct = letter == daily.word.word[0].lower()
        elapsed = max(0, int((timezone.now() - daily.created_at).total_seconds() * 1000))
        base = {'easy': 10, 'medium': 25, 'hard': 50}[daily.word.difficulty]
        points = base + max(0, 100 - elapsed // 100) if correct else 0
        DailyWordAnswer.objects.create(daily_word=daily, player=request.player, answer_letter=letter,
                                       response_time_ms=elapsed, points_earned=points, is_correct=correct)
        if points:
            Player.objects.filter(pk=request.player.id).update(score=F('score') + points)
    return JsonResponse({'message': '¡Correcto!' if correct else 'Incorrecto', 'isCorrect': correct,
                         'answer': daily.word.word[0].upper(), 'pointsEarned': points,
                         'responseTimeMs': elapsed})


@endpoint(['GET'], auth=True)
def daily_leaderboard(request, daily_word_id):
    rows = DailyWordAnswer.objects.filter(daily_word_id=daily_word_id, is_correct=True).select_related('player').order_by('-points_earned', 'response_time_ms')[:10]
    return JsonResponse([{'id': row.player_id, 'name': row.player.name,
                          'first_name': row.player.first_name, 'last_name': row.player.last_name,
                          'response_time_ms': row.response_time_ms, 'points_earned': row.points_earned,
                          'is_correct': row.is_correct, 'rank': index}
                         for index, row in enumerate(rows, 1)], safe=False)
