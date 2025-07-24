// --------------- Socket.IO --------------------------
const socket = io();

let mySid = null;

socket.on("connect", () => {
  mySid = socket.id;
});

socket.on("progress", msg => L2Overlay.show(msg));
socket.on("done",      data => {
  window.location.href = data.next;
});

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

  // expose globally
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
  document.addEventListener("submit", async e => {
    const f = e.target;
    if (!("ajax" in f.dataset)) return;  // opt-in only

    const raw = f.querySelector("#blob").value.trim();
    const ok  = /^\s*[^,\s]+(?:, [^,\s]+)*\s*$/.test(raw);
    if (!ok) {
      const msg = "Words must be separated by ', ' (comma + space).";
      document.getElementById("blobErr").style.display = "block";
      document.getElementById("blobErr").textContent = msg;
      return;                         // ⬅ abort submit
    }
    document.getElementById("blobErr").style.display = "none";

    e.preventDefault();
    L2Overlay.show(f.dataset.msg || "Working…");

    const url = new URL(f.action, window.location.origin);
    if (mySid) url.searchParams.set("sid", mySid);

    try {
      const resp = await fetch(url, {
        method: "POST",
        body: new FormData(f)
      });
      const json = await resp.json();
      if (json.started) {
        return;
      }
    } catch (err) {
      console.error(err);
      alert("Request failed. WTF");
    }
  });

})();