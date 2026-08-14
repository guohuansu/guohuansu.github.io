# Guohuan Su — academic website

A responsive static academic website hosted by GitHub Pages.

## Publication updates

`scripts/update_publications.py` retrieves the public publication list from Google Scholar profile `uqPekUQAAAAJ`. GitHub Actions runs it every Monday and commits changes only when the profile changed. It can also be run manually from the Actions tab. If Scholar temporarily blocks automated access, the script fails safely and preserves the existing site data.

Google Scholar is the authoritative publication source. ResearchGate and ORCID remain linked as complementary profiles.

## Adding downloadable PDFs

Place author manuscripts or other legally shareable full texts in `pdf/`. Use a filename close to the publication title, then run `python scripts/update_publications.py`. The updater attaches unambiguous matches and writes `data/missing-pdfs.md` for everything still missing. PDF files are never deleted by the updater.

For a broader open-access search, install `pypdf` and run `python scripts/discover_open_pdfs.py --download`. It checks OpenAlex, Unpaywall, and Crossref, accepts only explicitly reusable or repository-hosted manuscripts, validates the downloaded PDF against the title, and records every source in `data/open-pdf-sources.json`.

Vetted sources that need a direct URL or an existing local file are listed in `data/manual-open-pdf-sources.json`. A local source may use `local_filename` for the computer's Downloads folder or `local_path` for a path relative to the repository (absolute paths also work). Run `python scripts/import_open_pdf_sources.py` to import and validate them. The resulting audit is stored in `data/manual-open-pdf-audit.json`.

If the Scholar list is already current and only local PDFs changed, run `python scripts/rematch_local_pdfs.py` to rebuild download links without contacting Google Scholar.

## Local preview

Run a static web server from the repository root, for example `python -m http.server 8000`, then open `http://localhost:8000`.
