async function startCompetitiveMode(mode = 'koth', duelId = null) {
  if (currentUserData && currentUserData.role === 'trial') {
    showToast('⚠️ Pro kompetitivní režimy je nutné se přihlásit.');
    return;
  }
  let qs = [];
  let matchedDuel = null;
  const endpoint = mode === 'ffa' ? '/api/ffa/start' : mode === 'duel' ? '/api/duel/start' : '/api/koth/start';
  try {
    const payload = { count: 10, source: currentSource };
    if (mode === 'duel' && duelId !== null) payload.duel_id = duelId;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.questions) && data.questions.length) qs = data.questions;
      if (data.duel) matchedDuel = data.duel;
    }
  } catch (e) {}
  if (!qs.length) {
    qs = shuffle(ALL.filter(q => !q.reveal)).slice(0, 10);
  }
  if (!qs.length) return;
  queue = qs; idx = 0; history = []; optOrder = {};
  suddenDeath = false; studyMode = false; examMode = false;
  kothMode = true; compMode = mode; activeDuelId = matchedDuel ? matchedDuel.id : duelId;
  kothStartTime = Date.now(); kothLastResult = null;
  if (mode === 'ffa') {
    $('sudden-banner').innerHTML = '🏟️ Free For All Aréna<span>Získej co nejvyšší skóre v žebříčku všech hráčů (10 otázek na čas)!</span>';
  } else if (mode === 'duel') {
    const opp = matchedDuel && matchedDuel.creator_username ? `Soupeř: ${esc(matchedDuel.creator_username)} (${matchedDuel.creator_score} b.)` : 'Zakládáš novou 1v1 výzvu pro soupeře';
    $('sudden-banner').innerHTML = `⚔️ 1v1 Duel<span>${opp}</span>`;
  } else {
    $('sudden-banner').innerHTML = '👑 King of the Hill<span>Překonej skóre krále kopce v 10 otázkách na čas!</span>';
  }
  $('sudden-banner').style.display = 'block';
  show('quiz');
  renderQ();
}

async function startKothChallenge() {
  return startCompetitiveMode('koth');
}

async function submitKothResults() {
  const elapsed = Math.max(0, Date.now() - (kothStartTime || Date.now()));
  const mode = compMode || 'koth';
  const endpoint = activeRoomId
    ? `/api/rooms/${activeRoomId}/submit`
    : (mode === 'ffa' ? '/api/ffa/submit' : mode === 'duel' ? '/api/duel/submit' : '/api/koth/submit');
  try {
    const payload = {
      answers: history.map(h => ({ id: h.id, userKeys: h.userKeys, isCorrect: h.isCorrect })),
      time_ms: elapsed,
      total_questions: queue.length
    };
    if (mode === 'duel' && activeDuelId !== null) payload.duel_id = activeDuelId;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      kothLastResult = await res.json();
      if (kothLastResult.room) {
        renderRoomStandingsBoard(kothLastResult.room);
      } else if ($('room-results-board')) {
        $('room-results-board').style.display = 'none';
      }
      refreshKothStatus();
      refreshUserStats();
    }
  } catch (e) {}
}

