import { state, setState } from './components/state.mjs';
import { setMessage, showPanel } from './components/ui.mjs';
import { deleteMyAccount, loadLeaderboard as fetchLeaderboard, registerUser, loginUser } from './components/api.mjs';
import { saveSession, loadSession, clearSession as clearStoredSession } from './components/session.mjs';
import {
  getGoogleRegistrationDraft,
  getGoogleRegistrationProfile,
  registerWithGoogle,
  startGoogleAuth,
} from './components/google-auth.mjs?v=20261022-google-signup-recovery';
import { initTraditionalGame } from './components/game.mjs';
import { initDailyChallenge } from './components/challenge.mjs';
import { initTeacherPanel } from './components/teacher.mjs';

const APP_BUILD = '2026-07-18-auth-ui-fix';

const elements = {
  loginForm: document.getElementById('login-form'),
  authName: document.getElementById('auth-name'),
  authPassword: document.getElementById('auth-password'),
  showRegisterBtn: document.getElementById('show-register-btn'),
  googleLoginBtn: document.getElementById('google-login-btn'),
  authMessage: document.getElementById('auth-message'),
  rankingList: document.getElementById('ranking-list'),
  registerForm: document.getElementById('register-form'),
  registerChoice: document.getElementById('register-choice'),
  registerEmailStartBtn: document.getElementById('register-email-start'),
  registerTitle: document.getElementById('register-title'),
  registerDescription: document.getElementById('register-description'),
  registerUsername: document.getElementById('register-username'),
  registerFirstName: document.getElementById('register-first-name'),
  registerLastName: document.getElementById('register-last-name'),
  registerEmail: document.getElementById('register-email'),
  registerEmailField: document.getElementById('register-email-field'),
  registerEmailError: document.getElementById('register-email-error'),
  registerRole: document.getElementById('register-role'),
  studentRegistrationFields: document.getElementById('student-registration-fields'),
  registerGrade: document.getElementById('register-grade'),
  registerGroup: document.getElementById('register-group'),
  registerPassword: document.getElementById('register-password'),
  registerPasswordField: document.getElementById('register-password-field'),
  registerPasswordConfirmation: document.getElementById('register-password-confirmation'),
  googlePasswordConfirmation: document.getElementById('google-password-confirmation'),
  googlePasswordRequirements: document.getElementById('google-password-requirements'),
  registerFormBtn: document.getElementById('register-form-btn'),
  registerMessage: document.getElementById('register-message'),
  googleRegisterBtn: document.getElementById('google-register-btn'),
  googleRegisterRetryBtn: document.getElementById('google-register-retry-btn'),
  backToLoginBtn: document.getElementById('back-to-login'),
  loginLayout: document.getElementById('login-layout'),
  introPanel: document.getElementById('intro-panel'),
  homePanel: document.getElementById('home-panel'),
  settingsPanel: document.getElementById('settings-panel'),
  gamePanel: document.getElementById('game-panel'),
  teacherPanel: document.getElementById('teacher-panel'),
  speedChallengePanel: document.getElementById('speed-challenge-panel'),
  welcomeName: document.getElementById('welcome-name'),
  welcomeAvatar: document.getElementById('welcome-avatar'),
  playGameBtn: document.getElementById('play-game-btn'),
  speedChallengeBtn: document.getElementById('speed-challenge-btn'),
  teacherBtn: document.getElementById('teacher-btn'),
  settingsBtn: document.getElementById('settings-btn'),
  managementShortcut: document.getElementById('management-shortcut'),
  logoutBtn: document.getElementById('logout-btn'),
  settingsLogoutBtn: document.getElementById('settings-logout-btn'),
  backToHomeBtn: document.getElementById('back-to-home-btn'),
  backToHomeFromSettingsBtn: document.getElementById('back-to-home-from-settings-btn'),
  backToHomeFromTeacherBtn: document.getElementById('back-to-home-from-teacher-btn'),
  backToHomeFromChallengeBtn: document.getElementById('back-to-home-from-challenge-btn'),
  letterInput: document.getElementById('letter-input'),
  guessBtn: document.getElementById('guess-btn'),
  newGameBtn: document.getElementById('new-game'),
  startGameBtn: document.getElementById('start-game-btn'),
  assignmentSelect: document.getElementById('assignment-select'),
  difficultySelect: document.getElementById('difficulty'),
  lettersRow: document.getElementById('letters-row'),
  maskedWord: document.getElementById('masked-word'),
  attemptsEl: document.getElementById('attempts'),
  wrongAttemptsEl: document.getElementById('wrong-attempts'),
  hangmanParts: document.querySelectorAll('.hangman-part'),
  attemptMeterFill: document.getElementById('attempt-meter-fill'),
  difficultyEl: document.getElementById('game-difficulty'),
  gameStatusEl: document.getElementById('game-status'),
  hintArea: document.getElementById('hint-area'),
  gameMessage: document.getElementById('game-message'),
  wordForm: document.getElementById('word-form'),
  wordText: document.getElementById('word-text'),
  wordDifficulty: document.getElementById('word-difficulty'),
  wordTheme: document.getElementById('word-theme'),
  wordAssignDaily: document.getElementById('word-assign-daily'),
  aiWordForm: document.getElementById('ai-word-form'),
  aiWordTheme: document.getElementById('ai-word-theme'),
  aiWordCount: document.getElementById('ai-word-count'),
  aiWordDifficulty: document.getElementById('ai-word-difficulty'),
  aiWordMessage: document.getElementById('ai-word-message'),
  wordFilter: document.getElementById('word-filter'),
  themeFilter: document.getElementById('theme-filter'),
  teacherWordBank: document.getElementById('teacher-word-bank'),
  gameConfigForm: document.getElementById('game-config-form'),
  gameTheme: document.getElementById('game-theme'),
  gameWordCount: document.getElementById('game-word-count'),
  gameSource: document.getElementById('game-source'),
  gameConfigDifficulty: document.getElementById('game-config-difficulty'),
  gameConfigMessage: document.getElementById('game-config-message'),
  studentFilter: document.getElementById('student-filter'),
  studentGradeFilter: document.getElementById('student-grade-filter'),
  studentGroupFilter: document.getElementById('student-group-filter'),
  selectFilteredStudentsBtn: document.getElementById('select-filtered-students'),
  clearFilteredStudentsBtn: document.getElementById('clear-filtered-students'),
  studentChecklist: document.getElementById('student-checklist'),
  startPreparedGameBtn: document.getElementById('start-prepared-game-btn'),
  assignedGamesList: document.getElementById('assigned-games-list'),
  assignedGamesMessage: document.getElementById('assigned-games-message'),
  teacherMessage: document.getElementById('teacher-message'),
  dailyWordForm: document.getElementById('daily-word-form'),
  dailyWordSelect: document.getElementById('daily-word-select'),
  dailyWordText: document.getElementById('daily-word-text'),
  dailyWordTheme: document.getElementById('daily-word-theme'),
  dailyWordDifficulty: document.getElementById('daily-word-difficulty'),
  dailyWordMessage: document.getElementById('daily-word-message'),
  challengeWaiting: document.getElementById('challenge-waiting'),
  challengeGame: document.getElementById('challenge-game'),
  challengeResult: document.getElementById('challenge-result'),
  challengeLeaderboard: document.getElementById('challenge-leaderboard'),
  challengeMaskedWord: document.getElementById('challenge-masked-word'),
  challengeDifficultyBadge: document.getElementById('challenge-difficulty-badge'),
  challengeStatus: document.getElementById('challenge-status'),
  challengeLettersRow: document.getElementById('challenge-letters-row'),
  challengeAttemptsEl: document.getElementById('challenge-attempts'),
  challengeWrongAttemptsEl: document.getElementById('challenge-wrong-attempts'),
  challengeHangmanParts: document.querySelectorAll('.challenge-hangman-part'),
  challengeAttemptMeterFill: document.getElementById('challenge-attempt-meter-fill'),
  challengeHintArea: document.getElementById('challenge-hint-area'),
  challengeSolveForm: document.getElementById('challenge-solve-form'),
  challengeSolveInput: document.getElementById('challenge-solve-input'),
  challengeAnswerForm: document.getElementById('challenge-answer-form'),
  challengeLetterInput: document.getElementById('challenge-letter-input'),
  challengeMessage: document.getElementById('challenge-message'),
  timerText: document.getElementById('timer-text'),
  timerProgress: document.getElementById('timer-progress'),
  resultTitle: document.getElementById('result-title'),
  resultMessage: document.getElementById('result-message'),
  resultPoints: document.getElementById('result-points'),
  resultTime: document.getElementById('result-time'),
  challengeLeaderboardBtn: document.getElementById('challenge-leaderboard-btn'),
  challengeBackBtn: document.getElementById('challenge-back-btn'),
  challengeRankingList: document.getElementById('challenge-ranking-list'),
  deleteAccountForm: document.getElementById('delete-account-form'),
  deleteAccountPassword: document.getElementById('delete-account-password'),
  deleteAccountMessage: document.getElementById('delete-account-message'),
};

