"""Refresh the publication list from Guohuan Su's public Google Scholar profile."""
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
from datetime import date

SCHOLAR_ID = "uqPekUQAAAAJ"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "publications.json"
PROFILE = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en&pagesize=100"


def clean(fragment):
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).replace("\xa0", " ").strip()


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

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(
    json.dumps(
        {
            "updated_at": date.today().isoformat(),
            "total_works": len(works),
            "source": "Google Scholar",
            "scholar_id": SCHOLAR_ID,
            "profile_url": PROFILE,
            "works": works,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Updated {len(works)} Google Scholar records in {OUT}")
