const { el: gEl, setChildren: gSet, iconSvg: gIco } = TziDom;

function gInlineSeg(str) {
  const frag = document.createDocumentFragment();
  let pos = 0;
  const re = /(?:^|(?<=[\s(>„"']))\*(?!\*)((?:[^*\n]|\*\*[^*\n]+?\*\*)+?)(?<!\*)\*(?=$|[\s.,:;!?)"“'<])|\*\*(.+?)\*\*/g;
  for (const m of str.matchAll(re)) {
    if (m.index > pos) frag.appendChild(fmtToFragment(str.slice(pos, m.index)));
    if (m[1] !== undefined) frag.appendChild(gEl('i', null, gInlineSeg(m[1])));
    else frag.appendChild(gEl('b', null, gInlineSeg(m[2])));
    pos = m.index + m[0].length;
  }
  if (pos < str.length) frag.appendChild(fmtToFragment(str.slice(pos)));
  return frag;
}

function gInline(raw) {
  const frag = document.createDocumentFragment();
  for (const part of String(raw ?? '').split(/(`[^`\n]+`)/g)) {
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      frag.appendChild(gEl('code', null, part.slice(1, -1)));
    } else {
      frag.appendChild(gInlineSeg(part));
    }
  }
  return frag;
}

const mkWarnIco = () => gIco([['circle', { cx: 12, cy: 12, r: 9 }], ['line', { x1: 12, y1: 8, x2: 12, y2: 12 }], ['line', { x1: 12, y1: 16, x2: 12.01, y2: 16 }]]);
const mkXIco = () => gIco([['circle', { cx: 12, cy: 12, r: 9 }], ['line', { x1: 15, y1: 9, x2: 9, y2: 15 }], ['line', { x1: 9, y1: 9, x2: 15, y2: 15 }]]);
const mkCheckIco = () => gIco([['circle', { cx: 12, cy: 12, r: 9 }], ['polyline', { points: '8.5 12.5 11 15 15.5 9.5' }]]);
const mkChevIco = () => gIco([['polyline', { points: '9 18 15 12 9 6' }]], 'chev ico');

let _gTblSeq = 0;

function gTable(lines, label) {
  let aligns = [];
  const rows = [];
  for (const l of lines) {
    if (/^\|[\s|:-]+\|?\s*$/.test(l)) {
      aligns = l.replace(/^\||\|$/g, '').split('|').map(c => {
        const s = c.trim();
        if (s.startsWith(':') && s.endsWith(':')) return 'col-c';
        if (s.endsWith(':')) return 'col-r';
        return '';
      });
      continue;
    }
    rows.push(l.replace(/^\||\|$/g, '').split('|'));
  }
  if (!rows.length) return null;
  const headRow = gEl('tr', null, rows[0].map((c, idx) => {
    const raw = c.trim();
    const cls = aligns[idx] || null;
    if (!raw) return gEl('th', { scope: 'col', class: cls }, gEl('span', { class: 'sr-only' }, 'Sloupec'));
    const h = gInline(raw);
    if (h.querySelector('math')) {
      return gEl('th', { scope: 'col', class: cls },
        gEl('span', { class: 'sr-only' }, raw),
        gEl('span', { 'aria-hidden': 'true' }, h)
      );
    }
    return gEl('th', { scope: 'col', class: cls }, h);
  }));
  const bodyRows = rows.slice(1).map(r =>
    gEl('tr', null, r.map((c, idx) => gEl('td', { class: aligns[idx] || null }, gInline(c.trim()))))
  );
  const regionLabel = `${label || 'Tabulka'} #${++_gTblSeq}`;
  return gEl('div', { class: 'table-wrap', tabindex: '0', role: 'region', 'aria-label': regionLabel },
    gEl('table', { class: 'g-table' },
      gEl('thead', null, headRow),
      bodyRows.length ? gEl('tbody', null, bodyRows) : null
    )
  );
}

function gMistakeItem(raw) {
  const txt = String(raw || '').trim();
  const checkPos = txt.indexOf('✅');
  if (!txt.includes('❌') && checkPos === -1) return gEl('li', null, gInline(txt));
  const before = (checkPos !== -1 ? txt.slice(0, checkPos) : txt).replace(/^❌\s*/, '').trim();
  const after = checkPos !== -1 ? txt.slice(checkPos + 1).trim() : '';
  const qm = before.match(/^(„[^“]+“)\s*(.+)$/);
  const claim = qm ? qm[1] : before;
  const why = qm ? qm[2] : '';
  return gEl('li', { class: 'mistake-item' },
    claim ? gEl('div', { class: 'm-row m-wrong' }, mkXIco(), gEl('span', { class: 'm-claim' }, gInline(claim))) : null,
    why ? gEl('div', { class: 'm-why' }, gInline(why)) : null,
    after ? gEl('div', { class: 'm-row m-right' }, mkCheckIco(), gEl('span', null, gInline(after))) : null
  );
}

function gSourceFooter(rawLines) {
  if (!rawLines.length) return null;
  const items = rawLines.map(rawLine => {
    const s = rawLine.trim();
    return (/^\*[^*\n].*\*$/.test(s) ? s.slice(1, -1) : s).trim();
  });
  const combinedPlain = items.join(' ').replace(/\*\*/g, '');
  const hasClaude = /Doplněno z Claude/i.test(combinedPlain);
  if (items.length === 1 && combinedPlain.length <= 85 && !combinedPlain.includes(';') && !hasClaude) {
    return gEl('p', { class: 'src-inline' }, gInline(items[0]));
  }
  const firstPlain = items[0].replace(/\*\*/g, '');
  const shortMatch = firstPlain.match(/^([^;(]+)/);
  let shortLabel = (shortMatch ? shortMatch[1] : firstPlain).trim()
    .replace(/\s*\*\*Doplněno z Claude\*\*/gi, '')
    .replace(/\s*Doplněno z Claude/gi, '')
    .replace(/[.:,\s]+$/, '');
  if (!shortLabel || shortLabel.toLowerCase() === 'zdroj:') shortLabel = 'Zdroj: přednáška';
  if (shortLabel.length > 56) shortLabel = shortLabel.slice(0, 54).trim() + '…';
  return gEl('details', { class: 'entry-src' },
    gEl('summary', null, mkChevIco(), gEl('span', null, shortLabel), hasClaude ? gEl('span', { class: 'src-badge' }, 'doplněno AI') : null),
    gEl('div', { class: 'src-full' }, items.map(it => gEl('p', null, gInline(it))))
  );
}

// Formátuje heslo v teorii: callouty (> [!warning]), tabulky, číslované/odrážkové seznamy, časté omyly, příklady a zdroje.
function gBody(body, termLabel) {
  const out = [];
  const srcLines = [];
  const L = String(body ?? '').split('\n');
  for (let i = 0; i < L.length; i++) {
    const l = L[i];
    if (/^>/.test(l)) {
      const qLines = [];
      for (; i < L.length && /^>/.test(L[i]); i++) qLines.push(L[i].replace(/^>\s?/, ''));
      i--;
      let title = '';
      if (qLines.length && /^\[![a-z]+\]/i.test(qLines[0])) {
        const tm = qLines[0].match(/^\[![a-z]+\]\s*(.*)$/i);
        title = tm && tm[1] ? tm[1].trim() : 'Poznámka';
        qLines.shift();
      }
      out.push(gEl('aside', { class: 'callout' },
        title ? gEl('div', { class: 'callout-head' }, mkWarnIco(), gEl('span', null, title)) : null,
        gBody(qLines.join('\n'), termLabel)
      ));
    } else if (/^\|/.test(l)) {
      const tLines = [];
      for (; i < L.length && /^\|/.test(L[i]); i++) tLines.push(L[i]);
      i--;
      out.push(gTable(tLines, termLabel ? `Tabulka: ${termLabel}` : 'Tabulka'));
    } else if (/^\*Časté omyly:\*\s*$/i.test(l.trim()) && i + 1 < L.length && /^- /.test(L[i + 1])) {
      const items = [];
      i++;
      for (; i < L.length && /^- /.test(L[i]); i++) items.push(L[i].slice(2));
      i--;
      out.push(gEl('div', { class: 'mistakes' },
        gEl('div', { class: 'mistakes-head' }, 'Časté omyly'),
        gEl('ul', { class: 'mistake-list' }, items.map(gMistakeItem))
      ));
    } else if (/^- /.test(l)) {
      const items = [];
      for (; i < L.length && /^- /.test(L[i]); i++) items.push(L[i].slice(2));
      i--;
      const isMistake = items.some(x => x.includes('❌') && x.includes('✅'));
      out.push(isMistake
        ? gEl('ul', { class: 'mistake-list' }, items.map(gMistakeItem))
        : gEl('ul', { class: 'g-ul' }, items.map(x => gEl('li', null, gInline(x)))));
    } else if (/^\d+\.\s+/.test(l)) {
      const items = [];
      for (; i < L.length && /^\d+\.\s+/.test(L[i]); i++) items.push(L[i].replace(/^\d+\.\s+/, ''));
      i--;
      out.push(gEl('ol', { class: 'g-ol' }, items.map(x => gEl('li', null, gInline(x)))));
    } else if (/^\*Zdroj\s*:/i.test(l.trim())) {
      srcLines.push(l);
    } else if (l.trim()) {
      const exMatch = l.match(/^\*(Příklad[^*:]*|Příklady[^*:]*|Další příklad[^*:]*|Dveře[^*:]*):\*\s*(.+)$/);
      const noteMatch = l.match(/^\*(Pozor[^*:]*):\*\s*(.+)$/);
      if (exMatch) out.push(gEl('p', { class: 'block-ex' }, gEl('span', { class: 'b-tag' }, gInline(exMatch[1] + ':')), gInline(exMatch[2])));
      else if (noteMatch) out.push(gEl('p', { class: 'block-note' }, gEl('span', { class: 'b-tag' }, gInline(noteMatch[1] + ':')), gInline(noteMatch[2])));
      else out.push(gEl('p', null, gInline(l)));
    }
  }
  const frag = document.createDocumentFragment();
  if (out.length) frag.appendChild(gEl('div', { class: 'entry-body' }, out));
  const foot = gSourceFooter(srcLines);
  if (foot) frag.appendChild(foot);
  return frag;
}

function parseLectureMeta(label) {
  const m = String(label || '').match(/^(\d+)\.\s*přednáška\s*\(([^)]+)\):\s*(.+)$/);
  if (!m) return { key: String(label || ''), num: '', date: '', heading: String(label || ''), topic: '' };
  return {
    key: `${m[1]}|${m[2].trim()}`,
    num: m[1],
    date: m[2].trim(),
    heading: `${m[1]}. přednáška · ${m[2].trim()}`,
    topic: m[3].trim()
  };
}

function mergeGroupsByDate(groups) {
  const map = new Map();
  const order = [];
  for (const g of groups || []) {
    const meta = parseLectureMeta(g && g.label);
    let bucket = map.get(meta.key);
    if (!bucket) {
      bucket = {
        key: meta.key,
        num: meta.num,
        date: meta.date,
        heading: meta.heading,
        topics: meta.topic ? [meta.topic] : [],
        entries: []
      };
      map.set(meta.key, bucket);
      order.push(bucket);
    } else if (meta.topic && !bucket.topics.includes(meta.topic)) {
      bucket.topics.push(meta.topic);
    }
    const seen = new Set(bucket.entries.map(e => e && e.term));
    for (const e of (g && g.entries) || []) {
      if (e && !seen.has(e.term)) {
        bucket.entries.push(e);
        seen.add(e.term);
      }
    }
  }
  return order.map(b => ({
    key: b.key,
    num: b.num,
    date: b.date,
    heading: b.heading,
    topicsText: b.topics.join(' · '),
    label: b.topics.length ? `${b.heading}: ${b.topics.join(' · ')}` : b.heading,
    entries: b.entries
  }));
}

(async () => {
  const THEME_ORDER = ['catppuccin', 'dark', 'amoled', 'light'];
  const THEME_NAMES = { catppuccin: 'Mocha', dark: 'Dark', amoled: 'AMOLED', light: 'Světlý', auto: 'Auto' };
  const themeBtn = document.getElementById('themeBtn');
  const applyTheme = t => {
    const mode = THEME_NAMES[t] ? t : 'catppuccin';
    if (mode === 'catppuccin') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', mode);
    if (themeBtn) themeBtn.textContent = 'Motiv: ' + THEME_NAMES[mode];
    try { localStorage.setItem('tzi_theme', mode); } catch (_) {}
  };
  let initTheme = 'catppuccin';
  try {
    const saved = localStorage.getItem('tzi_theme');
    if (THEME_NAMES[saved]) initTheme = saved;
  } catch (_) {}
  applyTheme(initTheme);
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'catppuccin';
      const idx = THEME_ORDER.indexOf(cur);
      const next = THEME_ORDER[(idx + 1) % THEME_ORDER.length];
      applyTheme(next);
    });
  }

  const outEl = document.getElementById('out');
  const subEl = document.getElementById('sub');
  const countMeta = document.getElementById('countMeta');
  const lecSelect = document.getElementById('lecSelect');
  const tocAside = document.getElementById('tocAside');
  const tocLabel = document.getElementById('tocLabel');
  const tocNav = document.getElementById('tocNav');
  const qInput = document.getElementById('q');
  const qClear = document.getElementById('qClear');
  const resetFilterBtn = document.getElementById('resetFilterBtn');
  const emptyResetBtn = document.getElementById('emptyResetBtn');
  const emptySearch = document.getElementById('emptySearch');
  const emptyMsg = document.getElementById('emptyMsg');
  const toTopBtn = document.getElementById('toTop');

  const menuBtn = document.getElementById('menuBtn');
  const drawer = document.getElementById('overviewDrawer');
  const drawerSheet = document.getElementById('drawerSheet');
  const drawerClose = document.getElementById('drawerClose');
  const ovStats = document.getElementById('ovStats');
  const ovLectures = document.getElementById('ovLectures');
  const drawerSrcToggle = document.getElementById('drawerSrcToggle');

  const tocTermFrag = t => {
    const frag = document.createDocumentFragment();
    const s = String(t ?? '');
    const re = /\^\(([^)]+)\)|\^([A-Za-z0-9]+)|_\(([^)]+)\)|_([A-Za-z0-9]+)/g;
    let pos = 0;
    for (const m of s.matchAll(re)) {
      if (m.index > pos) frag.appendChild(document.createTextNode(s.slice(pos, m.index)));
      if (m[1] !== undefined || m[2] !== undefined) frag.appendChild(gEl('sup', null, m[1] ?? m[2]));
      else frag.appendChild(gEl('sub', null, m[3] ?? m[4]));
      pos = m.index + m[0].length;
    }
    if (pos < s.length) frag.appendChild(document.createTextNode(s.slice(pos)));
    return frag;
  };

  const norm = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const bodyWithoutSources = b => String(b || '').split('\n').filter(l => !/^\*Zdroj\s*:/i.test(l.trim())).join('\n');

  let state = {
    source: '_all',
    activeDateKey: '',
    rawTitle: '',
    allMerged: [],
    groups: [],
    entryIndex: [],
    groupEls: [],
    tocEls: [],
    showSources: false
  };

  function openDrawer() {
    if (!drawer || drawer.open) return;
    drawer.showModal();
    if (menuBtn) menuBtn.setAttribute('aria-expanded', 'true');
  }
  function closeDrawer() {
    if (drawer && drawer.open) drawer.close();
  }
  if (menuBtn) menuBtn.addEventListener('click', openDrawer);
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  if (drawer) {
    drawer.addEventListener('click', e => {
      if (drawerSheet && !drawerSheet.contains(e.target)) closeDrawer();
    });
    drawer.addEventListener('cancel', () => {
      if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
    });
    drawer.addEventListener('close', () => {
      if (menuBtn) menuBtn.setAttribute('aria-expanded', 'false');
    });
  }

  if (drawerSrcToggle) {
    drawerSrcToggle.addEventListener('click', () => {
      state.showSources = !state.showSources;
      outEl.classList.toggle('show-sources', state.showSources);
      drawerSrcToggle.setAttribute('aria-pressed', state.showSources ? 'true' : 'false');
      drawerSrcToggle.textContent = state.showSources ? 'Skrýt zdroje u pojmů' : 'Zobrazit zdroje u pojmů';
    });
  }

  const showEmpty = msg => {
    outEl.textContent = '';
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = msg;
    outEl.appendChild(p);
    if (tocAside) tocAside.hidden = true;
    if (emptySearch) emptySearch.hidden = true;
  };

  function updateOverview() {
    const overviewGroups = state.allMerged.length ? state.allMerged : state.groups;
    const totalEntries = overviewGroups.reduce((sum, g) => sum + g.entries.length, 0);
    const totalTables = overviewGroups.reduce((s, g) => s + g.entries.reduce((a, e) => a + (String(e.body || '').match(/^[>\s]*\|[\s|:-]+\|\s*$/gm) || []).length, 0), 0);
    const totalMistakes = overviewGroups.reduce((s, g) => s + g.entries.reduce((a, e) => a + (String(e.body || '').match(/^- ❌/gm) || []).length, 0), 0);
    if (ovStats) {
      gSet(ovStats, [
        gEl('div', { class: 'ov-stat' }, gEl('span', { class: 'ov-stat-val' }, overviewGroups.length), gEl('span', { class: 'ov-stat-lbl' }, 'Přednášek')),
        gEl('div', { class: 'ov-stat' }, gEl('span', { class: 'ov-stat-val' }, totalEntries), gEl('span', { class: 'ov-stat-lbl' }, 'Pojmů')),
        gEl('div', { class: 'ov-stat' }, gEl('span', { class: 'ov-stat-val' }, `${totalTables}/${totalMistakes}`), gEl('span', { class: 'ov-stat-lbl' }, 'Tabulek/Omylů'))
      ]);
    }
    if (ovLectures) {
      const isAll = state.source === '_all' && !state.activeDateKey;
      const items = [
        gEl('button', { type: 'button', class: `ov-lec-btn${isAll ? ' active' : ''}`, dataset: { pick: '_all' } },
          gEl('span', { class: 'ov-lec-title' }, 'Všechny přednášky podle data'),
          gEl('span', { class: 'ov-lec-cnt' }, totalEntries)
        )
      ];
      for (const g of overviewGroups) {
        const active = (state.source === '_all' && state.activeDateKey === g.key) || (state.groups.length === 1 && state.groups[0].key === g.key && !isAll);
        items.push(
          gEl('button', { type: 'button', class: `ov-lec-btn${active ? ' active' : ''}`, dataset: { pick: 'date:' + g.key } },
            gEl('span', { class: 'ov-lec-title' }, g.heading),
            gEl('span', { class: 'ov-lec-cnt' }, g.entries.length),
            g.topicsText ? gEl('span', { class: 'ov-lec-topics' }, g.topicsText) : null
          )
        );
      }
      gSet(ovLectures, items);
    }
  }

  function applyFilter() {
    const raw = (qInput && qInput.value || '').trim();
    const q = norm(raw);
    if (qClear) qClear.hidden = !raw;
    if (resetFilterBtn) resetFilterBtn.hidden = !raw;

    let visibleTotal = 0;
    const total = state.entryIndex.length;
    const grpVisible = new Array(state.groupEls.length).fill(0);

    for (const item of state.entryIndex) {
      const show = !q || item.searchText.includes(q);
      item.el.hidden = !show;
      if (show) {
        visibleTotal++;
        grpVisible[item.grpIdx]++;
      }
      if (item.tocEl) item.tocEl.hidden = !show;
    }

    state.groupEls.forEach((gEl, gi) => {
      const cnt = grpVisible[gi];
      gEl.hidden = cnt === 0;
      const cSpan = gEl.querySelector('.grp-count');
      const fullCnt = (state.groups[gi] && state.groups[gi].entries.length) || 0;
      if (cSpan) cSpan.textContent = q ? `${cnt} / ${fullCnt}` : `${fullCnt} pojmů`;
      if (state.groups.length > 1 && state.tocEls[gi]) {
        state.tocEls[gi].hidden = cnt === 0;
        const tCnt = state.tocEls[gi].querySelector('.toc-cnt');
        if (tCnt) tCnt.textContent = q ? `${cnt}/${fullCnt}` : String(fullCnt);
      }
    });

    if (emptySearch) {
      emptySearch.hidden = visibleTotal > 0 || total === 0;
      if (emptyMsg && raw) emptyMsg.textContent = `Dotazu „${raw}“ neodpovídá žádný pojem.`;
    }
    if (subEl) {
      if (q) subEl.textContent = `Nalezeno ${visibleTotal} z ${total} pojmů`;
      else if (state.groups.length > 1) subEl.textContent = `${state.groups.length} přednášek seřazených podle data`;
      else subEl.textContent = state.groups[0] ? `${state.groups[0].entries.length} pojmů v přednášce` : state.rawTitle;
    }
    if (countMeta) {
      countMeta.textContent = q ? `${visibleTotal}/${total}` : `${total} pojmů`;
    }
  }

  function renderGroups(groups, title) {
    state.groups = groups;
    document.title = `Teorie: ${title} · TZI Trenér`;

    if (!groups.length) {
      if (subEl) subEl.textContent = title;
      if (countMeta) countMeta.textContent = '0 pojmů';
      showEmpty('K téhle přednášce zatím není v teorii žádný obsah.');
      updateOverview();
      return;
    }

    const multi = groups.length > 1;
    gSet(outEl, groups.map((g, gi) => {
      const entries = g.entries || [];
      const cards = entries.map((e, ei) =>
        gEl('article', { class: 'entry', id: `e-${gi}-${ei}` },
          gEl('h3', null, gInline(e && e.term)),
          gBody(e && e.body, e && e.term)
        )
      );
      return gEl('section', { class: 'lec-group', id: `grp-${gi}`, 'aria-labelledby': `gh-${gi}` },
        gEl('div', { class: 'grp-head' },
          gEl('h2', { id: `gh-${gi}` }, g.heading),
          gEl('span', { class: 'grp-count' }, `${entries.length} pojmů`),
          g.topicsText ? gEl('div', { class: 'grp-topics' }, g.topicsText) : null
        ),
        gEl('div', { class: 'entries-list' }, cards)
      );
    }));

    state.groupEls = [...outEl.querySelectorAll('.lec-group')];
    state.entryIndex = [];
    state.tocEls = [];

    if (tocNav && tocAside) {
      tocAside.hidden = false;
      if (multi) {
        if (tocLabel) tocLabel.textContent = 'Přednášky';
        gSet(tocNav, groups.map((g, gi) =>
          gEl('a', { class: `toc-link${gi === 0 ? ' active' : ''}`, href: `#grp-${gi}`, title: g.label },
            gEl('span', null, g.heading),
            gEl('span', { class: 'toc-cnt' }, g.entries.length),
            g.topicsText ? gEl('span', { class: 'toc-sub' }, g.topicsText) : null
          )
        ));
        state.tocEls = [...tocNav.querySelectorAll('.toc-link')];
      } else {
        if (tocLabel) tocLabel.textContent = 'Pojmy v přednášce';
        const entries = groups[0].entries || [];
        gSet(tocNav, entries.map((e, ei) =>
          gEl('a', { class: `toc-link${ei === 0 ? ' active' : ''}`, href: `#e-0-${ei}` }, gEl('span', null, tocTermFrag(e.term)))
        ));
      }
    }

    let flatIdx = 0;
    const entryTocLinks = !multi && tocNav ? [...tocNav.querySelectorAll('.toc-link')] : [];
    groups.forEach((g, gi) => {
      const els = state.groupEls[gi] ? [...state.groupEls[gi].querySelectorAll('.entry')] : [];
      (g.entries || []).forEach((e, ei) => {
        const el = els[ei];
        if (!el) return;
        const tocEl = !multi ? entryTocLinks[flatIdx++] : null;
        state.entryIndex.push({
          el,
          grpIdx: gi,
          tocEl,
          searchText: norm(`${g.label || ''} ${e.term || ''} ${bodyWithoutSources(e.body)}`)
        });
      });
    });

    updateOverview();
    applyFilter();
  }

  function populateLectureSelect() {
    if (!lecSelect) return;
    const list = state.allMerged;
    if (!list.length) return;
    const total = list.reduce((s, g) => s + g.entries.length, 0);
    const opts = [gEl('option', { value: '_all' }, `Všechny přednášky (${total})`)];
    for (const g of list) {
      opts.push(gEl('option', { value: 'date:' + g.key }, g.heading));
    }
    gSet(lecSelect, opts);
    if (state.source === '_all' && state.activeDateKey) lecSelect.value = 'date:' + state.activeDateKey;
    else if (state.source === '_all') lecSelect.value = '_all';
    else if (state.groups.length === 1 && list.some(x => x.key === state.groups[0].key)) {
      lecSelect.value = 'date:' + state.groups[0].key;
    }
  }

  async function fetchGlosar(src) {
    const r = await fetch('/api/teorie?source=' + encodeURIComponent(src), { credentials: 'same-origin' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    if (!d || typeof d.title !== 'string' || !Array.isArray(d.groups)) throw new Error('invalid');
    return d;
  }

  async function selectView(pickVal, updateUrl = true) {
    const isDatePick = String(pickVal || '').startsWith('date:');
    const targetSrc = (isDatePick || pickVal === '_all') ? '_all' : pickVal;
    const safeSrc = /^[A-Za-z0-9_-]{1,64}$/.test(targetSrc) ? targetSrc : '_all';
    state.source = safeSrc;
    state.activeDateKey = isDatePick ? pickVal.slice(5) : '';

    if (updateUrl) {
      const u = new URL(location.href);
      u.searchParams.set('source', safeSrc);
      if (state.activeDateKey) u.searchParams.set('den', state.activeDateKey);
      else u.searchParams.delete('den');
      history.replaceState(null, '', u.pathname + u.search);
    }

    if (safeSrc === '_all' && state.allMerged.length) {
      const subset = state.activeDateKey ? state.allMerged.filter(g => g.key === state.activeDateKey) : state.allMerged;
      const viewTitle = state.activeDateKey && subset[0] ? subset[0].heading : state.rawTitle || 'Všechny přednášky podle data';
      populateLectureSelect();
      renderGroups(subset, viewTitle);
      return;
    }

    try {
      const d = await fetchGlosar(safeSrc);
      state.rawTitle = d.title;
      const merged = mergeGroupsByDate(d.groups);
      if (safeSrc === '_all') state.allMerged = merged;
      const subset = state.activeDateKey ? merged.filter(g => g.key === state.activeDateKey) : merged;
      const viewTitle = state.activeDateKey && subset[0] ? subset[0].heading : d.title;
      populateLectureSelect();
      renderGroups(subset, viewTitle);
    } catch (_) {
      showEmpty('Teorii se nepodařilo načíst.');
    }
  }

  if (qInput) {
    qInput.addEventListener('input', applyFilter);
    qInput.addEventListener('keydown', e => {
      if (e.key === 'Escape' && qInput.value) {
        qInput.value = '';
        applyFilter();
      }
    });
  }
  const clearSearch = () => {
    if (!qInput) return;
    qInput.value = '';
    applyFilter();
    qInput.focus();
  };
  if (qClear) qClear.addEventListener('click', clearSearch);
  if (resetFilterBtn) resetFilterBtn.addEventListener('click', clearSearch);
  if (emptyResetBtn) emptyResetBtn.addEventListener('click', clearSearch);

  document.addEventListener('keydown', e => {
    if (e.key === '/' && qInput && document.activeElement !== qInput && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
      e.preventDefault();
      qInput.focus();
      qInput.select();
    }
  });

  if (tocNav) {
    tocNav.addEventListener('click', e => {
      const link = e.target.closest('.toc-link');
      if (!link) return;
      tocNav.querySelectorAll('.toc-link.active').forEach(a => a.classList.remove('active'));
      link.classList.add('active');
    });
  }

  if (ovLectures) {
    ovLectures.addEventListener('click', async e => {
      const btn = e.target.closest('.ov-lec-btn');
      if (!btn) return;
      const pick = btn.dataset.pick || '_all';
      closeDrawer();
      await selectView(pick, true);
      window.scrollTo({ top: 0 });
    });
  }

  if (toTopBtn) {
    window.addEventListener('scroll', () => {
      toTopBtn.hidden = window.scrollY < 420;
    }, { passive: true });
    toTopBtn.addEventListener('click', () => window.scrollTo({ top: 0 }));
  }

  if (lecSelect) {
    lecSelect.addEventListener('change', () => {
      selectView(lecSelect.value || '_all', true);
    });
  }

  const sp = new URLSearchParams(location.search);
  const rawSource = sp.get('source') || '_all';
  const initSource = /^[A-Za-z0-9_-]{1,64}$/.test(rawSource) ? rawSource : '_all';
  const initDen = sp.get('den') || '';

  // Přednačíst _all pro kompletní přehled podle data i při otevření konkrétní banky z kvízu
  if (initSource !== '_all') {
    fetchGlosar('_all').then(allD => {
      state.allMerged = mergeGroupsByDate(allD.groups);
      if (!state.rawTitle) state.rawTitle = allD.title;
      populateLectureSelect();
      updateOverview();
    }).catch(() => {});
  }

  await selectView(initDen ? 'date:' + initDen : initSource, false);
})();
