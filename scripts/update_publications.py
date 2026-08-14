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
    "Mapping global biodiversity, profiling invasive species and developing a global index of biodiversity change based on taxonomic, functional and phylogenetic facets of …": "2020-mapping-global-biodiversity-doctoral-thesis.pdf",
    "Cartographie de la biodiversité mondiale, profilage des espèces envahissantes et élaboration d'un indice global du changement de la biodiversité basé sur les facettes …": "2020-mapping-global-biodiversity-doctoral-thesis.pdf",
    "栖息地环境对种群营养生态位的影响——以黄颡鱼为例": "2015-habitat-environment-yellow-catfish-trophic-niches.pdf",
    "鱼类形态特征与营养级位置之间关系初探": "2015-fish-morphology-trophic-position.pdf",
    "大坝截流前后金沙江观音岩水电站鱼类群落功能多样性的变化": "2015-guanyinyan-dam-fish-functional-diversity.pdf",
    "Functional diversity patterns reveal different elevations shaping Himalayan amphibian assemblages, highlighting the importance of morphologically extreme individuals": "2023-functional-diversity-himalayan-amphibian-assemblages.pdf",
    "Impacts of nonnative fishes on local contributions to beta diversity in United States freshwater fishes": "2025-impacts-of-nonnative-fishes-on-local-contributions-to-beta-diversity-in-united-states-freshwater-fishes.pdf",
    "Human impacts on fish biodiversity in the Yangtze River Basin: a multidimensional assessment using the Cumulative Change in Biodiversity Facets (CCBF) index": "2026-human-impacts-yangtze-fish-biodiversity-ccbf.pdf",
    "Differential controls of warming and phosphorus enrichment on CO2, CH4, and N2O emissions in shallow lake mesocosms": "2026-differential-controls-warming-phosphorus-greenhouse-gases.pdf",
    "Spatial Patterns and Determinants of Multidimensional Beta Diversity in the United States Freshwater Fishes": "2026-spatial-patterns-multidimensional-beta-diversity-us-fishes.pdf",
    "Phytoplankton dominance alters basal energy pathways and food web structure in eutrophic shallow lakes": "2026-phytoplankton-dominance-basal-energy-food-web.pdf",
    "Global diversity patterns and threats of cave fish": "2025-global-diversity-patterns-threats-cave-fish.pdf",
    "Global Patterns and Determinants of Multiple Facets of Freshwater Fishes Beta Diversity": "2025-global-patterns-determinants-freshwater-fish-beta-diversity.pdf",
    "Spatial distribution and introduction pathways of non-native freshwater fish species in China": "2024-spatial-distribution-introduction-pathways-nonnative-fish-china.pdf",
    "Intra-annual compositions and diversity variations of waterbird communities in China": "2024-intra-annual-waterbird-communities-china.pdf",
    "Assessment of greenhouse gases emissions and intensity from Chinese marine aquaculture in the past three decades": "2023-greenhouse-gas-emissions-chinese-marine-aquaculture.pdf",
    "Societal benefits and environmental performance of Chinese aquaculture": "2023-societal-benefits-environmental-performance-chinese-aquaculture.pdf",
    "Assessing sustainable performance of aquatic species using multiple footprints for comprehensive dietary advice": "2023-assessing-sustainable-performance-aquatic-species.pdf",
    "Current status of greenhouse gas emissions from aquaculture in China": "2022-current-status-greenhouse-gas-emissions-aquaculture-china.pdf",
    "Biogeographic Regionalization: Freshwater": "2022-biogeographic-regionalization-freshwater.pdf",
}
EXCLUDED_TITLES = {
    # This is the name of a repository page accidentally indexed as a Scholar
    # item, not one of Guohuan Su's publications.
    "Publications Repository-Helmholtz-Zentrum Dresden-Rossendorf",
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
    # Keep explicitly mapped files out of the fuzzy candidate pool. Otherwise a
    # similar title appearing earlier in Scholar can consume the reserved PDF.
    reserved = {PDF_DIR / name for name in PDF_OVERRIDES.values() if (PDF_DIR / name).exists()}
    unused = set(files) - reserved
    for publication in publications:
        override = PDF_OVERRIDES.get(publication["title"])
        if override and (PDF_DIR / override).exists():
            path = PDF_DIR / override
            publication["pdf_url"] = "/pdf/" + urllib.parse.quote(path.name)
            unused.discard(path)
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

# Undated Scholar entries are often incomplete working records. Keep the public
# website limited to publications with a confirmed year.
works = [work for work in works if work["year"] is not None]
works = [work for work in works if work["title"] not in EXCLUDED_TITLES]

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
