import { setMessage, showPanel } from './ui.mjs';
import { loadCurrentDailyChallengeLeaderboard, loadLeaderboard, loadVisitorWords } from './api.mjs?v=20261110-visitor-db-words';

const byId = (id) => document.getElementById(id);
const panels = {
  login: byId('login-layout'),
  home: byId('home-panel'),
  game: byId('game-panel'),
  settings: byId('settings-panel'),
  teacher: byId('teacher-panel'),
  challenge: byId('speed-challenge-panel'),
};
const hiddenPanels = [panels.login, panels.home, panels.game, panels.settings, panels.teacher, panels.challenge];
const visitorButton = byId('visitor-login-btn');
const loginForm = byId('login-form');
const guessedLetters = new Set();
const challengeLetters = new Set();
let wordBank = [];
let currentGameWord = null;
const dailyWord = 'UTVAM';
let wrongGuesses = 0;
let dailyWrongGuesses = 0;
let rankingRequestId = 0;
let rankingSearchTimeout;

function showOnly(panel) {
  hiddenPanels.forEach((item) => showPanel(item, item === panel));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function renderRanking() {
  const ranking = byId('ranking-list');
  if (!ranking) return;
  const requestId = ++rankingRequestId;
  const query = byId('searchInput')?.value.trim().toLocaleLowerCase('es') || '';
  const limit = byId('limitFilter')?.value || '10';
  ranking.textContent = 'Cargando ranking…';

  try {
    const { response, data } = await loadLeaderboard(query, limit);
    if (requestId !== rankingRequestId) return;
    if (!response.ok || !Array.isArray(data)) {
      throw new Error(data.error || `El servidor respondió con estado ${response.status}.`);
    }

    if (data.length === 0) {
      ranking.textContent = 'Aún no hay jugadores en el ranking.';
      return;
    }

    ranking.replaceChildren(...data.map((player) => {
      const item = document.createElement('li');
      item.textContent = `${player.name} — ${player.score} pts`;
      return item;
    }));
  } catch (error) {
    if (requestId !== rankingRequestId) return;
    console.error('Error al cargar el ranking real en modo visita:', error);
    ranking.textContent = 'El ranking real no está disponible por el momento. Intenta de nuevo más tarde.';
  }
}

function resetGame() {
  const difficulty = byId('difficulty')?.value || 'easy';
  const matchingWords = wordBank.filter((item) => item.difficulty === difficulty);
  const availableWords = matchingWords.length ? matchingWords : wordBank;
  if (!availableWords.length) {
    currentGameWord = null;
    byId('game-status').textContent = 'Partida no disponible';
    byId('game-difficulty').textContent = 'No se pudieron cargar palabras de la base de datos.';
    byId('hint-area').textContent = 'Intenta recargar la página para volver a consultar el banco.';
    byId('game-message').textContent = 'No hay palabras disponibles para jugar en este momento.';
    byId('masked-word').textContent = '';
    byId('start-game-btn').disabled = true;
    byId('new-game').classList.add('hidden');
    return;
  }

  currentGameWord = availableWords[Math.floor(Math.random() * availableWords.length)];
  guessedLetters.clear();
  wrongGuesses = 0;
  byId('game-status').textContent = 'Partida local de visita';
  byId('game-difficulty').textContent = `Dificultad: ${difficultyLabel(currentGameWord.difficulty)} · ${currentGameWord.theme}`;
  byId('attempts').textContent = '0';
  byId('wrong-attempts').textContent = '0';
  byId('hint-area').textContent = `Tema: ${currentGameWord.theme}. Encuentra la palabra antes de quedarte sin intentos.`;
  byId('game-message').textContent = '';
  byId('new-game').classList.add('hidden');
  byId('hangman-parts').querySelectorAll('[data-step]').forEach((part) => part.classList.remove('visible'));
  byId('attempt-meter-fill').style.width = '0%';
  renderWord(currentGameWord.word.toLocaleUpperCase('es'), guessedLetters, byId('masked-word'));
  renderKeyboard(byId('letters-row'), guessedLetters, (letter) => guessLetter(letter));
}

function difficultyLabel(difficulty) {
  return { easy: 'fácil', medium: 'media', hard: 'difícil' }[difficulty] || difficulty;
}

function renderWord(word, letters, target) {
  target.textContent = [...word].map((letter) => letters.has(normalizeGameLetter(letter)) ? letter : '_').join(' ');
}

function normalizeGameLetter(letter) {
  return letter.toLocaleUpperCase('es')
    .replace(/Ñ/g, '\0')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\0/g, 'Ñ');
}

