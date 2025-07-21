document.addEventListener('DOMContentLoaded', () => {
  const max       = 3;
  const grid      = document.getElementById('grid');
  const btn       = document.getElementById('btn');
  const fileInput = document.getElementById('file');
  const dz        = document.getElementById('dz');

  /* ---------- helpers -------------------------------------------- */
  const currentCount = () =>
    document.querySelectorAll('input[name=url]:checked').length;   // only picks

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

  /* ---------- click on remote thumbs ----------------------------- */
  grid.querySelectorAll('label').forEach(lbl => {
    const box = lbl.querySelector('input');
    const img = lbl.querySelector('img');
    lbl.addEventListener('click', () => toggleBox(box, img));
  });

  /* ---------- preview local files -------------------------------- */
  const previewFiles = (files) => {
    [...files].forEach(f => {
      if (currentCount() >= max) return;

      const url   = URL.createObjectURL(f);

      const label = document.createElement('label');

      const input = document.createElement('input');
      input.type  = 'checkbox';
      input.name  = 'url';
      input.hidden = true;

      const img   = document.createElement('img');
      img.src     = url;

      label.appendChild(input);
      label.appendChild(img);
      grid.prepend(label);

      toggleBox(input, img);
    });
    updateBtn();
  };

  /* ---------- add files from any source -------------------------- */
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

  /* ---------- dedicated drop-zone (keeps blue highlight) --------- */
  dz.addEventListener('dragover', e => {
    e.preventDefault();
    dz.style.borderColor = '#2196f3';
  });
  dz.addEventListener('dragleave', () => {
    dz.style.borderColor = '#888';
  });
  dz.addEventListener('drop', e => {
    e.preventDefault();
    dz.style.borderColor = '#888';
    addNewFiles(e.dataTransfer.files);
  });

  /* ---------- page-level drag-and-drop fallback ------------------ */
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop',     e => {
    e.preventDefault();                            // stop browser file-open
    addNewFiles(e.dataTransfer.files);             // ✓ works outside dz too
  });

  /* ---------- paste from clipboard ------------------------------ */
  document.addEventListener('paste', e => {
    const imgs = [...e.clipboardData.items]
                   .filter(it => it.type.startsWith('image'))
                   .map(it => it.getAsFile());
    if (imgs.length) addNewFiles(imgs);
  });

  updateBtn();   // initialise
});