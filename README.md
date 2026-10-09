# Guohuan Su — academic website

A responsive static academic website hosted by GitHub Pages.

## Publication updates

`scripts/update_publications.py` retrieves the public publication list from Google Scholar profile `uqPekUQAAAAJ`. GitHub Actions runs every Monday at 02:17 UTC (10:17 China time; GitHub may delay scheduled jobs), commits refreshed data, and directly calls the Pages deployment workflow. This runs in the cloud even when the owner's computer is off.

Cloud updates require a SerpApi account and a repository Actions secret named `SERPAPI_API_KEY`. Add the API key at Settings → Secrets and variables → Actions → New repository secret. Never put the key in source files. The updater uses the Google Scholar Author API with 100 articles per page; weekly requests are generally within the service's free quota, subject to its current plan. Without a key, the cloud job stops with a clear setup message. Local runs without a key can still fetch Scholar directly.

Set Settings → Pages → Build and deployment → Source to **GitHub Actions**. `deploy-pages.yml` publishes the static site both after ordinary pushes and after a successful scheduled update. After adding the secret, use Actions → Update publications → Run workflow to verify the complete update and deployment. A failed fetch preserves the existing data and deployed website.

Google Scholar is the authoritative publication source. ResearchGate and ORCID remain linked as complementary profiles.

## Adding downloadable PDFs

Place author manuscripts or other legally shareable full texts in `pdf/`. Use a filename close to the publication title, then run `python scripts/update_publications.py`. The updater attaches unambiguous matches and writes `data/missing-pdfs.md` for everything still missing. PDF files are never deleted by the updater.

For a broader open-access search, install `pypdf` and run `python scripts/discover_open_pdfs.py --download`. It checks OpenAlex, Unpaywall, and Crossref, accepts only explicitly reusable or repository-hosted manuscripts, validates the downloaded PDF against the title, and records every source in `data/open-pdf-sources.json`.

Vetted sources that need a direct URL or an existing local file are listed in `data/manual-open-pdf-sources.json`. A local source may use `local_filename` for the computer's Downloads folder or `local_path` for a path relative to the repository (absolute paths also work). Run `python scripts/import_open_pdf_sources.py` to import and validate them. The resulting audit is stored in `data/manual-open-pdf-audit.json`.

If the Scholar list is already current and only local PDFs changed, run `python scripts/rematch_local_pdfs.py` to rebuild download links without contacting Google Scholar.

Corresponding-author labels are maintained in `data/publication-author-metadata.json`. Both the online updater and offline rematcher attach them to the Scholar records.

## Local preview

Run a static web server from the repository root, for example `python -m http.server 8000`, then open `http://localhost:8000`.