function renderKeyboard(target, letters, onGuess) {
  target.replaceChildren();
  'ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'.split('').forEach((letter) => {
    const key = document.createElement('button');
    key.type = 'button';
    key.textContent = letter;
    key.disabled = letters.has(letter);
    key.addEventListener('click', () => onGuess(letter));
    target.appendChild(key);
  });
}

function finishGame(won) {
  byId('game-status').textContent = won ? '¡Palabra descubierta!' : 'Fin de la partida local';
  byId('game-message').textContent = won
    ? '¡Excelente! Esta partida solo existe en tu navegador y no se guarda en la base.'
    : `La palabra era ${currentGameWord.word.toLocaleUpperCase('es')}. Puedes iniciar otra partida local.`;
  byId('new-game').classList.remove('hidden');
}

function guessLetter(letter) {
  if (!currentGameWord) return;
  const normalized = normalizeGameLetter(letter.trim());
  if (!/^[A-ZÑ]$/.test(normalized) || guessedLetters.has(normalized)) return;
  guessedLetters.add(normalized);
  const word = currentGameWord.word.toLocaleUpperCase('es');
  const normalizedWord = [...word].map(normalizeGameLetter);
  if (!normalizedWord.includes(normalized)) {
    wrongGuesses += 1;
    byId('hangman-parts').querySelector(`[data-step="${wrongGuesses}"]`)?.classList.add('visible');
  }
  byId('attempts').textContent = String(guessedLetters.size);
  byId('wrong-attempts').textContent = String(wrongGuesses);
  byId('attempt-meter-fill').style.width = `${Math.min(wrongGuesses / 6, 1) * 100}%`;
  renderWord(word, guessedLetters, byId('masked-word'));
  renderKeyboard(byId('letters-row'), guessedLetters, guessLetter);
  if (normalizedWord.every((item) => guessedLetters.has(item))) finishGame(true);
  else if (wrongGuesses >= 6) finishGame(false);
}

function resetDailyChallenge() {
  challengeLetters.clear();
  dailyWrongGuesses = 0;
  byId('challenge-game').classList.remove('hidden');
  byId('challenge-result').classList.add('hidden');
  byId('challenge-leaderboard').classList.add('hidden');
  byId('challenge-status').textContent = 'Reto diario de demostración';
  byId('challenge-difficulty-badge').textContent = 'Dificultad: fácil · reto de muestra';
  byId('challenge-attempts').textContent = '0';
  byId('challenge-wrong-attempts').textContent = '0';
  byId('challenge-hint-area').textContent = 'Pista de muestra: nombre corto de la institución.';
  byId('challenge-message').textContent = '';
  byId('challenge-hangman-parts').querySelectorAll('[data-step]').forEach((part) => part.classList.remove('visible'));
  byId('challenge-attempt-meter-fill').style.width = '0%';
  renderWord(dailyWord, challengeLetters, byId('challenge-masked-word'));
  renderKeyboard(byId('challenge-letters-row'), challengeLetters, guessDailyLetter);
}

function finishDailyChallenge(won) {
  byId('challenge-game').classList.add('hidden');
  byId('challenge-result').classList.remove('hidden');
  byId('result-title').textContent = won ? '¡Reto completado!' : 'Fin del reto de muestra';
  byId('result-message').textContent = won
    ? 'Tu resultado es local y no se guarda en el ranking real.'
    : `La palabra de muestra era ${dailyWord}.`;
  byId('result-points').textContent = won ? '+20' : '+0';
  byId('result-time').textContent = '00:38';
}

function guessDailyLetter(letter) {
  const normalized = letter.trim().toLocaleUpperCase('es');
  if (!/^[A-ZÑ]$/.test(normalized) || challengeLetters.has(normalized)) return;
  challengeLetters.add(normalized);
  if (!dailyWord.includes(normalized)) {
    dailyWrongGuesses += 1;
    byId('challenge-hangman-parts').querySelector(`[data-step="${dailyWrongGuesses}"]`)?.classList.add('visible');
  }
  byId('challenge-attempts').textContent = String(challengeLetters.size);
  byId('challenge-wrong-attempts').textContent = String(dailyWrongGuesses);
  byId('challenge-attempt-meter-fill').style.width = `${Math.min(dailyWrongGuesses / 6, 1) * 100}%`;
  renderWord(dailyWord, challengeLetters, byId('challenge-masked-word'));
  renderKeyboard(byId('challenge-letters-row'), challengeLetters, guessDailyLetter);
  if ([...dailyWord].every((item) => challengeLetters.has(item))) finishDailyChallenge(true);
  else if (dailyWrongGuesses >= 6) finishDailyChallenge(false);
}

