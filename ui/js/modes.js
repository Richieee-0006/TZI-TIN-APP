// ── režimy ──
function startAll() { beginSession([...ALL], false); }
function startUnseen() { beginSession(ALL.filter(q => !progress[q.id]), false); }
function startWrongs() { beginSession(ALL.filter(q => progress[q.id] === 'wrong'), false); }
function startCorrect() { beginSession(ALL.filter(q => progress[q.id] === 'correct'), false); }

function resumeSession() {
  if (!session) return;
  const idMap = Object.fromEntries(FULL.map(q => [q.id, q]));
  queue = session.queue_ids.map(id => idMap[id]).filter(Boolean);
  idx = session.idx; history = session.history || []; suddenDeath = session.sudden_death || false;
  studyMode = false; examMode = false; fromChunks = false;
  $('sudden-banner').style.display = suddenDeath ? 'block' : 'none';
  show('quiz'); renderQ();
}

let modalPool = null;
function showRandomModal(mode, pool) {
  modalMode = mode || 'random';
  if (modalMode === 'study' && !pool) pool = ALL.filter(q => !progress[q.id] || progress[q.id] === 'wrong');
  modalPool = pool || null;
  $('random-modal').querySelector('h2').textContent = (modalMode === 'study' || modalMode === 'chunk-study') ? 'Kolik otázek nastudovat?' : 'Kolik otázek?';
  const maxN = modalPool ? modalPool.length : ALL.length;
  const input = $('rand-count'); input.max = maxN; input.value = Math.min(10, maxN);
  $('random-modal').classList.add('show');
  setTimeout(() => input.focus(), 50);
}
function closeModal() { $('random-modal').classList.remove('show'); }
function startRandom() {
  const maxN = modalPool ? modalPool.length : ALL.length;
  const n = Math.min(Math.max(1, parseInt($('rand-count').value) || 1), maxN);
  closeModal();
  if (modalMode === 'study' || modalMode === 'chunk-study') startStudy(shuffle(modalPool || ALL).slice(0, n));
  else beginSession(shuffle(modalPool || ALL).slice(0, n), false);
}
function startStudy(qs) {
  if (!qs.length) return;
  studyPicks = [...qs]; studyMode = true; examMode = false;
  queue = [...qs]; idx = 0; history = []; optOrder = {}; suddenDeath = false;
  $('sudden-banner').style.display = 'none';
  show('quiz'); renderQ();
}
function startSuddenDeath() { beginSession(shuffle(ALL.filter(q => !q.reveal)), true); }

function startExam() {
  const eligible = ALL.filter(q => !q.reveal);
  const n = Math.min(15, eligible.length);
  if (!n) return;
  examMode = true; studyMode = false;
  queue = shuffle(eligible).slice(0, n); idx = 0; history = []; optOrder = {}; suddenDeath = false;
  $('sudden-banner').style.display = 'none';
  show('quiz');
  startExamTimer(Math.max(5, n * 2) * 60);
  renderQ();
}
function startExamTimer(sec) { clearExamTimer(); examEndTime = Date.now() + sec * 1000; updateExamTimer(); examTimer = setInterval(updateExamTimer, 1000); }
function clearExamTimer() { if (examTimer) clearInterval(examTimer); examTimer = null; }
function updateExamTimer() {
  const remain = Math.max(0, Math.round((examEndTime - Date.now()) / 1000));
  $('score-label').textContent = `Zbývá ${String(Math.floor(remain / 60)).padStart(2, '0')}:${String(remain % 60).padStart(2, '0')}`;
  if (remain <= 0) { clearExamTimer(); saveProgress(); showResults(); }
}

function beginSession(qs, sd) {
  if (!qs.length) return;
  queue = qs; idx = 0; history = []; optOrder = {}; suddenDeath = sd; studyMode = false; examMode = false; kothMode = false;
  $('sudden-banner').innerHTML = 'Sudden Death<span>1 život, první chyba ukončí hru</span>';
  $('sudden-banner').style.display = sd ? 'block' : 'none';
  show('quiz'); renderQ();
}

