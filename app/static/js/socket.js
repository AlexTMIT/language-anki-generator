const socket = io();          // auto-connect
let mySid = null;

socket.on("connect", () => { mySid = socket.id; });

// ---------- overlay ----------
const Overlay = (() => {
  const el = document.createElement("div");
  el.id = "l2-overlay";
  el.style.cssText = `
    display:none;position:fixed;inset:0;z-index:2000;
    backdrop-filter:blur(2px);background:rgba(0,0,0,.25);
    justify-content:center;align-items:center;
  `;
  el.innerHTML = `
    <div style="text-align:center;color:#fff;">
      <div class="dots">
        <span class="dot"></span><span class="dot" style="animation-delay:.2s"></span>
        <span class="dot" style="animation-delay:.4s"></span>
      </div>
      <h4 id="l2-msg">Working…</h4>
    </div>`;
  document.addEventListener("DOMContentLoaded", () => document.body.append(el));

  const show = msg => {
    document.getElementById("l2-msg").textContent = msg;
    el.style.display = "flex";
  };
  const hide = () => { el.style.display = "none"; };
  return { show, hide };
})();

// Socket progress → overlay
socket.on("progress", msg => Overlay.show(msg));
socket.on("done", data => window.location.href = data.next);

// ---------- toast (reads data-flash div injected by Jinja) ----------
document.addEventListener("DOMContentLoaded", () => {
  const flash = document.querySelector("[data-flash]");
  if (!flash) return;
  const toast = document.createElement("div");
  toast.className = "l2-toast";
  toast.textContent = flash.dataset.flash;
  document.body.append(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => toast.classList.remove("show"), 4000);
});

// ---------- AJAX opt-in (data-ajax) ----------
document.addEventListener("submit", async e => {
  const f = e.target;
  if (!("ajax" in f.dataset)) return;
  e.preventDefault();

  Overlay.show(f.dataset.msg || "Working…");

  const url = new URL(f.action, window.location.origin);
  if (mySid) url.searchParams.set("sid", mySid);

  try {
    const resp = await fetch(url, { method: "POST", body: new FormData(f) });
    const json = await resp.json();
    if (!json.started) throw new Error("Unexpected response");
    // let the background job push progress / done events
  } catch (err) {
    console.error(err);
    alert("Request failed – check console.");
    Overlay.hide();
  }
});

/* ---------- tiny CSS for overlay dots ---------- */
const style = document.createElement("style");
style.textContent = `
.dots{display:inline-block}
.dot{width:8px;height:8px;margin:0 2px;border-radius:50%;
     background:#2196f3;display:inline-block;animation:l2-b .9s infinite}
@keyframes l2-b{0%,80%,100%{transform:scale(0)}40%{transform:scale(1)}}
`;
document.head.append(style);