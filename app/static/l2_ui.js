// l2_ui.js
// Shared overlay, toast, AJAX form hijack, Socket.IO progress wiring.

(function () {
  // ---------- overlay ----------
  const ov = document.createElement('div');
  ov.id = 'l2-overlay';
  ov.style.cssText = `
    display:none;position:fixed;inset:0;z-index:9999;
    backdrop-filter:blur(2px);background:rgba(0,0,0,.25);
    justify-content:center;align-items:center;
  `;
  ov.innerHTML = `
    <div style="text-align:center;color:#fff;">
      <div class="dots">
        <span class="dot"></span><span class="dot" style="animation-delay:.2s"></span>
        <span class="dot" style="animation-delay:.4s"></span>
      </div>
      <h4 id="l2-msg">Working…</h4>
    </div>`;
  document.addEventListener('DOMContentLoaded', () => document.body.append(ov));

  function showOverlay(msg) {
    document.getElementById('l2-msg').textContent = msg;
    ov.style.display = 'flex';
  }
  function hideOverlay() {
    ov.style.display = 'none';
  }

  // expose globally so other scripts can call
  window.L2Overlay = { show: showOverlay, hide: hideOverlay };

  // ---------- toast from Flask flash ----------------------------
  document.addEventListener('DOMContentLoaded', () => {
    const flash = document.querySelector('[data-flash]');
    if (!flash) return;
    const toast = document.createElement('div');
    toast.className = 'l2-toast';
    toast.textContent = flash.dataset.flash;
    document.body.append(toast);
    setTimeout(() => toast.classList.add('show'), 50);
    setTimeout(() => toast.classList.remove('show'), 4000);
  });

  // ---------- AJAX form hijack (opt-in w/ data-ajax) -------------
  document.addEventListener('submit', async (e) => {
    const f = e.target;
    if (!('ajax' in f.dataset)) return;       // not opted in
    e.preventDefault();

    showOverlay(f.dataset.msg || 'Working…');

    try {
      const resp = await fetch(f.action, {
        method: 'POST',
        body: new FormData(f)
      });
      const data = await resp.json();
      hideOverlay();
      if (data.next) {
        window.location.href = data.next;
      } else {
        console.error('No next URL in response', data);
      }
    } catch (err) {
      console.error('AJAX form error', err);
      hideOverlay();
      alert('Request failed.');
    }
  });

  // ---------- Socket.IO progress feed ----------------------------
  // (after DOM load so that window.io is guaranteed available)
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof io !== 'function') {
      console.error('Socket.IO client not found!');
      return;
    }
    const socket = io();   // auto-connect (same origin)
    socket.on('progress', msg => showOverlay(msg));
  });
})();