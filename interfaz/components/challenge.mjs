import { setState } from './state.mjs';
import { setMessage } from './ui.mjs';
import { createGame, loadDailyChallenge, submitGuess, loadGameExplanation } from './api.mjs';
import { celebrate, createSoundEngine } from './effects.mjs';

const alphabet = 'abcdefghijklmnñopqrstuvwxyz'.split('');

export function initDailyChallenge({ elements }) {
  const {
    challengeWaiting,
    challengeGame,
    challengeResult,
    challengeLeaderboard,
    challengeMaskedWord,
    challengeDifficultyBadge,
    challengeStatus,
    challengeLettersRow,
    challengeAttemptsEl,
    challengeWrongAttemptsEl,
    challengeHangmanParts,
    challengeAttemptMeterFill,
    challengeHintArea,
    challengeSolveForm,
    challengeSolveInput,
    challengeMessage,
  } = elements;

  const sounds = createSoundEngine();
  let dailyGameId = null;
  let currentGame = null;
  const pendingLetters = new Set();
  let explainedGameId = null;

  function renderHangman(wrongAttempts = 0, shouldAnimate = false) {
    challengeHangmanParts?.forEach((part) => {
      const shouldBeVisible = Number(part.dataset.step) <= wrongAttempts;
      const wasVisible = part.classList.contains('visible');

      part.classList.toggle('visible', shouldBeVisible);
      if (shouldBeVisible && !wasVisible) {
        part.classList.remove('part-appearing');
        void part.getBoundingClientRect();
        part.classList.add('part-appearing');
      }
    });

    const stage = challengeHangmanParts?.[0]?.closest('.hangman-stage');
    if (shouldAnimate && stage) {
      stage.classList.remove('is-animating');
      void stage.offsetWidth;
      stage.classList.add('is-animating');
    } else if (wrongAttempts === 0) {
      stage?.classList.remove('is-animating');
    }

    if (challengeAttemptMeterFill) {
      challengeAttemptMeterFill.style.width = `${Math.min(100, (wrongAttempts / 6) * 100)}%`;
    }
  }

  function renderKeypad(guessed = [], wrong = [], status = 'playing') {
    if (!challengeLettersRow) return;
    challengeLettersRow.innerHTML = '';
    const correctSet = new Set(guessed || []);
    const wrongSet = new Set(wrong || []);

    alphabet.forEach((letter) => {
      const isPending = pendingLetters.has(letter);
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = letter.toUpperCase();
      button.dataset.letter = letter;
      button.disabled = status !== 'playing' || isPending || correctSet.has(letter) || wrongSet.has(letter);
      if (isPending) button.classList.add('used', 'pending');
      if (correctSet.has(letter)) button.classList.add('used', 'correct');
      if (wrongSet.has(letter)) button.classList.add('used', 'wrong');
      const activateLetter = (event) => {
        event.preventDefault();
        if (button.disabled) return;
        button.blur();
        handleGuess(letter);
      };
      button.addEventListener('pointerdown', activateLetter);
      button.addEventListener('touchstart', activateLetter, { passive: false });
      button.addEventListener('mousedown', activateLetter);
      button.addEventListener('click', (event) => {
        if (event.detail === 0) handleGuess(letter);
      });
      challengeLettersRow.appendChild(button);
    });
  }

  function getLetterButton(letter) {
    return challengeLettersRow?.querySelector(`button[data-letter="${letter}"]`);
  }

  function isAlreadyTried(letter) {
    return pendingLetters.has(letter) || currentGame?.guessedLetters?.includes(letter) || currentGame?.wrongLetters?.includes(letter);
  }

  function markLetterPending(letter) {
    const button = getLetterButton(letter);
    if (!button || button.disabled) return;
    pendingLetters.add(letter);
    button.classList.add('used', 'pending');
    button.disabled = true;
  }

  function clearLetterPending(letter) {
    pendingLetters.delete(letter);
    const button = getLetterButton(letter);
    if (!button?.classList.contains('pending')) return;
    button.classList.remove('used', 'pending');
    button.disabled = false;
  }

  function announceResult(data) {
    if (data.status === 'won') {
      sounds.win();
      celebrate();
      setMessage(challengeMessage, `🎉 ¡Excelente! Adivinaste “${data.word}”.`);
      challengeMessage?.classList.add('result-message', 'win');
    } else if (data.status === 'lost') {
      sounds.lose();
      setMessage(challengeMessage, `La palabra era “${data.word}”. Inténtalo de nuevo mañana.`);
      challengeMessage?.classList.add('result-message', 'lose');
    }
  }

  async function showLearningExplanation(data) {
    if (!data?.id || data.status === 'playing' || explainedGameId === data.id || !challengeHintArea) return;
    explainedGameId = data.id;
    challengeHintArea.textContent = 'Generando explicación de aprendizaje...';
    try {
      const { response, data: explanationData } = await loadGameExplanation(data.id);
      if (!response.ok || !explanationData.explanation) {
        challengeHintArea.textContent = data.learningHint || 'Repasa la palabra del día antes de volver al inicio.';
        return;
      }
      challengeHintArea.textContent = `Aprendizaje: ${explanationData.explanation}`;
    } catch {
      challengeHintArea.textContent = data.learningHint || 'Repasa la palabra del día antes de volver al inicio.';
    }
  }

  function renderGame(data) {
    const wasPlaying = currentGame?.status === 'playing';
    const newCorrectGuess = currentGame && data.guessedLetters?.length > currentGame.guessedLetters?.length;
    const newWrongGuess = currentGame && data.wrongAttempts > currentGame.wrongAttempts;
    [...pendingLetters].forEach((letter) => {
      if (data.guessedLetters?.includes(letter) || data.wrongLetters?.includes(letter)) {
        pendingLetters.delete(letter);
      }
    });
    dailyGameId = data.id;
    if (challengeMaskedWord) challengeMaskedWord.textContent = data.masked;
    if (challengeAttemptsEl) challengeAttemptsEl.textContent = data.attempts;
    if (challengeWrongAttemptsEl) challengeWrongAttemptsEl.textContent = data.wrongAttempts;
    if (challengeDifficultyBadge) {
      challengeDifficultyBadge.textContent = `Dificultad: ${data.difficulty === 'easy' ? 'fácil' : data.difficulty === 'medium' ? 'media' : 'difícil'}`;
    }
    if (challengeStatus) {
      challengeStatus.textContent = data.status === 'playing'
        ? 'Partida diaria'
        : data.status === 'won'
          ? '¡Palabra descubierta!'
          : 'Fin de la partida diaria';
    }
    if (challengeHintArea) {
      challengeHintArea.textContent = data.hint
        ? `Pista: se reveló la letra “${data.hint.toUpperCase()}”. ${data.learningHint || ''}`.trim()
        : 'Recibes una pista cada dos fallos.';
    }
    renderHangman(data.wrongAttempts, Boolean(newWrongGuess));
    renderKeypad(data.guessedLetters, data.wrongLetters, data.status);

    challengeMessage?.classList.remove('result-message', 'win', 'lose');
    if (data.status !== 'playing') {
      if (wasPlaying || !currentGame) {
        announceResult(data);
      }
      showLearningExplanation(data);
    } else if (newCorrectGuess) {
      sounds.correct();
      setMessage(challengeMessage, '¡Bien! Esa letra sí está en la palabra.');
    } else if (newWrongGuess) {
      sounds.wrong();
      setMessage(challengeMessage, `Esa letra no aparece. Te quedan ${6 - data.wrongAttempts} oportunidades.`);
    } else {
      setMessage(challengeMessage, 'Selecciona una letra para resolver la palabra del día.');
    }

    currentGame = data;
  }

  async function handleGuess(letter) {
    if (!dailyGameId) return;
    const normalized = String(letter || '').toLowerCase();
    if (!alphabet.includes(normalized) || isAlreadyTried(normalized)) return;
    markLetterPending(normalized);
    setMessage(challengeMessage, `Probando “${normalized.toUpperCase()}”...`);
    try {
      const { response, data } = await submitGuess(normalized, dailyGameId);
      if (response.ok) renderGame(data);
      else {
        clearLetterPending(normalized);
        setMessage(challengeMessage, data.error || 'No se pudo procesar la letra.');
      }
    } catch {
      clearLetterPending(normalized);
      setMessage(challengeMessage, 'No se pudo conectar con el servidor.');
    } finally {
      pendingLetters.delete(normalized);
    }
  }

  async function loadChallenge() {
    try {
      if (challengeWaiting) challengeWaiting.classList.remove('hidden');
      if (challengeGame) challengeGame.classList.add('hidden');
      if (challengeResult) challengeResult.classList.add('hidden');
      if (challengeLeaderboard) challengeLeaderboard.classList.add('hidden');
      setMessage(challengeWaiting, 'Comprobando disponibilidad del servidor...');
      currentGame = null;
      explainedGameId = null;
      pendingLetters.clear();

      const { response, data } = await loadDailyChallenge();
      if (!response.ok || !data.wordId) {
        setMessage(challengeWaiting, data.message || data.error || 'No hay palabra del día configurada.');
        return;
      }

      setState({ dailyWordId: data.id });
      const gameResponse = await createGame(data.difficulty, data.wordId);
      if (!gameResponse.response.ok) {
        setMessage(challengeWaiting, gameResponse.data.error || 'No se pudo iniciar la palabra del día.');
        return;
      }

      if (challengeWaiting) challengeWaiting.classList.add('hidden');
      if (challengeGame) challengeGame.classList.remove('hidden');
      if (challengeSolveInput) challengeSolveInput.value = '';
      renderGame(gameResponse.data);
    } catch (error) {
      console.error('Error loading daily hangman:', error);
      setMessage(challengeWaiting, 'Error cargando la palabra del día.');
    }
  }

  challengeSolveInput?.addEventListener('input', () => {
    challengeSolveInput.value = challengeSolveInput.value.replace(/[^a-zA-ZñÑáéíóúÁÉÍÓÚüÜ]/g, '').slice(0, 1);
  });

  challengeSolveForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    const guess = challengeSolveInput?.value.trim().toLowerCase();
    if (guess?.length === 1) handleGuess(guess);
    else setMessage(challengeMessage, 'Ingresa una sola letra.');
    if (challengeSolveInput) challengeSolveInput.value = '';
  });

  return { loadChallenge };
}
