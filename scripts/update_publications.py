"""Refresh publication metadata from OpenAlex using Guohuan Su's ORCID."""
import json
import pathlib
import urllib.parse
import urllib.request
from datetime import date

ORCID = "0000-0003-0091-9773"
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "publications.json"

def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "guohuansu.github.io/1.0 (mailto:suguohuan@ihb.ac.cn)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

author = get_json(f"https://api.openalex.org/authors/https://orcid.org/{ORCID}")
params = urllib.parse.urlencode({"filter": f"author.id:{author['id'].rsplit('/',1)[-1]}", "sort": "publication_date:desc", "per-page": 200})
payload = get_json(f"https://api.openalex.org/works?{params}")
works = []
for item in payload["results"]:
    source = ((item.get("primary_location") or {}).get("source") or {}).get("display_name", "")
    authors = ", ".join(a["author"]["display_name"] for a in item.get("authorships", []))
    url = item.get("doi") or (item.get("primary_location") or {}).get("landing_page_url") or item.get("id")
    works.append({"title": item["title"], "year": item.get("publication_year"), "venue": source, "authors": authors, "url": url, "cited_by_count": item.get("cited_by_count", 0), "openalex_id": item["id"]})
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps({"updated_at": date.today().isoformat(), "total_works": len(works), "openalex_author_id": author["id"], "works": works}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated {len(works)} works in {OUT}")
