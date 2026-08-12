"""Refresh the publication list from Guohuan Su's public Google Scholar profile."""
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
import unicodedata
from datetime import date
from difflib import SequenceMatcher

SCHOLAR_ID = "uqPekUQAAAAJ"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "publications.json"
PROFILE = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en&pagesize=100"
PDF_DIR = ROOT / "pdf"
PDF_OVERRIDES = {
    "Species invasiveness and community invasibility of North American freshwater fish fauna revealed via trait-based analysis": "Su 2023 Species-invasiveness and community.pdf",
}


def clean(fragment):
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).replace("\xa0", " ").strip()


def normalize_title(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(19|20)\d{2}\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def match_pdfs(publications):
    files = sorted(PDF_DIR.glob("*.pdf")) if PDF_DIR.exists() else []
    unused = set(files)
    for publication in publications:
        override = PDF_OVERRIDES.get(publication["title"])
        if override and PDF_DIR / override in unused:
            path = PDF_DIR / override
            publication["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.remove(path)
            continue
        title = normalize_title(publication["title"])
        ranked = sorted(((SequenceMatcher(None, title, normalize_title(path.stem)).ratio(), path) for path in unused), key=lambda item: item[0], reverse=True)
        if ranked and ranked[0][0] >= 0.56 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.08):
            path = ranked[0][1]
            publication["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.remove(path)
        else:
            publication["pdf_url"] = None
    return files, unused


request = urllib.request.Request(
    PROFILE,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    },
)
with urllib.request.urlopen(request, timeout=45) as response:
    page = response.read().decode("utf-8")

rows = re.findall(r'<tr class="gsc_a_tr">(.*?)</tr>', page, re.S)
if not rows:
    raise RuntimeError("Google Scholar returned no publication rows; existing data was preserved")

works = []
for row in rows:
    title_match = re.search(r'<a href="([^"]+)" class="gsc_a_at">(.*?)</a>', row, re.S)
    gray = re.findall(r'<div class="gs_gray">(.*?)</div>', row, re.S)
    year_match = re.search(r'<span class="gsc_a_h gsc_a_hc gs_ibl">(.*?)</span>', row, re.S)
    cited_match = re.search(r'class="gsc_a_ac[^>]*>(.*?)</a>', row, re.S)
    if not title_match:
        continue
    citation_text = clean(cited_match.group(1)) if cited_match else ""
    works.append(
        {
            "title": clean(title_match.group(2)),
            "year": int(clean(year_match.group(1))) if year_match and clean(year_match.group(1)).isdigit() else None,
            "venue": clean(gray[1]) if len(gray) > 1 else "",
            "authors": clean(gray[0]) if gray else "",
            "url": urllib.parse.urljoin("https://scholar.google.com", html.unescape(title_match.group(1))),
            "cited_by_count": int(citation_text) if citation_text.isdigit() else 0,
        }
    )

if not works:
    raise RuntimeError("Google Scholar rows could not be parsed; existing data was preserved")

# Scholar profiles default to citation-count order; the website is easier to scan
# when the newest work appears first while retaining citation order within a year.
works.sort(key=lambda work: (work["year"] or 0, work["cited_by_count"]), reverse=True)
pdf_files, unmatched_pdfs = match_pdfs(works)

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(
    json.dumps(
        {
            "updated_at": date.today().isoformat(),
            "total_works": len(works),
            "source": "Google Scholar",
            "scholar_id": SCHOLAR_ID,
            "profile_url": PROFILE,
            "pdf_count": sum(bool(work["pdf_url"]) for work in works),
            "works": works,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
missing = ROOT / "data" / "missing-pdfs.md"
missing_lines = ["# Publications without a local PDF", "", f"Generated {date.today().isoformat()}. Add legally shareable files to `pdf/` and rerun the updater.", ""] + [f"- {work['year'] or 'n.d.'} — {work['title']}" for work in works if not work["pdf_url"]]
if unmatched_pdfs:
    missing_lines += ["", "## Unmatched PDF files", ""] + [f"- {path.name}" for path in sorted(unmatched_pdfs)]
missing.write_text("\n".join(missing_lines) + "\n", encoding="utf-8")
print(f"Updated {len(works)} Scholar records; matched {sum(bool(w['pdf_url']) for w in works)}/{len(pdf_files)} PDFs")
