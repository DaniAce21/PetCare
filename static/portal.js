'use strict';
document.addEventListener('submit', event => {
  const form = event.target;
  form.setAttribute('aria-busy', 'true');
  for (const button of form.querySelectorAll('button[type="submit"], button:not([type])')) {
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.textContent = 'Procesando…';
  }
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[aria-busy]').forEach(form => form.removeAttribute('aria-busy'));
  document.querySelectorAll('button[data-original-text]').forEach(button => {
    button.disabled = false;
    button.textContent = button.dataset.originalText;
    delete button.dataset.originalText;
  });
});
