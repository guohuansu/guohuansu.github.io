# Guohuan Su — academic website

A responsive static academic website hosted by GitHub Pages.

## Publication updates

`scripts/update_publications.py` retrieves the public publication list from Google Scholar profile `uqPekUQAAAAJ`. GitHub Actions runs every Monday at 02:17 UTC (10:17 China time; GitHub may delay scheduled jobs), commits refreshed data, and directly calls the Pages deployment workflow. This runs in the cloud even when the owner's computer is off.

Cloud updates require a SerpApi account and a repository Actions secret named `SERPAPI_API_KEY`. Add the API key at Settings → Secrets and variables → Actions → New repository secret. Never put the key in source files. The updater uses the Google Scholar Author API with 100 articles per page; weekly requests are generally within the service's free quota, subject to its current plan. Without a key, the cloud job stops with a clear setup message. Local runs without a key can still fetch Scholar directly.

Set Settings → Pages → Build and deployment → Source to **GitHub Actions**. `deploy-pages.yml` publishes the static site both after ordinary pushes and after a successful scheduled update. After adding the secret, use Actions → Update publications → Run workflow to verify the complete update and deployment. A failed fetch preserves the existing data and deployed website.

Google Scholar is the authoritative publication source. ResearchGate and ORCID remain linked as complementary profiles.

## Adding downloadable PDFs

PDF filenames use `Year_FirstSurname et al_Full title_Journal.pdf`, for example `2021_Su et al_Human impacts on global freshwater fish biodiversity_Science.pdf`. Single-author documents omit `et al`. Journal names exclude volume/issue/page numbers; characters invalid on Windows (such as `:`) become ` - `. Extremely long titles are shortened only to fit the 240-byte filename limit. New downloads use the same naming rule automatically.

`data/pdf-library.json` records every file's metadata, old filename and SHA-256 checksum. It also retains a byte-identical duplicate with `(duplicate)` in its name; nothing was deleted. The thesis, book chapter and preprints stay in the local library but remain excluded from the journal publication list. Exact inventory matches are resolved before fuzzy matching, and corrections cannot reuse the original article's file.

To preview a future naming migration run `python scripts/standardize_pdf_names.py`; use `--apply` only after reviewing its plan. It checks directory boundaries/collisions, updates tracked links and source references, and verifies that file contents did not change.

Place author manuscripts or other legally shareable full texts in `pdf/`. Use a filename close to the publication title, then run `python scripts/update_publications.py`. The updater attaches unambiguous matches and writes `data/missing-pdfs.md` for everything still missing. PDF files are never deleted by the updater.

For a broader open-access search, install `pypdf` and run `python scripts/discover_open_pdfs.py --download`. It checks OpenAlex, Unpaywall, and Crossref, accepts only explicitly reusable or repository-hosted manuscripts, validates the downloaded PDF against the title, and records every source in `data/open-pdf-sources.json`.

The weekly cloud update runs this full-text search automatically for every journal paper without a local PDF, retries missing PDFs on later weeks, rematches the downloaded files, and commits both the files and links before deployment. Cloud downloads become local files after pulling the repository with Git or GitHub Desktop. A paper remains listed with its Scholar link when no suitable PDF is found or the host rejects the download.

Vetted sources that need a direct URL or an existing local file are listed in `data/manual-open-pdf-sources.json`. A local source may use `local_filename` for the computer's Downloads folder or `local_path` for a path relative to the repository (absolute paths also work). Run `python scripts/import_open_pdf_sources.py` to import and validate them. The resulting audit is stored in `data/manual-open-pdf-audit.json`.

If the Scholar list is already current and only local PDFs changed, run `python scripts/rematch_local_pdfs.py` to rebuild download links without contacting Google Scholar.

Corresponding-author labels are maintained in `data/publication-author-metadata.json`. Both the online updater and offline rematcher attach them to the Scholar records.

Google Scholar does not supply corresponding-author roles. Verify new papers against the publisher page or full-text PDF before adding those roles; an absent metadata entry means unreviewed, not evidence that the paper has no corresponding author. `data/publication-author-overrides.json` restores verified complete author lists when Scholar truncates them, so a corresponding author at the end of the list remains visible. Both updater scripts preserve these overrides.

## Local preview

Run a static web server from the repository root, for example `python -m http.server 8000`, then open `http://localhost:8000`.
