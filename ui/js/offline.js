let isSyncing = false;
async function syncOfflineQueue() {
  if (isSyncing || !isOnline()) return;
  const oq = getOfflineQueue();
  if (!oq.length) {
    updateNetStatus();
    refreshUserStats();
    return;
  }
  isSyncing = true;
  updateNetStatus();
  try {
    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-TZI': '1'},
      body: JSON.stringify({
        source: currentSource || '_default',
        seen: progress,
        answers: oq
      })
    });
    if (res.ok) {
      const data = await res.json();
      localStorage.removeItem(OFFLINE_QUEUE_KEY);
      updateNetStatus();
      if (data.points_awarded > 0) {
        showToast(`🔄 Synchronizováno: <b>+${data.points_awarded} b.</b> (${data.synced_count} otázek)`);
      } else if (data.synced_count > 0) {
        showToast(`🔄 Synchronizováno ${data.synced_count} offline odpovědí.`);
      }
      refreshUserStats();
    }
  } catch(e) {
    console.warn('[TZI] Sync offline failed, will retry', e);
  } finally {
    isSyncing = false;
    updateNetStatus();
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => { updateNetStatus(); syncOfflineQueue(); });
  window.addEventListener('offline', () => { updateNetStatus(); });
}

async function prefetchBanksForOffline() {
  if (!isOnline()) return;
  try {
    const sRes = await fetch('/api/sources');
    if (!sRes.ok) return;
    const sData = await sRes.json();
    const srcs = (sData.sources || []).map(s => s.id);
    for (const src of srcs) {
      fetch(`/api/questions?source=${encodeURIComponent(src)}`).catch(() => {});
    }
    fetch('/api/recall').catch(() => {});
  } catch(e) {}
}

