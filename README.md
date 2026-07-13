# Guohuan Su — academic website

A responsive static academic website hosted by GitHub Pages.

## Publication updates

`scripts/update_publications.py` retrieves the public publication list from Google Scholar profile `uqPekUQAAAAJ`. GitHub Actions runs it every Monday and commits changes only when the profile changed. It can also be run manually from the Actions tab. If Scholar temporarily blocks automated access, the script fails safely and preserves the existing site data.

Google Scholar is the authoritative publication source. ResearchGate and ORCID remain linked as complementary profiles.

## Local preview

Run a static web server from the repository root, for example `python -m http.server 8000`, then open `http://localhost:8000`.
