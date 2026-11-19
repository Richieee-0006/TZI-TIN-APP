(function () {
  try {
    const th = localStorage.getItem('tzi_theme');
    if (['dark', 'amoled', 'light', 'catppuccin', 'auto'].includes(th)) {
      document.documentElement.setAttribute('data-theme', th);
    }
  } catch (e) {}

  function switchTab(t) {
    const loginForm = document.getElementById('login-form');
    const regForm = document.getElementById('reg-form');
    if (loginForm) loginForm.classList.toggle('is-hidden', t !== 'login');
    if (regForm) regForm.classList.toggle('is-hidden', t !== 'reg');
    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === t);
    });
  }

  document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
})();
