import { state } from './state.mjs';

/**
 * Un wrapper de fetch centralizado para todas las llamadas a la API.
 * Automáticamente añade el 'Content-Type' y el token de autorización si está disponible.
 * También parsea la respuesta JSON.
 * @param {string} url - La URL del endpoint de la API.
 * @param {object} options - Las opciones para la petición fetch.
 * @returns {Promise<{response: Response, data: any}>}
 */
export async function apiFetch(url, options = {}) {
  const requestOptions = { ...options };

  requestOptions.headers = {
    'Content-Type': 'application/json',
    ...requestOptions.headers,
  };

  if (state.token) {
    requestOptions.headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(url, requestOptions);
  let data = {};
  try {
    const text = await response.text();
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {};
  }

  if (!response.ok && !data.error) {
    if (response.status === 503) {
      data.error = 'Base de datos temporalmente no disponible (503). Si estás usando Supabase, verifica que el proyecto no esté pausado.';
    } else if (response.status >= 500) {
      data.error = `Error interno en el servidor (${response.status}).`;
    }
  }

  return { response, data };
}

export async function registerUser(userData) {
  return apiFetch('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
}

export async function loginUser(usernameOrEmail, password) {
  return apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ credential: usernameOrEmail, password }),
  });
}

export async function deleteMyAccount(password) {
  return apiFetch('/api/auth/me', {
    method: 'DELETE',
    body: JSON.stringify({ password }),
  });
}

export async function loadLeaderboard() {
  return apiFetch('/api/leaderboard');
}

export async function createGame(difficulty, wordId = null, assignmentId = null) {
  return apiFetch('/api/game', {
    method: 'POST',
    body: JSON.stringify({ difficulty, wordId, assignmentId }),
  });
}

export async function submitGuess(letter, gameId) {
  return apiFetch('/api/game/guess', {
    method: 'POST',
    body: JSON.stringify({ gameId, letter }),
  });
}

export async function loadGameExplanation(gameId) {
  return apiFetch('/api/game/explain', {
    method: 'POST',
    body: JSON.stringify({ gameId }),
  });
}

export async function loadMyAssignments() {
  return apiFetch('/api/assignments/mine');
}

export async function loadWordsForTeacher() {
  return apiFetch('/api/words');
}

export async function setDailyWord(payload) {
  const body = typeof payload === 'object' && payload !== null ? payload : { wordId: payload };
  return apiFetch('/api/daily-words', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function loadDailyChallenge() {
  return apiFetch('/api/daily-words');
}

export async function submitDailyChallengeAnswer(dailyWordId, answerLetter) {
  return apiFetch('/api/daily-words/answer', {
    method: 'POST',
    body: JSON.stringify({ dailyWordId, answerLetter }),
  });
}

export async function loadDailyChallengeLeaderboard(dailyWordId) {
  return apiFetch(`/api/daily-words/leaderboard/${dailyWordId}`);
}
