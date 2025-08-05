// static/js/flashcards.js
document.addEventListener('DOMContentLoaded', () => {
  const deckSelect  = document.querySelector('select[name="deck"]');
  const langSelect  = document.querySelector('select[name="lang"]');
  const textarea    = document.querySelector('textarea[name="blob"]');
  const continueBtn = document.querySelector('button[type="submit"]');

  function updateContinue() {
    // disable only when nothing at all is filled in
    const allEmpty = !deckSelect.value
                  && !langSelect.value
                  && textarea.value.trim() === '';
    continueBtn.disabled = allEmpty;
  }

  // run on load to pick up the default state
  updateContinue();

  // listen for both change (for selects) and input (for textarea)
  deckSelect.addEventListener('change', updateContinue);
  deckSelect.addEventListener('input',  updateContinue);
  langSelect.addEventListener('change', updateContinue);
  langSelect.addEventListener('input',  updateContinue);
  textarea.addEventListener('input',    updateContinue);
});