let leaderboardRequestId = 0;

export async function loadLeaderboard() {
  const rankingList = document.getElementById('ranking-list');
  if (!rankingList) return;

  const requestId = ++leaderboardRequestId;
  const search = document.getElementById('searchInput')?.value.trim() ?? '';
  const normalizedSearch = search.toLocaleLowerCase();
  const limit = document.getElementById('limitFilter')?.value ?? '10';

  try {
    const { response, data } = await fetchLeaderboard(search, limit);
    if (requestId !== leaderboardRequestId) return;
    if (!response.ok || !Array.isArray(data)) {
      throw new Error(data.error || 'Ranking no disponible');
    }

    const matchingPlayers = data.filter((player) =>
      player.name.toLocaleLowerCase().includes(normalizedSearch)
    );

    rankingList.innerHTML = '';

    if (matchingPlayers.length === 0) {
      rankingList.innerHTML = '<li>Aún no hay jugadores en el ranking.</li>';
      return;
    }

    matchingPlayers.forEach((player) => {
      const listItem = document.createElement('li');
      listItem.textContent = `${player.name} — ${player.score} pts`;
      rankingList.appendChild(listItem);
    });
  } catch (error) {
    if (requestId !== leaderboardRequestId) return;
    console.error('Error al cargar el ranking:', error);
    rankingList.innerHTML = '<li>El ranking no está disponible por el momento.</li>';
  }
}

