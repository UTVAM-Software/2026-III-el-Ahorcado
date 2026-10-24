import json
import random
import re
import unicodedata
from logging import getLogger

from django.db import IntegrityError, transaction
from django.http import JsonResponse

from .ai import generate as generate_content
from .api import body, endpoint, error, id_list, integer, word_data
from .models import DailyWord, Word

DIFFICULTIES = ('easy', 'medium', 'hard')
logger = getLogger(__name__)


def gemini_unavailable(exc, message):
    logger.exception('Gemini no pudo generar palabras.')
    if getattr(exc, 'code', None) == 504:
        return error('Gemini tardó demasiado en responder. Inténtalo de nuevo.', 504)
    return error(message, 502)


def sanitize_word(value):
    text = str(value or '').strip().lower().replace('ñ', '__enie__')
    text = ''.join(ch for ch in unicodedata.normalize('NFD', text) if not unicodedata.combining(ch))
    return re.sub('[^a-zñ]', '', text.replace('__enie__', 'ñ'))


def count_from(data):
    return max(1, min(integer(data.get('count')) or 5, 50))


def generated_words(theme, difficulty, count, teacher):
    prompt = (f'Genera exactamente {count} palabras en español para un juego de ahorcado con el tema '
              f'"{theme}" y dificultad "{difficulty}". Sin espacios, números ni caracteres especiales. '
              'Devuelve únicamente un array JSON de strings.')
    response, model = generate_content(prompt)
    if response is None:
        raise ValueError('La clave de API de Gemini no está configurada en el servidor.')
    match = re.search(r'\[.*\]', response, re.S)
    if not match:
        raise ValueError('La respuesta de la IA no tuvo el formato esperado.')
    raw = json.loads(match.group())
    if not isinstance(raw, list):
        raise ValueError('La respuesta de la IA no tuvo el formato esperado.')
    results = []
    for value in list(dict.fromkeys(sanitize_word(item) for item in raw))[:count]:
        if value:
            word, _ = Word.objects.update_or_create(word=value, defaults={'difficulty': difficulty, 'theme': theme, 'created_by': teacher})
            results.append(word_data(word))
    return results, model


@endpoint(['GET', 'POST'], auth=True, teacher=True)
def words(request):
    if request.method == 'GET':
        return JsonResponse([dict(word_data(word), created_by=word.created_by_id,
                                  created_at=word.created_at.isoformat())
                             for word in Word.objects.order_by('theme', 'word')], safe=False)
    data = body(request)
    word = sanitize_word(data.get('word'))
    difficulty = data.get('difficulty')
    if not word or not difficulty:
        return error('La palabra y la dificultad son obligatorias.')
    if difficulty not in DIFFICULTIES:
        return error('La dificultad no es válida.')
    assign_daily = data.get('assignDaily') is True
    try:
        with transaction.atomic():
            instance = Word.objects.create(word=word, difficulty=difficulty,
                                           theme=str(data.get('theme') or '').strip()[:50] or 'General',
                                           created_by=request.player)
            if assign_daily:
                from django.utils import timezone
                DailyWord.objects.filter(set_date=timezone.localdate()).update(active=False)
                DailyWord.objects.create(word=instance, set_by=request.player)
    except IntegrityError:
        return error('La palabra ya existe en el banco.')
    return JsonResponse({'message': f'Palabra "{word}" agregada' + (' y establecida como Palabra del Día.' if assign_daily else '.'),
                         'word': word_data(instance)}, status=201)


@endpoint(['POST'], auth=True, teacher=True)
def generate(request):
    data = body(request)
    theme = str(data.get('theme') or '').strip()[:50]
    if not theme:
        return error('El tema es obligatorio para generar palabras con IA.')
    difficulty = data.get('difficulty') if data.get('difficulty') in DIFFICULTIES else 'easy'
    try:
        results, model = generated_words(theme, difficulty, count_from(data), request.player)
    except (ValueError, json.JSONDecodeError) as exc:
        return error(str(exc))
    except Exception as exc:
        return gemini_unavailable(exc, 'Gemini no pudo generar palabras con los modelos disponibles.')
    if not results:
        return error('La IA no generó palabras válidas. Inténtalo de nuevo.', 404)
    return JsonResponse({'message': f'{len(results)} palabra(s) generadas y agregadas al banco.',
                         'theme': theme, 'model': model, 'words': results}, status=201)


@endpoint(['POST'], auth=True, teacher=True)
def prepare_game(request):
    data = body(request)
    difficulty = data.get('difficulty')
    if difficulty not in DIFFICULTIES:
        return error('La dificultad no es válida.')
    theme = str(data.get('theme') or '').strip()[:50]
    count = count_from(data)
    source = data.get('source')
    model = None
    if source == 'manual':
        rows = list(Word.objects.filter(id__in=id_list(data.get('wordIds'))))
        random.shuffle(rows)
        results = [word_data(row) for row in rows[:count]]
        theme = theme or 'Selección Manual'
    elif source == 'random':
        rows = Word.objects.filter(difficulty=difficulty)
        if theme:
            rows = rows.filter(theme__iexact=theme)
        results = [word_data(row) for row in rows.order_by('?')[:count]]
    elif source == 'ai':
        theme = theme or 'General'
        try:
            results, model = generated_words(theme, difficulty, count, request.player)
        except ValueError as exc:
            return error(str(exc))
        except Exception as exc:
            return gemini_unavailable(exc, 'Gemini no pudo generar palabras.')
    else:
        return error('Selecciona un origen válido para las palabras.')
    if not results:
        return error('No se encontraron palabras con los criterios seleccionados.', 404)
    return JsonResponse({'message': 'Partida preparada.', 'theme': theme or 'General', 'model': model, 'words': results})
