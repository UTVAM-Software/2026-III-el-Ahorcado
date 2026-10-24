"""Único punto de acceso a Gemini para palabras y explicaciones."""
import os
from google import genai
from google.genai import types

MODELS = ('gemini-flash-latest', 'gemini-3.8-flash')
REQUEST_TIMEOUT_MS = 60_000


def generate(prompt):
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        return None, None
    configured = os.getenv('GEMINI_MODEL', MODELS[0]).removeprefix('models/')
    if configured == 'gemini-pro':
        configured = MODELS[0]
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    last_error = None
    for model in dict.fromkeys((configured, *MODELS)):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return (response.text or '').strip(), model
        except Exception as exc:
            if getattr(exc, 'code', None) != 404:
                raise
            last_error = exc
    raise last_error
