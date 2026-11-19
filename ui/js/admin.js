(function () {
  try {
    const th = localStorage.getItem('tzi_theme');
    if (['dark', 'amoled', 'light', 'catppuccin', 'auto'].includes(th)) {
      document.documentElement.setAttribute('data-theme', th);
    }
  } catch (e) {}

  const limitSelect = document.getElementById('limit-select');
  if (limitSelect && limitSelect.dataset.limit) {
    limitSelect.value = limitSelect.dataset.limit;
  }

  let allStacksExpanded = false;
  function toggleAllStacks() {
    allStacksExpanded = !allStacksExpanded;
    document.querySelectorAll('#errors-tbody details').forEach(d => {
      d.open = allStacksExpanded;
    });
    const btn = document.getElementById('btn-toggle-stacks');
    if (btn) btn.textContent = allStacksExpanded ? 'Sbalit všechny stacktrace' : 'Rozbalit všechny stacktrace';
  }

  function toggleSort() {
    const sortEl = document.getElementById('filter-sort');
    if (!sortEl) return;
    sortEl.value = sortEl.value === 'desc' ? 'asc' : 'desc';
    applyErrorFilters();
  }

  function resetErrorFilters() {
    ['filter-search', 'filter-level', 'filter-endpoint', 'filter-uid'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const sortEl = document.getElementById('filter-sort');
    if (sortEl) sortEl.value = 'desc';
    applyErrorFilters();
  }

  function applyErrorFilters() {
    const query = (document.getElementById('filter-search')?.value || '').toLowerCase().trim();
    const level = (document.getElementById('filter-level')?.value || '').trim().toUpperCase();
    const endpoint = (document.getElementById('filter-endpoint')?.value || '').toLowerCase().trim();
    const uid = (document.getElementById('filter-uid')?.value || '').toLowerCase().trim();
    const sort = document.getElementById('filter-sort')?.value || 'desc';

    const tbody = document.getElementById('errors-tbody');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr.error-item'));

    let visibleCount = 0;
    rows.forEach(row => {
      const rLevel = (row.getAttribute('data-level') || '').toUpperCase();
      const rEndpoint = (row.getAttribute('data-endpoint') || '').toLowerCase();
      const rUid = (row.getAttribute('data-uid') || '').toLowerCase();
      const rText = row.textContent.toLowerCase();

      let match = true;
      if (level && rLevel !== level) match = false;
      if (match && endpoint && !rEndpoint.includes(endpoint)) match = false;
      if (match && uid && !rUid.includes(uid)) match = false;
      if (match && query && !rText.includes(query)) match = false;

      row.style.display = match ? '' : 'none';
      if (match) visibleCount++;
    });

    const visibleRows = rows.filter(r => r.style.display !== 'none');
    visibleRows.sort((a, b) => {
      const tsA = a.getAttribute('data-ts') || '';
      const tsB = b.getAttribute('data-ts') || '';
      return sort === 'asc' ? tsA.localeCompare(tsB) : tsB.localeCompare(tsA);
    });
    visibleRows.forEach(r => tbody.appendChild(r));

    const stats = document.getElementById('filter-stats');
    if (stats) stats.textContent = `Zobrazeno ${visibleCount} z ${rows.length} záznamů`;
  }

  function filterStudents() {
    const query = (document.getElementById('student-search')?.value || '').toLowerCase().trim();
    const rows = Array.from(document.querySelectorAll('#students-tbody tr.student-row'));
    let visible = 0;
    rows.forEach(r => {
      const u = (r.getAttribute('data-username') || '').toLowerCase();
      const match = !query || u.includes(query);
      r.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    const info = document.getElementById('students-count-text');
    if (info && rows.length > 0) {
      info.textContent = query ? `Nalezeno ${visible} z ${rows.length} studentů` : `Celkem ${rows.length} studentů v databázi`;
    }
  }

  function openResetModal(uid, username, points, streak) {
    const modal = document.getElementById('reset-modal');
    if (!modal) return;
    document.getElementById('modal-user-id').value = uid;
    document.getElementById('modal-student-name').textContent = username;
    document.getElementById('modal-student-stats').textContent = `(${points} bodů, streak ${streak})`;
    const radAll = modal.querySelector('input[name="scope"][value="all"]');
    if (radAll) radAll.checked = true;
    if (typeof modal.showModal === 'function') modal.showModal();
    else modal.style.display = 'block';
  }

  function closeResetModal() {
    const modal = document.getElementById('reset-modal');
    if (!modal) return;
    if (typeof modal.close === 'function') modal.close();
    else modal.style.display = 'none';
  }

  function init() {
    applyErrorFilters();
    filterStudents();

    document.getElementById('student-search')?.addEventListener('input', filterStudents);
    limitSelect?.addEventListener('change', () => {
      window.location.href = '/admin?limit=' + encodeURIComponent(limitSelect.value);
    });
    document.getElementById('filter-search')?.addEventListener('input', applyErrorFilters);
    document.getElementById('filter-level')?.addEventListener('change', applyErrorFilters);
    document.getElementById('filter-endpoint')?.addEventListener('input', applyErrorFilters);
    document.getElementById('filter-uid')?.addEventListener('input', applyErrorFilters);
    document.getElementById('filter-sort')?.addEventListener('change', applyErrorFilters);
    document.getElementById('btn-reset-filters')?.addEventListener('click', resetErrorFilters);
    document.getElementById('btn-toggle-stacks')?.addEventListener('click', toggleAllStacks);
    document.getElementById('btn-toggle-sort')?.addEventListener('click', toggleSort);
    document.getElementById('btn-modal-close-x')?.addEventListener('click', closeResetModal);
    document.getElementById('btn-modal-cancel')?.addEventListener('click', closeResetModal);

    document.addEventListener('click', e => {
      const btn = e.target && e.target.closest ? e.target.closest('[data-reset-modal]') : null;
      if (!btn) return;
      openResetModal(
        btn.dataset.uid || '',
        btn.dataset.username || '',
        btn.dataset.points || '0',
        btn.dataset.streak || '0'
      );
    });

    document.addEventListener('submit', e => {
      const form = e.target && e.target.closest ? e.target.closest('form[data-confirm]') : null;
      if (!form) return;
      if (!window.confirm(form.dataset.confirm || 'Potvrdit akci?')) {
        e.preventDefault();
      }
    });

    const modal = document.getElementById('reset-modal');
    if (modal) {
      modal.addEventListener('click', e => {
        const rect = modal.getBoundingClientRect();
        const isInDialog = rect.top <= e.clientY && e.clientY <= rect.top + rect.height
          && rect.left <= e.clientX && e.clientX <= rect.left + rect.width;
        if (!isInDialog) closeResetModal();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
