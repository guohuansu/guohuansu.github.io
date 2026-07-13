# Guohuan Su — academic website

A responsive static academic website hosted by GitHub Pages.

## Publication updates

`scripts/update_publications.py` retrieves publication metadata from OpenAlex using ORCID `0000-0003-0091-9773`. GitHub Actions runs it every Monday and commits changes only when the metadata changed. It can also be run manually from the Actions tab.

Google Scholar and ResearchGate are linked as external profiles. They are intentionally not scraped directly because automated access is unstable and can trigger blocking.

## Local preview

Run a static web server from the repository root, for example `python -m http.server 8000`, then open `http://localhost:8000`.