function renderTeacherWords() {
  const bank = byId('teacher-word-bank');
  if (!wordBank.length && bank) {
    bank.textContent = 'No hay palabras disponibles en la base de datos.';
  } else if (bank) {
    bank.replaceChildren(...wordBank.map((item) => {
      const card = document.createElement('article');
      card.className = 'word-chip';
      card.dataset.word = item.word;
      card.dataset.theme = item.theme;
      const word = document.createElement('strong');
      word.textContent = item.word;
      const details = document.createElement('span');
      details.textContent = `${item.theme} · ${difficultyLabel(item.difficulty)}`;
      card.append(word, details);
      return card;
    }));
  }

  const themes = [...new Set(wordBank.map((item) => item.theme))];
  const themeFilter = byId('theme-filter');
  if (themeFilter) {
    themeFilter.replaceChildren(new Option('Todos los temas', ''), ...themes.map((theme) => new Option(theme, theme)));
  }

  const dailySelect = byId('daily-word-select');
  if (dailySelect) {
    dailySelect.replaceChildren(...(wordBank.length
      ? wordBank.map((item) => new Option(`${item.word} · ${item.theme}`, String(item.id)))
      : [new Option('No hay palabras disponibles', '')]));
  }

  byId('start-game-btn').disabled = wordBank.length === 0;
  if (wordBank.length) byId('game-message').textContent = '';
  filterWords();
}

function renderTeacherAccessPlaceholders() {
  const studentsContainer = byId('student-checklist');
  if (studentsContainer) {
    studentsContainer.textContent = 'La lista de alumnos requiere iniciar sesión como profesor.';
  }

  const assignments = byId('assigned-games-list');
  if (assignments) {
    assignments.textContent = 'Las partidas asignadas requieren iniciar sesión como profesor.';
  }
}

async function loadVisitorWordBank() {
  const bank = byId('teacher-word-bank');
  if (bank) bank.textContent = 'Cargando palabras de la base de datos…';
  try {
    const { response, data } = await loadVisitorWords();
    if (!response.ok || !Array.isArray(data)) {
      throw new Error(data.error || `El servidor respondió con estado ${response.status}.`);
    }
    wordBank = data.filter((item) => item
      && Number.isInteger(item.id)
      && typeof item.word === 'string'
      && typeof item.theme === 'string'
      && ['easy', 'medium', 'hard'].includes(item.difficulty));
    renderTeacherWords();
  } catch (error) {
    console.error('Error al cargar las palabras reales en modo visita:', error);
    wordBank = [];
    if (bank) bank.textContent = 'No fue posible cargar el banco de palabras real. Intenta de nuevo más tarde.';
    byId('daily-word-select')?.replaceChildren(new Option('Banco no disponible', ''));
    byId('start-game-btn').disabled = true;
    byId('game-message').textContent = 'No fue posible cargar palabras para la partida.';
  }
}