function initializeLeaderboardFilters() {
  const searchInput = document.getElementById('searchInput');
  const limitFilter = document.getElementById('limitFilter');

  if (searchInput) {
    let searchTimeout;
    searchInput.addEventListener('input', () => {
      const search = searchInput.value.trim().toLocaleLowerCase();
      document.querySelectorAll('#ranking-list li').forEach((item) => {
        item.style.display = item.textContent.toLocaleLowerCase().includes(search) ? '' : 'none';
      });
      window.clearTimeout(searchTimeout);
      searchTimeout = window.setTimeout(loadLeaderboard, 250);
    });
  }
  if (limitFilter) {
    limitFilter.addEventListener('change', loadLeaderboard);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeLeaderboardFilters, { once: true });
} else {
  initializeLeaderboardFilters();
}
async function setUserSession(data) {
  setState({ token: data.token, user: data.user });
  saveSession(data.token, data.user);

  showPanel(elements.loginLayout, false);
  showPanel(elements.homePanel, true);
  showPanel(elements.settingsPanel, false);
  showPanel(elements.gamePanel, false);
  showPanel(elements.teacherPanel, false);
  showPanel(elements.speedChallengePanel, false);
  elements.managementShortcut?.classList.add('hidden');

  const displayName = typeof data.user.name === 'string' ? data.user.name.trim() : '';
  if (elements.welcomeName) elements.welcomeName.textContent = displayName;
  if (elements.welcomeAvatar) {
    elements.welcomeAvatar.textContent = displayName
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => Array.from(part)[0])
      .join('')
      .toLocaleUpperCase('es') || 'f';
  }
  elements.settingsBtn?.classList.remove('hidden');

  if (elements.teacherBtn) {
    if (data.user.role === 'teacher') {
      elements.teacherBtn.classList.remove('hidden');
      elements.teacherBtn.style.display = '';
      teacherController.loadDailyWordsOptions();
    } else {
      elements.teacherBtn.classList.add('hidden');
      elements.teacherBtn.style.display = 'none';
    }
  }

  await loadLeaderboard();
}

function logout() {
  clearStoredSession();
  setState({ token: null, user: null });
  elements.settingsBtn?.classList.add('hidden');
  elements.managementShortcut?.classList.remove('hidden');
  showPanel(elements.loginLayout, true);
  showPanel(elements.homePanel, false);
  showPanel(elements.settingsPanel, false);
  showPanel(elements.gamePanel, false);
  showPanel(elements.teacherPanel, false);
  showPanel(elements.speedChallengePanel, false);
  showPanel(elements.loginLayout, true);
  if (elements.authName) elements.authName.value = '';
  if (elements.authPassword) elements.authPassword.value = '';
  setMessage(elements.authMessage, 'Sesión cerrada');
}

