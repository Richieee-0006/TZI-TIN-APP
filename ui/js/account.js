async function openLeaderboardView() {
  show('leaderboard-view');
  if (!isOnline()) return;
  try {
    const [lbRes, compRes] = await Promise.all([
      fetch('/api/leaderboard'),
      fetch('/api/competitive/overview')
    ]);
    if (lbRes.ok) {
      const lb = await lbRes.json();
      if ($('lb-my-rank')) $('lb-my-rank').textContent = lb.rank !== '-' ? `#${lb.rank} z ${lb.total}` : 'Host';
      if ($('lb-my-xp')) $('lb-my-xp').textContent = `${lb.points || 0} XP`;
      if ($('lb-my-streak')) $('lb-my-streak').textContent = `${lb.best_streak || 0}`;
      if ($('lb-my-dstreak')) $('lb-my-dstreak').textContent = `${lb.daily_streak || 0} dní`;
      if ($('lb-total-users')) $('lb-total-users').textContent = `${lb.total || 0} registrovaných`;
      const tbody = $('lb-table-body');
      const rows = Array.isArray(lb.leaderboard) ? lb.leaderboard : [];
      const myName = currentUserData ? currentUserData.username : '';
      if (tbody) {
        tbody.innerHTML = rows.length ? rows.map((r, i) => {
          const rInfo = getRankInfo(r.points || 0);
          const isMe = myName && r.username === myName;
          return `<tr class="${isMe ? 'me-row' : ''}">
            <td><b>#${i + 1}</b></td>
            <td><b>${esc(r.username)}</b>${isMe ? ' <small style="color:var(--blue)">(You)</small>' : ''}</td>
            <td><span style="font-family:var(--mono);font-size:.8rem;">Lvl ${rInfo.lvl} · ${rInfo.title}</span></td>
            <td><b style="color:var(--ok);font-family:var(--mono);">${r.points || 0} XP</b></td>
            <td>${r.best_streak || 0}</td>
            <td>${r.daily_streak || 0}d</td>
          </tr>`;
        }).join('') : '<tr><td colspan="6">Zatím žádné záznamy.</td></tr>';
      }
    }
    if (compRes.ok) {
      const ov = await compRes.json();
      const compEl = $('lb-comp-summary');
      if (compEl) {
        const items = [];
        if (ov.koth && ov.koth.king) {
          items.push(`<li><span>👑 <b>Král kopce (KotH):</b> ${esc(ov.koth.king.username)} (obhájení ${ov.koth.king.defenses_count || 0}×)</span><span><b>${ov.koth.king.score} b.</b></span></li>`);
        }
        if (ov.ffa && Array.isArray(ov.ffa.leaderboard) && ov.ffa.leaderboard.length) {
          ov.ffa.leaderboard.slice(0, 3).forEach((r, idx) => {
            items.push(`<li><span>🏟️ <b>FFA #${idx + 1}:</b> ${esc(r.username)} (${r.best_correct}/10 správně)</span><span><b>${r.best_score} b.</b></span></li>`);
          });
        }
        if (ov.duel && Array.isArray(ov.duel.leaderboard) && ov.duel.leaderboard.length) {
          ov.duel.leaderboard.slice(0, 3).forEach((r, idx) => {
            items.push(`<li><span>⚔️ <b>1v1 Duel #${idx + 1}:</b> ${esc(r.username)}</span><span><b>🏆 ${r.wins} výher</b></span></li>`);
          });
        }
        compEl.innerHTML = items.length ? items.join('') : '<li><span>Zatím žádné odehrané kompetitivní zápasy.</span></li>';
      }
    }
  } catch (e) {}
}

