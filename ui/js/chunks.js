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
  const list = $('chunk-list'); list.innerHTML = '';
  getChunks().forEach((qs, i) => {
    const done = qs.filter(q => progress[q.id] === 'correct').length;
    const wrong = qs.filter(q => progress[q.id] === 'wrong').length;
    const btn = document.createElement('button');
    btn.className = 'chunk-btn';
    const bit = q => progress[q.id] === 'correct' ? '<span class="bit ok">1</span>' : progress[q.id] === 'wrong' ? '<span class="bit bad">0</span>' : '<span class="bit new">·</span>';
    btn.innerHTML = `<span class="chunk-name">Blok ${i + 1}<small>otázky ${i * CHUNK_SIZE + 1} až ${i * CHUNK_SIZE + qs.length}</small></span>` +
      `<span class="chunk-bits" aria-hidden="true">${qs.map(bit).join('')}</span>` +
      `<span class="chunk-stats"><span class="ok" title="Správně">${done}</span><span class="bad" title="Chybně">${wrong}</span><span class="new" title="Nové">${qs.length - done - wrong}</span></span>`;
    btn.onclick = () => showChunkDetail(qs, i);
    list.appendChild(btn);
  });
}
let currentChunk = [];
function showChunkDetail(qs, i) {
  currentChunk = qs;
  $('chunk-detail-title').textContent = `Blok ${i + 1}, otázky ${i * CHUNK_SIZE + 1} až ${i * CHUNK_SIZE + qs.length}`;
  const pills = (el, list) => $(el).innerHTML = list.map(q => `<button class="q-pill${isInput(q) ? ' calc' : ''}" ${isInput(q) ? 'title="Příklad na výpočet" ' : ''}onclick="startChunkQuestion('${q.id}')">${q.number}</button>`).join('') || '<span class="cd-empty">Žádné otázky</span>';
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