const gameController = initTraditionalGame({
  elements,
  onGameReady: () => showPanel(elements.gamePanel, true),
});

const challengeController = initDailyChallenge({ elements });
const teacherController = initTeacherPanel({
  elements,
  onStartGame: async () => {
    showPanel(elements.teacherPanel, false);
    showPanel(elements.gamePanel, true);
    // Inicia directamente la partida preparada sin mostrar las opciones de alumno.
    await gameController.startNewGame();
  },
});

if (elements.loginForm) {
  elements.loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!elements.loginForm.checkValidity()) {
      elements.loginForm.reportValidity();
      return;
    }

    const { response, data } = await loginUser(elements.authName.value.trim(), elements.authPassword.value.trim());
    if (response.ok && data.token) {
      await setUserSession(data);
    } else {
      setMessage(elements.authMessage, data.error || 'Error de inicio de sesión');
    }
  });
}

if (elements.showRegisterBtn) {
  elements.showRegisterBtn.addEventListener('click', () => {
    window.location.href = '/register.html';
  });
}

document.getElementById('visitor-login-btn')?.addEventListener('click', () => {
  window.location.href = '/visita/';
});

if (elements.googleLoginBtn) {
  elements.googleLoginBtn.addEventListener('click', async () => {
    try {
      await startGoogleAuth('login');
    } catch (error) {
      setMessage(elements.authMessage, error.message || 'No se pudo iniciar sesión con Google.');
    }
  });
}