async function openProfileView() {
  show('profile-view');
  await refreshDailyProgress();
  const u = currentUserData || {};
  const rInfo = getRankInfo(u.points || 0);
  if ($('prof-lvl-title')) $('prof-lvl-title').textContent = `Lvl ${rInfo.lvl} · ${rInfo.title}`;
  if ($('prof-best-streak')) $('prof-best-streak').textContent = `${u.best_streak || 0}`;
  if ($('prof-role-badge')) $('prof-role-badge').textContent = u.role === 'admin' ? 'Administrator' : (u.role === 'trial' ? 'Trial Guest' : `Player: ${u.username || ''}`);
  if ($('prof-new-username') && u.username && u.role !== 'trial') $('prof-new-username').value = u.username;

  if (!isOnline()) {
    const localVals = Object.values(progress || {});
    const c = localVals.filter(v => v === 'correct').length;
    const w = localVals.filter(v => v === 'wrong').length;
    const acc = WASM_CORE.exp.calcRecapAccuracy(c | 0, w | 0);
    if ($('prof-accuracy')) $('prof-accuracy').textContent = `${acc} %`;
    if ($('prof-mastered')) $('prof-mastered').textContent = `${c} správně`;
    return;
  }
  try {
    const res = await fetch('/api/account/recap');
    if (res.ok) {
      const recap = await res.json();
      const tc = recap.total_correct || 0;
      const tw = recap.total_wrong || 0;
      const tq = recap.total_questions || 0;
      const acc = WASM_CORE.exp.calcRecapAccuracy(tc | 0, tw | 0);
      const cov = WASM_CORE.exp.calcPercentage(tc | 0, tq | 0);
      if ($('prof-accuracy')) $('prof-accuracy').textContent = `${acc} %`;
      if ($('prof-mastered')) $('prof-mastered').textContent = `${tc} / ${tq} (${cov} %)`;
      const listEl = $('profile-recap-sources');
      if (listEl && Array.isArray(recap.sources)) {
        listEl.innerHTML = recap.sources.map(s => {
          const okPct = WASM_CORE.exp.calcPercentage(s.correct | 0, s.total | 0);
          const badPct = WASM_CORE.exp.calcPercentage(s.wrong | 0, s.total | 0);
          return `<div class="recap-source-row">
            <div class="recap-source-top">
              <strong>${esc(s.title)}</strong>
              <span style="font-family:var(--mono);font-size:.8rem;color:var(--muted);"><b style="color:var(--ok)">${s.correct}✓</b> · <b style="color:var(--bad)">${s.wrong}✗</b> / ${s.total} (${okPct} %)</span>
            </div>
            <div class="recap-bar">
              <div class="recap-bar-ok" style="width:${okPct}%"></div>
              <div class="recap-bar-bad" style="width:${badPct}%"></div>
            </div>
          </div>`;
        }).join('');
      }
    }
  } catch (e) {}
}

async function submitUsernameChange() {
  const inp = $('prof-new-username');
  if (!inp) return;
  const username = inp.value.trim();
  try {
    const res = await fetch('/api/account/username', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify({ username })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast('⚠️ ' + (data.detail || 'Změna přezdívky se nezdařila.'));
      return;
    }
    showToast(`✅ Přezdívka změněna na <b>${esc(data.username)}</b>`);
    await refreshUserStats();
    await openProfileView();
  } catch (e) {
    showToast('⚠️ Chyba spojení se serverem.');
  }
}

