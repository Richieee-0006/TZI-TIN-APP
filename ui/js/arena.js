function updateCompArenaMenuState(openRoomsCount = null, kingName = null) {
  const btn = document.getElementById('btn-comp-arena');
  const desc = document.getElementById('comp-arena-desc');
  const badge = document.getElementById('comp-arena-badge');
  if (!btn) return;
  const offline = !isOnline() || serverUnreachable;
  btn.disabled = offline;
  if (offline) {
    btn.classList.add('comp-disabled');
    if (desc) desc.textContent = 'Nedostupné v offline režimu – vyžaduje spojení s backendem';
    if (badge) badge.textContent = 'Offline';
  } else {
    btn.classList.remove('comp-disabled');
    if (desc && openRoomsCount !== null) {
      const kTxt = kingName ? ` · King: ${kingName}` : '';
      desc.textContent = `Otevřené místnosti: ${openRoomsCount}${kTxt} · FFA, 1v1 Duel & KotH`;
    } else if (desc && String(desc.textContent || '').includes('Nedostupné')) {
      desc.textContent = 'Vytvoř nebo se připoj do místnosti · FFA, 1v1 Duel & King of the Hill';
    }
    if (badge) {
      badge.textContent = (openRoomsCount && openRoomsCount > 0) ? `${openRoomsCount} roomek` : 'Aréna →';
    }
  }
}

function selectArenaRoomMode(mode) {
  const sel = document.getElementById('room-mode-select');
  if (sel) sel.value = mode;
  const cards = document.querySelectorAll('.arena-mode-card');
  if (cards && cards.forEach) {
    cards.forEach(c => {
      if (c.getAttribute('data-mode') === mode) c.classList.add('active');
      else c.classList.remove('active');
    });
  }
}

async function openCompArena() {
  if (!isOnline()) {
    updateCompArenaMenuState();
    showToast('⚡ Kompetitivní aréna není v offline režimu dostupná.');
    return;
  }
  try {
    const res = await fetch('/api/competitive/overview');
    if (!res.ok) throw new Error('Backend unreachable');
    serverUnreachable = false;
    updateNetStatus();
    const ov = await res.json();
    if (ov.ffa) renderFfaUI(ov.ffa);
    if (ov.duel) renderDuelUI(ov.duel);
    if (ov.koth) renderKothUI(ov.koth, ov);
    if (ov.rooms) renderRoomsListUI(ov.rooms);
    const waitingCount = ov.rooms && Array.isArray(ov.rooms.active_rooms) ? ov.rooms.active_rooms.filter(r => r.status === 'waiting').length : 0;
    const kingUser = ov.koth && ov.koth.king ? ov.koth.king.username : null;
    updateCompArenaMenuState(waitingCount, kingUser);
  } catch (e) {
    serverUnreachable = true;
    updateNetStatus();
    showToast('⚠️ Server pro kompetitivní arénu je momentálně nedostupný.');
    return;
  }
  show('comp-arena');
}

