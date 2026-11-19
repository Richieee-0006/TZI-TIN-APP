// ── bloky ──
let CHUNK_SIZE = parseInt(localStorage.getItem('tzi_chunk_size'), 10) || 10;
function syncChunkSizeUI() {
  $('menu-chunk-size').textContent = CHUNK_SIZE;
  $('chunks-size-label').textContent = CHUNK_SIZE;
  $('chunk-size-input').value = CHUNK_SIZE;
}
function applyChunkSize() {
  const n = parseInt($('chunk-size-input').value, 10);
  if (!n || n < 1) return;
  CHUNK_SIZE = n; localStorage.setItem('tzi_chunk_size', String(n));
  syncChunkSizeUI(); renderChunks(); updateMenuStats(false);
}
function showChunks() { fromChunks = false; syncChunkSizeUI(); renderChunks(); show('chunks'); }
function getChunks() { const out = []; for (let i = 0; i < ALL.length; i += CHUNK_SIZE) out.push(ALL.slice(i, i + CHUNK_SIZE)); return out; }
function renderChunks() {
  const list = $('chunk-list');
  const bitNode = q => progress[q.id] === 'correct'
    ? TziDom.el('span', { class: 'bit ok' }, '1')
    : progress[q.id] === 'wrong'
      ? TziDom.el('span', { class: 'bit bad' }, '0')
      : TziDom.el('span', { class: 'bit new' }, '·');
  TziDom.setChildren(list, ...getChunks().map((qs, i) => {
    const done = qs.filter(q => progress[q.id] === 'correct').length;
    const wrong = qs.filter(q => progress[q.id] === 'wrong').length;
    return TziDom.el('button', { class: 'chunk-btn', on: { click: () => showChunkDetail(qs, i) } },
      TziDom.el('span', { class: 'chunk-name' }, `Blok ${i + 1}`, TziDom.el('small', null, `otázky ${i * CHUNK_SIZE + 1} až ${i * CHUNK_SIZE + qs.length}`)),
      TziDom.el('span', { class: 'chunk-bits', 'aria-hidden': 'true' }, ...qs.map(bitNode)),
      TziDom.el('span', { class: 'chunk-stats' },
        TziDom.el('span', { class: 'ok', title: 'Správně' }, String(done)),
        TziDom.el('span', { class: 'bad', title: 'Chybně' }, String(wrong)),
        TziDom.el('span', { class: 'new', title: 'Nové' }, String(qs.length - done - wrong))
      )
    );
  }));
}
let currentChunk = [];
function showChunkDetail(qs, i) {
  currentChunk = qs;
  $('chunk-detail-title').textContent = `Blok ${i + 1}, otázky ${i * CHUNK_SIZE + 1} až ${i * CHUNK_SIZE + qs.length}`;
  const pills = (el, list) => {
    const nodes = list.length
      ? list.map(q => TziDom.el('button', {
          class: `q-pill${isInput(q) ? ' calc' : ''}`,
          title: isInput(q) ? 'Příklad na výpočet' : null,
          on: { click: () => startChunkQuestion(q.id) }
        }, String(q.number)))
      : [TziDom.el('span', { class: 'cd-empty' }, 'Žádné otázky')];
    TziDom.setChildren($(el), ...nodes);
  };
  pills('cd-good', qs.filter(q => progress[q.id] === 'correct'));
  pills('cd-bad', qs.filter(q => progress[q.id] === 'wrong'));
  pills('cd-new', qs.filter(q => !progress[q.id]));
  show('chunk-detail');
}
function startChunkQuestion(id) { const q = currentChunk.find(q => q.id === id); if (q) { fromChunks = true; beginSession([q], false); } }
function startChunkSubset(status) {
  let qs;
  if (status === 'all') qs = currentChunk;
  else if (status === undefined) qs = currentChunk.filter(q => !progress[q.id]);
  else qs = currentChunk.filter(q => progress[q.id] === status);
  if (!qs.length) return;
  fromChunks = true; beginSession([...qs], false);
}
function startChunkStudy() {
  const pool = currentChunk.filter(q => !progress[q.id] || progress[q.id] === 'wrong');
  if (!pool.length) return;
  fromChunks = true; showRandomModal('chunk-study', pool);
}