function setUpVisitorMode() {
  document.body.classList.add('visitor-demo');
  byId('visitor-write-warning')?.classList.remove('hidden');
  document.querySelector('.management-shortcut')?.classList.add('hidden');
  byId('exit-visitor-mode')?.classList.remove('hidden');
  byId('login-btn')?.classList.add('hidden');
  byId('show-register-btn')?.classList.add('hidden');
  byId('google-login-btn')?.classList.add('hidden');
  byId('auth-name')?.classList.add('hidden');
  byId('auth-password')?.classList.add('hidden');
  document.querySelector('label[for="auth-name"]')?.classList.add('hidden');
  document.querySelector('label[for="auth-password"]')?.classList.add('hidden');
  document.querySelector('.password-recovery-link')?.classList.add('hidden');
  loginForm?.addEventListener('submit', (event) => event.preventDefault());

  const settings = byId('settings-btn');
  settings?.addEventListener('click', () => showOnly(panels.settings));
  byId('back-to-home-from-settings-btn')?.addEventListener('click', () => showOnly(panels.home));
  byId('back-to-home-btn')?.addEventListener('click', () => showOnly(panels.home));
  byId('back-to-home-from-challenge-btn')?.addEventListener('click', () => showOnly(panels.home));
  byId('back-to-home-from-teacher-btn')?.addEventListener('click', () => showOnly(panels.home));
  byId('play-game-btn')?.addEventListener('click', () => {
    resetGame();
    showOnly(panels.game);
  });
  byId('speed-challenge-btn')?.addEventListener('click', () => {
    resetDailyChallenge();
    showOnly(panels.challenge);
  });
  byId('teacher-btn')?.classList.remove('hidden');
  byId('teacher-btn')?.addEventListener('click', () => {
    byId('teacher-menu')?.classList.remove('hidden');
    document.querySelectorAll('.teacher-module').forEach((module) => module.classList.add('hidden'));
    showOnly(panels.teacher);
  });
  panels.teacher?.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) return;
    const moduleButton = event.target.closest('[data-teacher-module]');
    if (moduleButton) {
      const module = byId(moduleButton.getAttribute('data-teacher-module'));
      if (!module || !panels.teacher.contains(module)) return;
      byId('teacher-menu')?.classList.add('hidden');
      document.querySelectorAll('.teacher-module').forEach((item) => item.classList.add('hidden'));
      module.classList.remove('hidden');
      return;
    }
    if (event.target.closest('[data-back-to-teacher-menu]')) {
      document.querySelectorAll('.teacher-module').forEach((module) => module.classList.add('hidden'));
      byId('teacher-menu')?.classList.remove('hidden');
    }
  });
  byId('logout-btn')?.addEventListener('click', () => showOnly(panels.login));
  byId('settings-logout-btn')?.addEventListener('click', () => showOnly(panels.login));

  byId('start-game-btn')?.addEventListener('click', resetGame);
  byId('guess-btn')?.addEventListener('click', () => {
    guessLetter(byId('letter-input').value);
    byId('letter-input').value = '';
  });
  byId('letter-input')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      byId('guess-btn').click();
    }
  });
  byId('new-game')?.addEventListener('click', resetGame);
  byId('challenge-solve-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    guessDailyLetter(byId('challenge-solve-input').value);
    byId('challenge-solve-input').value = '';
  });
  byId('challenge-leaderboard-btn')?.addEventListener('click', async () => {
    byId('challenge-result').classList.add('hidden');
    byId('challenge-leaderboard').classList.remove('hidden');
    await renderDailyLeaderboard();
  });
  byId('challenge-back-btn')?.addEventListener('click', () => showOnly(panels.home));
  byId('searchInput')?.addEventListener('input', () => {
    window.clearTimeout(rankingSearchTimeout);
    rankingSearchTimeout = window.setTimeout(renderRanking, 250);
  });
  byId('limitFilter')?.addEventListener('change', renderRanking);
  byId('word-filter')?.addEventListener('input', filterWords);
  byId('theme-filter')?.addEventListener('change', filterWords);

  document.querySelectorAll('#teacher-panel form button[type="submit"], #delete-account-form button[type="submit"]').forEach((button) => {
    button.disabled = true;
    button.title = 'No disponible en el modo visita';
  });
  document.querySelectorAll('#teacher-panel form, #delete-account-form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      setMessage(form.querySelector('.message'), 'Modo visita: los cambios no se guardan.');
    });
  });
  byId('delete-account-password')?.setAttribute('disabled', '');
  document.querySelectorAll('#student-checklist input').forEach((input) => { input.disabled = true; });
  renderTeacherAccessPlaceholders();
  byId('teacher-word-bank').textContent = 'Cargando palabras de la base de datos…';
  byId('start-game-btn').disabled = true;
  loadVisitorWordBank();
  renderRanking();
  visitorButton?.addEventListener('click', enterAsVisitor);
  enterAsVisitor();
}

function filterWords() {
  const query = byId('word-filter')?.value.trim().toLocaleLowerCase('es') || '';
  const selectedTheme = byId('theme-filter')?.value || '';
  document.querySelectorAll('#teacher-word-bank .word-chip').forEach((card) => {
    const matchesText = card.dataset.word.toLocaleLowerCase('es').includes(query);
    const matchesTheme = !selectedTheme || card.dataset.theme === selectedTheme;
    card.classList.toggle('hidden', !matchesText || !matchesTheme);
  });
}

function enterAsVisitor() {
  byId('welcome-avatar').textContent = 'V';
  byId('welcome-name').textContent = 'Visitante';
  byId('welcome-role-text').textContent = 'Elige qué quieres hacer:';
  byId('settings-btn')?.classList.remove('hidden');
  showOnly(panels.home);
}

async function renderDailyLeaderboard() {
  const ranking = byId('challenge-ranking-list');
  if (!ranking) return;
  ranking.textContent = 'Cargando clasificación…';

  try {
    const { response, data } = await loadCurrentDailyChallengeLeaderboard();
    if (!response.ok || !Array.isArray(data.entries)) {
      throw new Error(data.error || `El servidor respondió con estado ${response.status}.`);
    }

    if (data.entries.length === 0) {
      ranking.textContent = data.message || 'Aún no hay respuestas correctas para la Palabra del Día.';
      return;
    }

    ranking.replaceChildren(...data.entries.map((entry) => {
      const item = document.createElement('li');
      item.textContent = `${entry.name} — ${entry.points} pts`;
      return item;
    }));
  } catch (error) {
    console.error('Error al cargar la clasificación real de la Palabra del Día:', error);
    ranking.textContent = 'La clasificación real no está disponible por el momento. Intenta de nuevo más tarde.';
  }
}

setUpVisitorMode();
