const list = document.querySelector('#publication-list');
let works = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  })[character]);
}

function normalizeAuthor(name) {
  return String(name ?? '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z\u3400-\u9fff]/g, '')
    .toLowerCase();
}

function isSiteOwner(name) {
  return ['gsu', 'ghsu', 'guohuansu', '苏国欢'].includes(normalizeAuthor(name));
}

function formatAuthors(authors, correspondingAuthors = []) {
  const corresponding = new Set(correspondingAuthors.map(normalizeAuthor));
  return String(authors ?? '').split(/([,，]\s*)/).map(part => {
    if (/^[,，]/.test(part)) return escapeHtml(part);
    const name = part.trim();
    if (!name) return '';
    const escapedName = escapeHtml(name);
    const displayedName = isSiteOwner(name)
      ? `<strong class="publication-author-self">${escapedName}</strong>`
      : escapedName;
    const mark = corresponding.has(normalizeAuthor(name))
      ? '<sup class="corresponding-mark" aria-label="corresponding author">*</sup>'
      : '';
    return displayedName + mark;
  }).join('');
}

function authorNames(authors) {
  return String(authors ?? '')
    .split(/[,，]/)
    .map(name => name.trim())
    .filter(name => name && name !== '...');
}

function isFirstOrCorrespondingAuthor(work) {
  const firstAuthor = authorNames(work.authors)[0] || '';
  return isSiteOwner(firstAuthor) ||
    (work.corresponding_authors || []).some(isSiteOwner);
}

function renderPublication(work) {
  return `
    <article class="publication">
      <span class="publication-year">${escapeHtml(work.year || '—')}</span>
      <div>
        <h3>${escapeHtml(work.title)}</h3>
        <p>${formatAuthors(work.authors, work.corresponding_authors)}${work.venue ? ` · <em>${escapeHtml(work.venue)}</em>` : ''}${work.cited_by_count != null ? ` · ${escapeHtml(work.cited_by_count)} citations in Google Scholar` : ''}</p>
      </div>
      <div class="publication-links">
        ${work.pdf_url ? `<a class="pdf-link" href="${escapeHtml(work.pdf_url)}" download>PDF ↓</a>` : ''}
        ${work.url ? `<a href="${escapeHtml(work.url)}" target="_blank" rel="noopener">Scholar ↗</a>` : ''}
      </div>
    </article>
  `;
}

function renderGroup(title, publications) {
  if (!publications.length) return '';
  return `
    <section class="publication-group">
      <header class="publication-group-header">
        <h3>${escapeHtml(title)}</h3>
        <span>${publications.length} publication${publications.length === 1 ? '' : 's'}</span>
      </header>
      ${publications.map(renderPublication).join('')}
    </section>
  `;
}

function render() {
  const query = document.querySelector('#publication-search').value.toLowerCase();
  const year = document.querySelector('#year-filter').value;
  const shown = works.filter(work =>
    (year === 'all' || String(work.year) === year) &&
    `${work.title} ${work.venue} ${work.year}`.toLowerCase().includes(query)
  );

  const leadWorks = shown.filter(isFirstOrCorrespondingAuthor);
  const otherWorks = shown.filter(work => !isFirstOrCorrespondingAuthor(work));

  list.innerHTML = shown.length
    ? renderGroup('First- or corresponding-author publications', leadWorks) + renderGroup('Other publications', otherWorks)
    : '<p>No matching publications found.</p>';
}

fetch('data/publications.json', { cache: 'no-store' }).then(response => response.json()).then(data => {
  works = data.works;
  document.querySelector('#publication-count').textContent = data.total_works;
  document.querySelector('#last-updated').textContent = data.updated_at;
  const years = [...new Set(works.map(work => work.year).filter(Boolean))].sort((a, b) => b - a);
  document.querySelector('#year-filter').insertAdjacentHTML('beforeend', years.map(year => `<option>${year}</option>`).join(''));
  render();
}).catch(() => list.innerHTML = '<p>Publication data is temporarily unavailable. Please visit Google Scholar or ResearchGate.</p>');

document.querySelector('#publication-search').addEventListener('input', render);
document.querySelector('#year-filter').addEventListener('change', render);
document.querySelector('#current-year').textContent = new Date().getFullYear();
const button = document.querySelector('.menu-button');
