// static/js/progress.js

document.addEventListener('DOMContentLoaded', () => {
  const sid   = document.getElementById('loader').dataset.sid;
  const fill  = document.querySelector('.fill');
  const pct   = document.querySelector('.pct');
  const currN = document.getElementById('curr-num');
  const currT = document.getElementById('curr-total');

  const byId = id => document.getElementById(id);

  // update a step’s icon & color
  function setState(id, cls) {
    const li   = byId(id);
    const icon = li.querySelector('i');
    li.classList.remove('idle','run','done','fail');
    li.classList.add(cls);

    switch (cls) {
      case 'run':
        icon.className = 'fa-solid fa-circle-notch fa-spin';
        break;
      case 'done':
        icon.className = 'fa-solid fa-circle-check';
        break;
      case 'fail':
        icon.className = 'fa-solid fa-circle-xmark';
        break;
      default:
        icon.className = 'fa-regular fa-circle';
    }
  }

  // set the right‐hand pct + spinner
  function updatePct(p, spin = true) {
    if (spin && p < 100) {
      pct.innerHTML = `${p}% <i class="fa-solid fa-circle-notch fa-spin"></i>`;
    } else {
      pct.textContent = `${p}%`;
    }
  }

  // Socket.IO
  const socket = io({ autoConnect: false });
  socket.auth = { sid };
  socket.connect();
  socket.on('connect', () => socket.emit('loader:ready', { sid }));

  // INITIALIZE
  socket.on('tracker:init', ({ total }) => {
    fill.style.width = '0%';
    updatePct(0);
    currN.textContent = '0';
    currT.textContent = total;
  });

  // STEP START
  socket.on('tracker:start', ({ id }) => {
    setState(id, 'run');
    const li = byId(id);
    const h2 = document.getElementById('task-label');
    if (li && h2) h2.textContent = li.dataset.label + '…';

    fill.style.width = '0%';
    updatePct(0);
    currN.textContent = '0';
  });

  // PROGRESS
  socket.on('tracker:progress', ({ done, total }) => {
    if (total !== null) {
      const p = Math.floor(done / total * 100);
      fill.style.width = `${p}%`;
      updatePct(p);
      currN.textContent = done;
      currT.textContent = total;
    }
  });

  // DONE
  socket.on('tracker:done', ({ id }) => {
    setState(id, 'done');
    fill.style.width = '100%';
    updatePct(100, false);
  });

  // ERROR
  socket.on('tracker:error', ({ id }) => setState(id, 'fail'));

  // FINISH → redirect
  socket.on('tracker:finish', ({ next }) => {
    window.location = next;
  });
});