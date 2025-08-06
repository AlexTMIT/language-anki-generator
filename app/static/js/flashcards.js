// static/js/flashcards.js
document.addEventListener('DOMContentLoaded', () => {
  const deckSelect  = document.querySelector('select[name="deck"]');
  const langSelect  = document.querySelector('select[name="lang"]');
  const textarea    = document.querySelector('textarea[name="blob"]');
  const continueBtn = document.querySelector('button[type="submit"]');
  const form        = document.querySelector('form.flashcard-form');

  // 1) Enable/disable Continue
  function updateContinue() {
    const allEmpty = !deckSelect.value
                  && !langSelect.value
                  && textarea.value.trim() === '';
    continueBtn.disabled = allEmpty;
  }
  [deckSelect, langSelect].forEach(el => {
    el.addEventListener('change', updateContinue);
    el.addEventListener('input',  updateContinue);
  });
  textarea.addEventListener('input', updateContinue);
  updateContinue();  // initial

  // 2) On submit, hijack and POST via fetch → redirect to loader page
  form.addEventListener('submit', async e => {
  e.preventDefault();
  const url  = form.action + location.search;          // keep your sid
  const resp = await fetch(url,        {method:'POST', body:new FormData(form)});
  const data = await resp.json();
  if (data.next_url) window.location = data.next_url;  
});

  
});