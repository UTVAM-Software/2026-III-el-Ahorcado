# 2026-III-el-Ahorcado · Ahorcado UTVAM

Aplicación Django para alumnos y profesores. La interfaz usa JavaScript modular y la API Django mantiene las rutas `/api/` conocidas por el navegador.

## Estructura

- `ahorcado/`: configuración, rutas y puntos de entrada WSGI/ASGI.
- `nucleo/models.py`: modelos de PostgreSQL compatibles con las tablas anteriores.
- `nucleo/api.py`: JSON, autenticación JWT y permisos compartidos.
- `nucleo/views_*.py`: endpoints de cuentas, palabras, partidas, actividades y palabra del día.
- `nucleo/ai.py`: integración con Gemini.
- `interfaz/`: interfaz y recursos estáticos.
- `nucleo/migrations/`: esquema inicial para instalaciones nuevas.
- `documentacion/`: diagramas del proyecto.
- `archivos_estaticos/`: archivos estáticos compilados para producción.

## Modelos de datos (ORM)

Los modelos están en `nucleo/models.py` y Django los persiste en PostgreSQL. Las claves primarias son enteros autoincrementales y las relaciones se declaran con `ForeignKey`.

| Modelo | Tabla | Propósito y relaciones |
| --- | --- | --- |
| `Player` | `players` | Cuenta de alumno o profesor; nombre y correo únicos, rol y puntuación. Los alumnos guardan grado y grupo para filtrar asignaciones. |
| `Word` | `words` | Palabra única con dificultad, tema y creador opcional. |
| `AssignedGame` | `assigned_games` | Actividad de un profesor para un alumno; conserva los IDs de palabras en un arreglo PostgreSQL y el avance/estado. |
| `Game` | `games` | Partida de un jugador asociada a una palabra y, opcionalmente, a una actividad; guarda letras, intentos, estado y fechas. |
| `DailyWord` | `daily_words` | Palabra diaria con fecha, estado activo y jugador que la seleccionó opcionalmente. |
| `DailyWordAnswer` | `daily_word_answers` | Respuesta de un jugador a la palabra diaria; impide más de una respuesta por jugador y palabra diaria. |

Relaciones principales: `Player` tiene palabras creadas, actividades como profesor o alumno, partidas y respuestas diarias. `Word` puede usarse en muchas partidas y palabras diarias. Al borrar un jugador, sus partidas/actividades/respuestas se eliminan; las palabras referenciadas por partidas o palabras diarias se protegen; el creador de una palabra o quien seleccionó la palabra diaria se conserva como nulo si se elimina.

Los campos `ArrayField` (`AssignedGame.word_ids`, `Game.guessed` y `Game.wrong`) requieren PostgreSQL. Las dificultades válidas son `easy`, `medium` y `hard`; los roles son `student` y `teacher`.

### Operaciones ORM frecuentes

```python
from nucleo.models import Game, Player, Word

player = Player.objects.get(email="alumno@example.com")
palabras = Word.objects.filter(difficulty="easy").order_by("word")
partidas = Game.objects.filter(player=player).select_related("word")
```

Después de modificar modelos, genera y aplica una migración:

```bash
python manage.py makemigrations
python manage.py migrate
```

La migración inicial está en `nucleo/migrations/0001_initial.py`. La etiqueta histórica `core` se conserva en Django para mantener el historial de migraciones y las tablas existentes. Para una base creada anteriormente por la versión Express, consulta la sección de migración y usa `--fake-initial` tras respaldar la base.

## Instalación nueva

Requiere Python 3.10 o superior y PostgreSQL.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configura `DATABASE_URL`, `DJANGO_SECRET_KEY` y `JWT_SECRET` en `.env`. Para el inicio de sesión con Google y el registro con Google también se requieren `SUPABASE_URL` y `SUPABASE_KEY` (la clave pública `anon`/publishable; **nunca** uses la `service_role` en el navegador). El registro público por correo está desactivado; las cuentas existentes conservan el inicio de sesión con usuario/correo y contraseña. La recuperación de contraseña requiere SMTP: configura `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` o `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL` y `PUBLIC_APP_URL`. El proyecto carga `.env` automáticamente en local; en producción, define estas variables en la configuración de secretos del proveedor. Mantenlo privado: contiene credenciales y está excluido del control de versiones.

