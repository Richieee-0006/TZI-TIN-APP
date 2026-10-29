let soundEnabled = localStorage.getItem('tzi_sound') !== '0';
function toggleSound() {
  soundEnabled = !soundEnabled;
  localStorage.setItem('tzi_sound', soundEnabled ? '1' : '0');
  const b = document.getElementById('btn-sound');
  if (b) b.style.opacity = soundEnabled ? '1' : '0.45';
}

const RANK_TITLES = ['', 'NPC', 'Nováček', 'Učeň', 'Student', 'Pokročilý', 'Teoretik', 'Mistr'];
function getRankInfo(xp) {
  const lvl = WASM_CORE.exp.calcRankLevel(xp | 0);
  const pct = WASM_CORE.exp.calcRankPct(xp | 0);
  return { lvl, title: RANK_TITLES[lvl] || 'NPC', pct };
}

const ACH_BIT_KEYS = ['first','start','wave','invincible','fifty','twohundred','marathon','learn','memory','regular','week','lucky','fast','done','routine','advanced','master'];
function updateAchievements(u, dp) {
  const listEl = document.getElementById('ach-list');
  if (!listEl || !listEl.querySelectorAll) return;
  const xp = (u && u.points) || 0;
  const bestStreak = (u && u.best_streak) || 0;
  const dStreak = (dp && dp.daily_streak) ?? (u && u.daily_streak) ?? 0;
  const goalMet = ((dp && dp.goal_met) ?? (u && u.daily_goal_met)) ? 1 : 0;
  const vals = Object.values(progress || {});
  const doneCount = vals.filter(v => v === 'correct').length;
  const hasWrong = vals.some(v => v === 'wrong') ? 1 : 0;
  const mask = WASM_CORE.exp.calcAchievementMask(xp | 0, bestStreak | 0, dStreak | 0, goalMet, doneCount | 0, hasWrong);
  let unlockedCount = 0;

  listEl.querySelectorAll('.ach-badge').forEach(el => {
    const key = el.getAttribute('data-ach');
    const bitIdx = ACH_BIT_KEYS.indexOf(key);
    const baseName = el.getAttribute('data-label') || key;
    const hint = el.getAttribute('data-hint') || '';
    const isUnl = bitIdx >= 0 && (mask & (1 << bitIdx)) !== 0;
    if (isUnl) {
      unlockedCount++;
      el.classList.add('unlocked');
    } else {
      el.classList.remove('unlocked');
    }
    el.innerHTML = `<span class="ach-title"><span>${esc(baseName)}</span><span>${isUnl ? '✓' : ''}</span></span>` +
      (hint ? `<small class="ach-hint">${esc(hint)}</small>` : '');
  });
  const cntEl = document.getElementById('prof-ach-count');
  if (cntEl) cntEl.textContent = `${unlockedCount} / ${ACH_BIT_KEYS.length} unlocked`;
}

function renderDailyProgressUI(dp) {
  if (!dp) return;
  const goal = dp.daily_goal || 5;
  const ans = dp.questions_answered ?? dp.questions_today ?? 0;
  const met = !!(dp.goal_met ?? dp.daily_goal_met);
  const dStreak = dp.daily_streak ?? 0;
  const pct = WASM_CORE.exp.calcPercentage(ans | 0, goal | 0);

  const stEl = document.getElementById('dp-streak');
  if (stEl) stEl.textContent = String(dStreak);
  const cntEl = document.getElementById('dp-count');
  if (cntEl) cntEl.innerHTML = `Denní cíl: <b>${ans}</b>/${goal} odpovědí (+50 XP)`;
  const barEl = document.getElementById('dp-bar-fill');
  if (barEl) {
    barEl.style.width = `${pct}%`;
    barEl.className = 'daily-bar-fill' + (met ? ' done' : '');
  }
  const statusEl = document.getElementById('dp-status');
  if (statusEl) {
    statusEl.textContent = met ? 'Splněno ✓' : '';
    statusEl.style.color = met ? 'var(--ok)' : 'var(--muted)';
  }
  const histEl = document.getElementById('dp-history');
  if (histEl && Array.isArray(dp.history)) {
    histEl.innerHTML = dp.history.slice(0, 7).map(h =>
      `<span class="daily-day-dot${h.goal_met ? ' met' : ''}" title="${esc(h.date)}: ${h.questions_answered} otázek">${esc(String(h.date).slice(5))} ${h.goal_met ? '✓' : '·'}</span>`
    ).join('');
  }
  updateAchievements(currentUserData, dp);
}

async function refreshDailyProgress() {
  if (!isOnline()) return;
  try {
    const res = await fetch('/api/daily-progress');
    if (res.ok) {
      const dp = await res.json();
      renderDailyProgressUI(dp);
    }
  } catch (e) {}
}

