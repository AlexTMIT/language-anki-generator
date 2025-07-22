document.addEventListener('DOMContentLoaded', () => {
  const max       = 3;
  const grid      = document.getElementById('grid');
  const btn       = document.getElementById('btn');
  const fileInput = document.getElementById('file');
  const dz        = document.getElementById('dz');
  const recBtn    = document.getElementById('recBtn');
  const audioB64  = document.getElementById('audio_b64');

  let mediaRec = null;
  let chunks   = [];

  /* —————— recording logic —————— */
  recBtn.addEventListener('click', async () => {
    if (!mediaRec) {
      // start
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRec = new MediaRecorder(stream);
        chunks   = [];
        mediaRec.ondataavailable = e => chunks.push(e.data);
        mediaRec.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          if (chunks.length === 0) {
            recBtn.textContent = '🎤 Record';
            mediaRec = null;
            return;
          }
          const reader = new FileReader();
          reader.onloadend = () => {
            audioB64.value = reader.result;
          };
          reader.readAsDataURL(blob);

          mediaRec = null;
          recBtn.textContent = '🎤 Re-record';
          recBtn.classList.add('success');
        };
        mediaRec.start();
        recBtn.textContent = '⏹️ Stop';
        recBtn.classList.remove('success');
      } catch (err) {
        alert('Could not access microphone.');
        console.error(err);
      }
    } else {
      // stop
      mediaRec.stop();
    }
  });

  /* —————— image picker logic —————— */
  const currentCount = () =>
    document.querySelectorAll('input[name=url]:checked').length;

  const updateBtn = () => {
    btn.disabled = currentCount() === 0;
    if (currentCount() === max) document.getElementById('f').submit();
  };

  const toggleBox = (box, img) => {
    if (!box.checked && currentCount() >= max) return;
    box.checked = !box.checked;
    img.classList.toggle('sel', box.checked);
    updateBtn();
  };

  grid.querySelectorAll('label').forEach(lbl => {
    const box = lbl.querySelector('input');
    const img = lbl.querySelector('img');
    lbl.addEventListener('click', () => toggleBox(box, img));
  });

  const previewFiles = (files) => {
    [...files].forEach(f => {
      if (currentCount() >= max) return;
      const url = URL.createObjectURL(f);
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type  = 'checkbox'; input.name = 'url'; input.hidden = true;
      const img   = document.createElement('img'); img.src = url;
      label.append(input, img);
      grid.prepend(label);
      toggleBox(input, img);
    });
    updateBtn();
  };

  const addNewFiles = (fileList) => {
    const roomLeft = max - currentCount();
    if (roomLeft <= 0) return;
    const newFiles = [...fileList].slice(0, roomLeft);
    const dt = new DataTransfer();
    [...fileInput.files].forEach(f => dt.items.add(f));
    newFiles.forEach(f => dt.items.add(f));
    fileInput.files = dt.files;
    previewFiles(newFiles);
  };

  // drop zone
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.style.borderColor = '#2196f3'; });
  dz.addEventListener('dragleave',   () => dz.style.borderColor = '#888');
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.style.borderColor = '#888';
    addNewFiles(e.dataTransfer.files);
  });

  // page-level drop
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop',     e => { e.preventDefault(); addNewFiles(e.dataTransfer.files); });

  // paste
  document.addEventListener('paste', e => {
    const imgs = [...e.clipboardData.items]
                   .filter(it => it.type.startsWith('image'))
                   .map(it => it.getAsFile());
    if (imgs.length) addNewFiles(imgs);
  });

  updateBtn();  // initialize
});