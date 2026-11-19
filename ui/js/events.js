/* CSP-kompatibilní registrace UI událostí (bez inline on*= atributů v novy.html). */
(function () {
  const CLICK_ACTIONS = {
    toggleOfflineMode: () => toggleOfflineMode(),
    openLeaderboardView: () => openLeaderboardView(),
    openProfileView: () => openProfileView(),
    setType: arg => setType(arg),
    goPrimary: () => goPrimary(),
    showChunks: () => showChunks(),
    startAll: () => startAll(),
    showRandomModal: arg => showRandomModal(arg),
    startUnseen: () => startUnseen(),
    startWrongs: () => startWrongs(),
    startCorrect: () => startCorrect(),
    startExam: () => startExam(),
    startSuddenDeath: () => startSuddenDeath(),
    openCompArena: () => openCompArena(),
    showMenu: () => showMenu(),
    startChunkSubset: arg => startChunkSubset(arg),
    startChunkStudy: () => startChunkStudy(),
    closeModal: () => closeModal(),
    selectArenaRoomMode: arg => selectArenaRoomMode(arg),
    startCompetitiveMode: arg => startCompetitiveMode(arg),
    startKothChallenge: () => startKothChallenge(),
    createRoomFromUI: () => createRoomFromUI(),
    toggleSound: () => toggleSound(),
    clearSourceProgress: () => clearSourceProgress(),
    openRevalidateModal: arg => openRevalidateModal(arg),
    openDeleteProfileModal: () => openDeleteProfileModal(),
    closeRevalidateModal: () => closeRevalidateModal(),
    closeDeleteProfileModal: () => closeDeleteProfileModal(),
    startActiveRoomByHost: () => startActiveRoomByHost(),
    leaveActiveRoom: () => leaveActiveRoom(),
    prevQ: () => prevQ(),
    finishEarly: () => finishEarly(),
    handleAction: () => handleAction(),
    restartSame: () => restartSame(),
    practiceWrong: () => practiceWrong(),
    backFromResults: () => backFromResults()
  };

  const SUBMIT_ACTIONS = {
    applyChunkSize: () => applyChunkSize(),
    startRandom: () => startRandom(),
    submitUsernameChange: () => submitUsernameChange(),
    submitPasswordChange: () => submitPasswordChange(),
    confirmRevalidatedDelete: () => confirmRevalidatedDelete(),
    submitDeleteProfileStep: () => submitDeleteProfileStep()
  };

  document.addEventListener('click', e => {
    const el = e.target && e.target.closest ? e.target.closest('[data-click]') : null;
    if (!el) return;
    if (el.dataset.stop) e.stopPropagation();
    const fn = CLICK_ACTIONS[el.dataset.click];
    if (fn) fn(el.dataset.arg);
  });

  document.addEventListener('submit', e => {
    const el = e.target && e.target.closest ? e.target.closest('[data-submit]') : null;
    if (!el) return;
    e.preventDefault();
    const fn = SUBMIT_ACTIONS[el.dataset.submit];
    if (fn) fn();
  });

  document.addEventListener('change', e => {
    const el = e.target && e.target.closest ? e.target.closest('[data-change]') : null;
    if (!el) return;
    if (el.dataset.change === 'applyUserTheme') applyUserTheme(el.value);
  });

  document.addEventListener('input', e => {
    const el = e.target && e.target.closest ? e.target.closest('[data-input]') : null;
    if (!el) return;
    if (el.dataset.input === 'onInput') onInput();
  });
})();