async function submitPasswordChange() {
  const curEl = $('prof-cur-pw'), newEl = $('prof-new-pw'), new2El = $('prof-new-pw2');
  if (!curEl || !newEl || !new2El) return;
  try {
    const res = await fetch('/api/account/password', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify({
        current_password: curEl.value,
        new_password: newEl.value,
        new_password_confirm: new2El.value
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast('⚠️ ' + (data.detail || 'Změna hesla selhala.'));
      return;
    }
    curEl.value = ''; newEl.value = ''; new2El.value = '';
    showToast('✅ Heslo bylo úspěšně změněno.');
  } catch (e) {
    showToast('⚠️ Chyba spojení se serverem.');
  }
}

let pendingDeleteScope = 'source';
function openRevalidateModal(scope = 'source') {
  pendingDeleteScope = scope;
  const isTrial = currentUserData && currentUserData.role === 'trial';
  const descEl = $('reval-modal-desc');
  const inpEl = $('reval-password-input');
  const errEl = $('reval-error-msg');
  if (errEl) errEl.textContent = '';
  if (inpEl) {
    inpEl.value = '';
    inpEl.type = isTrial ? 'text' : 'password';
    inpEl.placeholder = isTrial ? 'Napiš SMAZAT pro potvrzení...' : 'Zadej heslo svého účtu...';
  }
  if (descEl) {
    descEl.textContent = scope === 'all'
      ? (isTrial ? 'Chystáš se smazat veškerý postup. Napiš slovo SMAZAT.' : 'Chystáš se nenávratně smazat veškerý postup všech přednášek. Potvrď akci svým heslem.')
      : (isTrial ? 'Chystáš se smazat postup aktuální přednášky. Napiš slovo SMAZAT.' : `Chystáš se smazat postup přednášky (${currentSource || 'aktuální'}). Potvrď akci svým heslem.`);
  }
  const modal = $('revalidate-modal');
  if (modal) modal.classList.add('show');
  if (inpEl) inpEl.focus();
}


let deleteProfileStep = 1;
function openDeleteProfileModal() {
  if (currentUserData && currentUserData.role === 'trial') {
    showToast('Trial guest profile does not have a registered account to remove.');
    return;
  }
  deleteProfileStep = 1;
  if ($('del-prof-ack-chk')) $('del-prof-ack-chk').checked = false;
  if ($('del-prof-user-inp')) $('del-prof-user-inp').value = '';
  if ($('del-prof-phrase-inp')) $('del-prof-phrase-inp').value = '';
  if ($('del-prof-pw-inp')) $('del-prof-pw-inp').value = '';
  if ($('del-prof-err')) $('del-prof-err').textContent = '';
  if ($('del-prof-expected-user')) $('del-prof-expected-user').textContent = (currentUserData && currentUserData.username) || '';
  renderDeleteProfileStepUI();
  const modal = $('delete-profile-modal');
  if (modal) modal.classList.add('show');
}

function closeDeleteProfileModal() {
  const modal = $('delete-profile-modal');
  if (modal) modal.classList.remove('show');
}

function renderDeleteProfileStepUI() {
  if ($('del-prof-step-1')) $('del-prof-step-1').style.display = deleteProfileStep === 1 ? 'block' : 'none';
  if ($('del-prof-step-2')) $('del-prof-step-2').style.display = deleteProfileStep === 2 ? 'block' : 'none';
  if ($('del-prof-step-3')) $('del-prof-step-3').style.display = deleteProfileStep === 3 ? 'block' : 'none';
  if ($('del-prof-step-badge')) $('del-prof-step-badge').textContent = `Step ${deleteProfileStep} / 3`;
  const btn = $('del-prof-submit-btn');
  if (btn) {
    btn.textContent = deleteProfileStep === 1 ? 'Continue (1/3) →' : deleteProfileStep === 2 ? 'Continue (2/3) →' : 'Permanently Remove Profile (3/3)';
  }
}

async function submitDeleteProfileStep() {
  const errEl = $('del-prof-err');
  if (errEl) errEl.textContent = '';

  if (deleteProfileStep === 1) {
    const chk = $('del-prof-ack-chk');
    if (!chk || !chk.checked) {
      if (errEl) errEl.textContent = 'Please check the confirmation box to proceed.';
      return;
    }
    deleteProfileStep = 2;
    renderDeleteProfileStepUI();
    if ($('del-prof-user-inp')) $('del-prof-user-inp').focus();
    return;
  }

  if (deleteProfileStep === 2) {
    const uInp = ($('del-prof-user-inp') ? $('del-prof-user-inp').value : '').trim();
    const pInp = ($('del-prof-phrase-inp') ? $('del-prof-phrase-inp').value : '').trim().toUpperCase();
    const expected = (currentUserData && currentUserData.username) || '';
    if (uInp !== expected) {
      if (errEl) errEl.textContent = `Username must match "${expected}" exactly.`;
      return;
    }
    if (pInp !== 'DELETE') {
      if (errEl) errEl.textContent = 'Please type DELETE in the second field.';
      return;
    }
    deleteProfileStep = 3;
    renderDeleteProfileStepUI();
    if ($('del-prof-pw-inp')) $('del-prof-pw-inp').focus();
    return;
  }

  const pw = $('del-prof-pw-inp') ? $('del-prof-pw-inp').value : '';
  if (!pw) {
    if (errEl) errEl.textContent = 'Please enter your password.';
    return;
  }
  try {
    const res = await fetch('/api/account/delete-profile', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify({
        step1_ack: true,
        confirm_username: ($('del-prof-user-inp') ? $('del-prof-user-inp').value : '').trim(),
        confirm_phrase: ($('del-prof-phrase-inp') ? $('del-prof-phrase-inp').value : '').trim(),
        password: pw
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (errEl) errEl.textContent = data.detail || 'Profile deletion failed.';
      return;
    }
    localStorage.clear();
    window.location.href = data.redirect || '/login';
  } catch (e) {
    if (errEl) errEl.textContent = 'Connection error while removing profile.';
  }
}

function closeRevalidateModal() {
  const modal = $('revalidate-modal');
  if (modal) modal.classList.remove('show');
}

async function confirmRevalidatedDelete() {
  const inpEl = $('reval-password-input');
  const errEl = $('reval-error-msg');
  const password = inpEl ? inpEl.value : '';
  if (!password) return;
  try {
    const res = await fetch('/api/account/revalidate-delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify({
        password,
        scope: pendingDeleteScope,
        source: currentSource
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (errEl) errEl.textContent = data.detail || 'Ověření selhalo.';
      return;
    }
    closeRevalidateModal();
    if (pendingDeleteScope === 'all') {
      progress = {};
      session = null;
      localStorage.removeItem('tzi_local_progress_' + currentSource);
      showToast('🗑️ Veškerý studijní postup byl po ověření smazán.');
    } else {
      const ids = new Set(FULL.map(q => q.id));
      const keep = Object.fromEntries(Object.entries(progress).filter(([k]) => !ids.has(k)));
      progress = keep;
      session = null;
      localStorage.setItem('tzi_local_progress_' + currentSource, JSON.stringify(keep));
      showToast('🗑️ Postup vybrané přednášky byl po ověření smazán.');
    }
    updateMenuStats(false);
    if ($('profile-view') && $('profile-view').style.display === 'block') {
      await openProfileView();
    }
  } catch (e) {
    if (errEl) errEl.textContent = 'Chyba spojení se serverem při ověřování.';
  }
}

