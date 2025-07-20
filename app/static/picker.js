// picker.js – handles click-to-select, drag-drop, and paste
document.addEventListener('DOMContentLoaded', () => {
  const max = 3;
  const grid      = document.getElementById('grid');
  const btn       = document.getElementById('btn');
  const fileInput = document.getElementById('file');
  const dz        = document.getElementById('dz');

  const currentCount = () =>
    document.querySelectorAll('input[name=url]:checked').length +
    fileInput.files.length;

  const toggleBox = (box, img) => {
    if (!box.checked && currentCount() >= max) return;
    box.checked = !box.checked;
    img.classList.toggle('sel', box.checked);
    btn.disabled = currentCount() === 0;
    if (currentCount() === max) document.getElementById('f').submit();
  };

  // click on thumbs
  grid.querySelectorAll('label').forEach(lbl => {
    const box = lbl.querySelector('input');
    const img = lbl.querySelector('img');
    lbl.onclick = () => toggleBox(box, img);
  });

  // drag-drop local files
  dz.ondragover  = e => { e.preventDefault(); dz.style.borderColor = '#2196f3'; };
  dz.ondragleave = () => { dz.style.borderColor = '#888'; };
  dz.ondrop      = e => {
    e.preventDefault(); dz.style.borderColor = '#888';
    const dt = new DataTransfer();
    [...fileInput.files].forEach(f => dt.items.add(f));        // keep existing
    [...e.dataTransfer.files].slice(0, max - currentCount())
                             .forEach(f => dt.items.add(f));
    fileInput.files = dt.files;
    previewFiles(dt.files);
  };

  // paste image from clipboard
  document.addEventListener('paste', e => {
    for (const item of e.clipboardData.items) {
      if (item.type.startsWith('image') && currentCount() < max) {
        const file = item.getAsFile();
        const dt   = new DataTransfer();
        [...fileInput.files].forEach(f => dt.items.add(f));
        dt.items.add(file);
        fileInput.files = dt.files;
        previewFiles([file]);
      }
    }
  });

  // tiny preview for dropped / pasted files
  const previewFiles = files => {
    [...files].forEach(f => {
      const url = URL.createObjectURL(f);
      const img = document.createElement('img');
      img.src   = url;
      img.style.border = '3px solid #2196f3';
      grid.prepend(img);                  // visual feedback
    });
    btn.disabled = currentCount() === 0;
    if (currentCount() === max) document.getElementById('f').submit();
  };
});