if (elements.registerForm) {
  elements.registerEmailStartBtn?.addEventListener('click', () => {
    elements.registerChoice.classList.add('hidden');
    elements.registerForm.classList.remove('hidden');
    elements.registerDescription.textContent = 'Completa el formulario para crear tu cuenta.';
    elements.registerPasswordConfirmation.required = true;
    elements.googlePasswordConfirmation.classList.remove('hidden');
    elements.googlePasswordRequirements.textContent = 'De 12 a 72 caracteres, con mayúsculas, minúsculas y números.';
    elements.googlePasswordRequirements.classList.remove('hidden');
    elements.registerUsername.focus();
  });

  let googleRegistrationProfile = null;
  try {
    if (new URLSearchParams(window.location.search).get('google') === 'complete') {
      googleRegistrationProfile = getGoogleRegistrationProfile();
      if (googleRegistrationProfile) {
        elements.registerChoice.classList.add('hidden');
        elements.registerForm.classList.remove('hidden');
        const registrationDraft = getGoogleRegistrationDraft();
        const email = googleRegistrationProfile.email || '';
        const suggestedUsername = email.split('@', 1)[0].replace(/[^a-zA-Z0-9_]/g, '').slice(0, 30);
        elements.registerTitle.textContent = 'Completa tu registro';
        elements.registerDescription.textContent = `Cuenta de Google verificada: ${email}. Completa tus datos y elige una contraseña para iniciar sesión sin Google.`;
        elements.registerFirstName.value = registrationDraft?.first_name || googleRegistrationProfile.first_name || '';
        elements.registerLastName.value = registrationDraft?.last_name || googleRegistrationProfile.last_name || '';
        elements.registerUsername.value = registrationDraft?.name
          || (suggestedUsername.length >= 3 ? suggestedUsername : 'jugador_google');
        elements.registerEmail.value = email;
        elements.registerRole.value = registrationDraft?.role || '';
        if (elements.registerGrade) elements.registerGrade.value = registrationDraft?.grade || '';
        if (elements.registerGroup) elements.registerGroup.value = registrationDraft?.group_name || '';
        elements.registerEmailField.classList.add('hidden');
        elements.registerPasswordField.classList.remove('hidden');
        elements.registerEmail.required = false;
        elements.registerPassword.labels[0].textContent = 'Elige una contraseña:';
        elements.registerPasswordConfirmation.required = true;
        elements.googlePasswordConfirmation.classList.remove('hidden');
        elements.googlePasswordRequirements.classList.remove('hidden');
        elements.registerFormBtn.textContent = 'Completar registro y entrar';
        elements.googleRegisterRetryBtn.textContent = 'Volver a autorizar con Google';
        elements.googleRegisterRetryBtn.classList.remove('hidden');
      }
    }
  } catch (error) {
    setMessage(elements.registerMessage, error.message);
  }

  const updateStudentRegistrationFields = () => {
    const isStudent = elements.registerRole.value === 'student';
    elements.studentRegistrationFields?.classList.toggle('hidden', !isStudent);
    if (elements.registerGrade) elements.registerGrade.required = isStudent;
    if (elements.registerGroup) elements.registerGroup.required = isStudent;
  };

  elements.registerRole?.addEventListener('change', updateStudentRegistrationFields);
  updateStudentRegistrationFields();
  elements.registerPasswordConfirmation?.addEventListener('input', () => {
    elements.registerPasswordConfirmation.setCustomValidity('');
  });

  const validateRegistrationEmail = () => {
    const email = elements.registerEmail;
    if (!email) return true;

    const invalidFormat = email.value.length > 0 && email.validity.typeMismatch;
    const message = invalidFormat
      ? 'Escribe un correo válido, por ejemplo nombre@dominio.com.'
      : '';
    email.setCustomValidity(message);
    if (elements.registerEmailError) {
      elements.registerEmailError.textContent = message;
      elements.registerEmailError.classList.toggle('visible', Boolean(message));
    }
    return !message;
  };

  elements.registerEmail?.addEventListener('input', validateRegistrationEmail);
  elements.registerEmail?.addEventListener('blur', validateRegistrationEmail);
  elements.registerPasswordConfirmation?.addEventListener('input', () => {
    elements.registerPasswordConfirmation.setCustomValidity('');
  });

  elements.registerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    validateRegistrationEmail();
    if (!elements.registerForm.checkValidity()) {
      elements.registerForm.reportValidity();
      return;
    }

    const payload = {
      name: elements.registerUsername.value.trim(),
      first_name: elements.registerFirstName.value.trim(),
      last_name: elements.registerLastName.value.trim(),
      role: elements.registerRole.value,
      grade: elements.registerGrade?.value.trim() || '',
      group_name: elements.registerGroup?.value.trim() || '',
    };

    if (elements.registerPassword.value !== elements.registerPasswordConfirmation.value) {
      elements.registerPasswordConfirmation.setCustomValidity('Las contraseñas no coinciden.');
      elements.registerPasswordConfirmation.reportValidity();
      return;
    }
    elements.registerPasswordConfirmation.setCustomValidity('');

    let response;
    let data;
    if (googleRegistrationProfile) {
      payload.password = elements.registerPassword.value;
      try {
        data = await registerWithGoogle(payload);
        response = { ok: true };
      } catch (error) {
        setMessage(elements.registerMessage, error.message || 'No se pudo completar el registro con Google.');
        return;
      }
    } else {
      payload.email = elements.registerEmail.value.trim().toLowerCase();
      payload.password = elements.registerPassword.value;
      ({ response, data } = await registerUser(payload));
    }
    if (response.ok && data.token) {
      if (data.user?.role !== payload.role) {
        setMessage(elements.registerMessage, 'El rol guardado no coincide con el rol seleccionado. Inicia sesión de nuevo o contacta al administrador.');
        return;
      }
      saveSession(data.token, data.user);
      window.location.href = '/';
    } else {
      setMessage(elements.registerMessage, data.error || 'Error registrando usuario');
    }
  });

  const startGoogleRegistration = async () => {
    try {
      const registrationDraft = googleRegistrationProfile
        ? {
            name: elements.registerUsername.value.trim(),
            first_name: elements.registerFirstName.value.trim(),
            last_name: elements.registerLastName.value.trim(),
            role: elements.registerRole.value,
            grade: elements.registerGrade?.value.trim() || '',
            group_name: elements.registerGroup?.value.trim() || '',
          }
        : null;
      await startGoogleAuth('register', registrationDraft);
    } catch (error) {
      setMessage(elements.registerMessage, error.message || 'No se pudo iniciar el registro con Google.');
    }
  };
  elements.googleRegisterBtn?.addEventListener('click', startGoogleRegistration);
  elements.googleRegisterRetryBtn?.addEventListener('click', startGoogleRegistration);
}

if (elements.backToLoginBtn) {
  elements.backToLoginBtn.addEventListener('click', (event) => {
    event.preventDefault();
    window.location.href = '/';
  });
}

if (elements.playGameBtn) {
  elements.playGameBtn.addEventListener('click', () => {
    showPanel(elements.homePanel, false);
    showPanel(elements.gamePanel, true);
    gameController.loadGameOptions();
  });
}

if (elements.speedChallengeBtn) {
  elements.speedChallengeBtn.addEventListener('click', () => {
    showPanel(elements.homePanel, false);
    showPanel(elements.speedChallengePanel, true);
    challengeController.loadChallenge();
  });
}

