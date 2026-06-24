/* The Tuesday Man - minimal JS */

// Password reveal toggle
document.addEventListener('DOMContentLoaded', () => {
  // Dynamic greeting based on local time
  const greetEl = document.getElementById('page-greeting');
  if (greetEl) {
    const h = new Date().getHours();
    const word = h >= 5  && h < 12 ? 'Good morning'
               : h >= 12 && h < 17 ? 'Good afternoon'
               : h >= 17 && h < 21 ? 'Good evening'
               : 'Good night';
    greetEl.textContent = greetEl.textContent.replace(
      /^Good (morning|afternoon|evening|night)/i, word
    );
  }

  // Profile dropdown toggle
  const profileBtn      = document.getElementById('profile-btn');
  const profileDropdown = document.getElementById('profile-dropdown');
  if (profileBtn && profileDropdown) {
    profileBtn.addEventListener('click', e => {
      e.stopPropagation();
      const open = profileDropdown.classList.toggle('open');
      profileBtn.setAttribute('aria-expanded', open);
    });
    document.addEventListener('click', () => {
      profileDropdown.classList.remove('open');
      if (profileBtn) profileBtn.setAttribute('aria-expanded', 'false');
    });
    profileDropdown.addEventListener('click', e => e.stopPropagation());
  }

  // Hamburger menu toggle
  const menuBtn = document.getElementById('menu-toggle');
  const topnav  = document.getElementById('topnav');
  if (menuBtn && topnav) {
    menuBtn.addEventListener('click', () => {
      const open = topnav.classList.toggle('open');
      menuBtn.classList.toggle('open', open);
      menuBtn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });
    // Close menu when a nav link is tapped
    topnav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        topnav.classList.remove('open');
        menuBtn.classList.remove('open');
      });
    });
  }

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
