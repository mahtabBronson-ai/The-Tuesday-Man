/* The Tuesday Man - minimal JS */

// Password reveal toggle
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-pw-toggle]').forEach(btn => {
    const targetId = btn.dataset.pwToggle;
    const input = document.getElementById(targetId);
    if (!input) return;
    btn.addEventListener('click', () => {
      const isText = input.type === 'text';
      input.type = isText ? 'password' : 'text';
      btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
    });
  });

  // Auto-dismiss flash messages after 5s
  document.querySelectorAll('.flash-bar').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });

  // Scroll to anchor on page load (for settings sections)
  if (window.location.hash) {
    const target = document.querySelector(window.location.hash);
    if (target) {
      setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    }
  }

  // Buddy inline edit toggle
  document.querySelectorAll('[data-edit-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      const panel = document.getElementById(btn.dataset.editToggle);
      if (!panel) return;
      const open = panel.style.display !== 'none';
      panel.style.display = open ? 'none' : 'block';
      btn.classList.toggle('active', !open);
    });
  });

  // Run Now button
  const runBtn = document.getElementById('run-now-btn');
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      runBtn.disabled = true;
      runBtn.textContent = 'Running…';
      try {
        const res = await fetch('/api/run-now', { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Done.');
      } catch (e) {
        alert('Error: ' + e.message);
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = 'Run dry run now';
      }
    });
  }

  // Run Inspector button
  const inspBtn = document.getElementById('run-inspector-btn');
  if (inspBtn) {
    inspBtn.addEventListener('click', async () => {
      inspBtn.disabled = true;
      inspBtn.textContent = 'Running…';
      try {
        const res = await fetch('/api/run-inspector', { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Done.');
      } catch (e) {
        alert('Error: ' + e.message);
      } finally {
        inspBtn.disabled = false;
        inspBtn.textContent = 'Run inspector now';
      }
    });
  }
});