Si Django muestra `password authentication failed` al conectar con Supabase, actualiza la contraseña dentro de `DATABASE_URL` en tu `.env` con la contraseña vigente de la base de datos (no la `anon key` ni la contraseña de tu cuenta de Supabase). Si la contraseña fue restablecida, actualiza también el secreto `DATABASE_URL` en Vercel y vuelve a desplegar. No publiques ni compartas esa URL. Si no usas una URL completa, puedes definir `SUPABASE_DB_PASSWORD`; el proyecto no incluye una contraseña predeterminada.

```dotenv
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_KEY=<clave_publica_anon_o_publishable>
```

Para habilitar Google, reemplaza el valor de ejemplo de `SUPABASE_KEY` por la clave pública de tu proyecto Supabase y activa Google en **Authentication > Sign In / Providers**. En Google Cloud configura como URI de redirección autorizada la que Supabase muestra para el proveedor, normalmente `https://<PROJECT_REF>.supabase.co/auth/v1/callback`. En **Authentication > URL Configuration** añade como URLs de redirección permitidas `http://localhost:4000/auth/callback/`, `http://127.0.0.1:4000/auth/callback/`, `http://localhost:8000/auth/callback/`, `http://127.0.0.1:8000/auth/callback/` y la URL equivalente de producción. La aplicación verifica en Django el token recibido; el registro con Google pide al usuario crear una contraseña para que también pueda iniciar sesión con su usuario. No vincula automáticamente una cuenta Google a una cuenta existente con el mismo correo.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_words
python manage.py runserver 4000
```

Visita `http://localhost:4000/`. Para probar la navegación como visitante sin cuenta, abre `http://localhost:4000/visita/`; permite jugar localmente con palabras reales del banco, consultar el banco y los rankings en modo de solo lectura, y no guarda cambios ni resultados. Las listas de alumnos y partidas asignadas requieren iniciar sesión como profesor. El panel de gestión de Django está en `http://localhost:4000/gestion/`; entra con el superusuario creado arriba. La autenticación de Gestión es independiente del acceso público con Google. Al abrir **Usuarios Django**, el panel sincroniza las cuentas principales con `auth.User`; los roles `student` y `teacher` se reflejan en los grupos `Alumno` y `Profesor`. El panel muestra solo módulos para los que la cuenta tiene permisos; un superusuario puede asignar permisos y grupos desde **Usuarios Django** y **Grupos Django**. Gemini es opcional y usa `GEMINI_API_KEY`.

En esta Mac se instaló PostgreSQL 17 con Homebrew como servicio de inicio de sesión. La base local se llama `ahorcado_django`, usa el rol `ahorcado_app` y su conexión está en `.env`. Ya tiene las migraciones y las 15 palabras iniciales. Para comprobar el servicio o iniciarlo manualmente:

```bash
brew services list
brew services start postgresql@17
```

## Migración de una base Express existente

Usa la misma conexión PostgreSQL y **el mismo `JWT_SECRET`** para conservar las sesiones. Haz una copia de la base antes del cambio. Las tablas anteriores coinciden con los modelos; registra la migración inicial sin recrearlas:

```bash
python manage.py migrate --fake-initial
```

Para producción, configura `ALLOWED_HOSTS`, sirve el sitio por HTTPS, ejecuta `python manage.py collectstatic --noinput` y arranca `gunicorn ahorcado.wsgi:application`. WhiteNoise sirve los archivos estáticos.

## Respaldo del servidor anterior

`backups/express-pre-django-2026-09-18.tar.gz` contiene los archivos Express y la configuración anterior. Tiene permisos privados y se excluye del control de versiones. Conserva este respaldo en un lugar seguro hasta verificar el despliegue Django.

## Publicar en GitHub

Este directorio debe subirse a un repositorio GitHub creado para el proyecto. Antes de publicar, revisa que `.env` y cualquier respaldo con datos o secretos no estén versionados. El `.gitignore` ya excluye `.env`, entornos virtuales, archivos compilados y respaldos.

```bash
git remote -v
git add .
git status
git commit -m "Documenta modelos Django y estructura del proyecto"
git push origin main
```

El repositorio del proyecto es `https://github.com/UTVAM-Software/2026-III-el-Ahorcado`. GitHub debe contener el código y este README, nunca el `.env` real, el entorno virtual ni copias de la base de datos.
