document.querySelectorAll('[data-current-year]').forEach(year => {
  year.textContent = new Date().getFullYear();
});