if (elements.teacherBtn) {
  elements.teacherBtn.addEventListener('click', () => {
    showPanel(elements.homePanel, false);
    elements.teacherPanel?.querySelector('#teacher-menu')?.classList.remove('hidden');
    elements.teacherPanel?.querySelectorAll('.teacher-module').forEach((module) => module.classList.add('hidden'));
    showPanel(elements.teacherPanel, true);
  });
}

elements.teacherPanel?.addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;

  const moduleButton = event.target.closest('[data-teacher-module]');
  if (moduleButton) {
    const module = document.getElementById(moduleButton.getAttribute('data-teacher-module'));
    if (!module || !elements.teacherPanel.contains(module)) return;
    elements.teacherPanel.querySelector('#teacher-menu')?.classList.add('hidden');
    elements.teacherPanel.querySelectorAll('.teacher-module').forEach((item) => item.classList.add('hidden'));
    module.classList.remove('hidden');
    return;
  }

  if (event.target.closest('[data-back-to-teacher-menu]')) {
    elements.teacherPanel.querySelectorAll('.teacher-module').forEach((module) => module.classList.add('hidden'));
    elements.teacherPanel.querySelector('#teacher-menu')?.classList.remove('hidden');
  }
});

if (elements.settingsBtn) {
  elements.settingsBtn.addEventListener('click', () => {
  showPanel(elements.loginLayout, false);
    showPanel(elements.homePanel, false);
    showPanel(elements.gamePanel, false);
    showPanel(elements.teacherPanel, false);
    showPanel(elements.speedChallengePanel, false);
    showPanel(elements.settingsPanel, true);
  });
}

if (elements.logoutBtn) {
  elements.logoutBtn.addEventListener('click', logout);
}
if (elements.settingsLogoutBtn) {
  elements.settingsLogoutBtn.addEventListener('click', logout);
}

if (elements.deleteAccountForm) {
  elements.deleteAccountForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!elements.deleteAccountForm.checkValidity()) {
      elements.deleteAccountForm.reportValidity();
      return;
    }

    const confirmed = window.confirm('¿Eliminar tu cuenta permanentemente? Esta acción no se puede deshacer.');
    if (!confirmed) return;

    const button = elements.deleteAccountForm.querySelector('button[type="submit"]');
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Eliminando...';
    setMessage(elements.deleteAccountMessage, 'Eliminando cuenta...');
    try {
      const { response, data } = await deleteMyAccount(elements.deleteAccountPassword.value);
      if (!response.ok) {
        return setMessage(elements.deleteAccountMessage, data.error || 'No se pudo eliminar la cuenta.');
      }
      clearStoredSession();
      setState({ token: null, user: null });
      elements.settingsBtn?.classList.add('hidden');
      elements.deleteAccountPassword.value = '';
      showPanel(elements.settingsPanel, false);
      showPanel(elements.homePanel, false);
      showPanel(elements.gamePanel, false);
      showPanel(elements.teacherPanel, false);
      showPanel(elements.speedChallengePanel, false);
      showPanel(elements.loginLayout, true);
      setMessage(elements.authMessage, data.message || 'Cuenta eliminada permanentemente.');
      await loadLeaderboard();
    } catch {
      setMessage(elements.deleteAccountMessage, 'No se pudo conectar con el servidor.');
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  });
}

const backToHomeAction = () => {
  showPanel(elements.homePanel, true);
  showPanel(elements.settingsPanel, false);
  showPanel(elements.gamePanel, false);
  showPanel(elements.teacherPanel, false);
  showPanel(elements.speedChallengePanel, false);
  loadLeaderboard();
};

if (elements.backToHomeBtn) elements.backToHomeBtn.addEventListener('click', backToHomeAction);
if (elements.backToHomeFromSettingsBtn) elements.backToHomeFromSettingsBtn.addEventListener('click', backToHomeAction);
if (elements.backToHomeFromTeacherBtn) elements.backToHomeFromTeacherBtn.addEventListener('click', backToHomeAction);
if (elements.backToHomeFromChallengeBtn) elements.backToHomeFromChallengeBtn.addEventListener('click', backToHomeAction);
if (elements.challengeBackBtn) elements.challengeBackBtn.addEventListener('click', backToHomeAction);

if (elements.loginForm && window.location.pathname === '/') {
  const existingSession = loadSession();
  if (existingSession) {
    setUserSession(existingSession);
  } else {
    loadLeaderboard();
  }
}
