// Show/hide buttons for password inputs. The buttons are `hidden` in the
// markup, so without JavaScript the fields simply stay masked.
document.querySelectorAll('.password-toggle').forEach((button) => {
  const input = button.parentElement.querySelector('input');
  button.hidden = false;

  button.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(show));
    button.setAttribute('aria-label', show ? button.dataset.hide : button.dataset.show);
  });

  // Submit as a password field again, so the browser never files the
  // value under its plain-text form history.
  input.form.addEventListener('submit', () => {
    input.type = 'password';
  });
});
