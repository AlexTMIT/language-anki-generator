document.addEventListener('DOMContentLoaded', () => {
  const MAX = 3;
  const grid      = document.getElementById('grid');
  const btn       = document.getElementById('btn');
  const fileInput = document.getElementById('file');
  const recBtn    = document.getElementById('recBtn');
  const audioB64  = document.getElementById('audio_b64');

  let mediaRec = null,
      chunks   = [];

  /* —————— Recording logic —————— */
  recBtn.addEventListener('click', async () => {
    if (!mediaRec) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRec = new MediaRecorder(stream);
        chunks   = [];
        mediaRec.ondataavailable = e => chunks.push(e.data);
        mediaRec.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          if (!chunks.length) {
            recBtn.textContent = '🎤 Record';
            mediaRec = null;
            return;
          }
          const reader = new FileReader();
          reader.onloadend = () => audioB64.value = reader.result;
          reader.readAsDataURL(blob);

          recBtn.textContent = '🎤 Re-record';
          recBtn.classList.add('success');
          mediaRec = null;
        };
        mediaRec.start();
        recBtn.textContent = '⏹️ Stop';
        recBtn.classList.remove('success');
      } catch (err) {
        alert('Could not access microphone.');
        console.error(err);
      }
    } else {
      mediaRec.stop();
    }
  });

  /* —————— Image picker logic —————— */
  const currentCount = () =>
    document.querySelectorAll('input[name="url"]:checked').length;

  const updateBtn = () => {
    btn.disabled = currentCount() === 0;
  };

  const toggleSelection = (checkbox, img) => {
    if (!checkbox.checked && currentCount() >= MAX) return;
    checkbox.checked = !checkbox.checked;
    img.classList.toggle('sel', checkbox.checked);
    updateBtn();
  };

  // click-to-select
  grid.querySelectorAll('label').forEach(label => {
    const cb  = label.querySelector('input');
    const img = label.querySelector('img');
    label.addEventListener('click', () => toggleSelection(cb, img));
  });

  // preview newly dropped/pasted files
  const previewFiles = files => {
    [...files].slice(0, MAX - currentCount()).forEach(file => {
      const url   = URL.createObjectURL(file);
      const label = document.createElement('label');
      const cb    = document.createElement('input');
      const img   = document.createElement('img');
      cb.type  = 'checkbox';
      cb.name  = 'url';
      cb.hidden = true;
      img.src  = url;
      img.alt  = '';
      label.append(cb, img);
      grid.prepend(label);
      toggleSelection(cb, img);
    });
  };

  // add files to the hidden <input>
  const addNewFiles = fileList => {
    const dt = new DataTransfer();
    // keep existing
    [...fileInput.files].forEach(f => dt.items.add(f));
    // add new (up to room)
    [...fileList].slice(0, MAX - currentCount()).forEach(f => dt.items.add(f));
    fileInput.files = dt.files;
    previewFiles(fileList);
  };

  // global drag/drop
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => {
    e.preventDefault();
    if (e.dataTransfer.files.length) {
      addNewFiles(e.dataTransfer.files);
    }
  });

  // paste anywhere
  document.addEventListener('paste', e => {
    const imgs = [...e.clipboardData.items]
      .filter(it => it.type.startsWith('image/'))
      .map(it => it.getAsFile());
    if (imgs.length) addNewFiles(imgs);
  });

  updateBtn(); // initial
});