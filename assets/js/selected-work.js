// The weekly Scholar job maintains PDF URLs. Curated summaries live in HTML.
fetch('data/publications.json', { cache: 'no-store' })
  .then(response => {
    if (!response.ok) throw new Error('Publication data unavailable');
    return response.json();
  })
  .then(data => {
    const byCitationId = new Map();
    for (const work of data.works) {
      if (!work.url) continue;
      const id = new URL(work.url, document.baseURI).searchParams.get('citation_for_view');
      if (id) byCitationId.set(id, work);
    }
    document.querySelectorAll('[data-paper-id]').forEach(actions => {
      const pdf = byCitationId.get(actions.dataset.paperId)?.pdf_url;
      if (!pdf?.startsWith('/pdf/')) return;
      const link = document.createElement('a');
      link.className = 'button primary';
      link.href = pdf;
      link.download = '';
      link.textContent = 'Download PDF ↓';
      actions.prepend(link);
    });
  })
  .catch(() => {});
