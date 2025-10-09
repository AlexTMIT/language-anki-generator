const socket = io();          // auto-connect
let mySid = null;

socket.on("connect", () => {
  mySid = socket.id;
});

// ---------- toast (reads data-flash) ----------
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
  if (!f.dataset.ajax) return;    // only forms with data-ajax
  e.preventDefault();

  const url = new URL(f.action, window.location.origin);
  if (mySid) url.searchParams.set("sid", mySid);

  try {
    const resp = await fetch(url, { method: "POST", body: new FormData(f) });
    const json = await resp.json();
    if (!json.next_url) throw new Error("Unexpected response");
    window.location = json.next_url;  // go to loader page
  } catch (err) {
    console.error(err);
    alert("Request failed – check console.");
  }
});