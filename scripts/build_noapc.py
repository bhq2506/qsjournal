"""
Rebuild data/noapc.json from https://noapc.com.

Usage (run where noapc.com is reachable):
    python scripts/build_noapc.py

How it works: reads the subject pages linked from the noapc.com home page, collects
every journal row (title, publisher, ISSN), and matches them to data/journals.json by
ISSN/eISSN, then by exact normalised title for rows without an ISSN.
noapc.com has no export; it claims ~2,600 journals but its pages list ~1,700.
"""
import json
import re
import unicodedata
import urllib.request
from datetime import date
from html.parser import HTMLParser

HOME = "https://noapc.com/"
SKIP = ("about", "contact", "privacy")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (qsjournal data refresh)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


class Tables(HTMLParser):
    """Collects all <table> rows as lists of cell text, plus all <a href>."""

    def __init__(self):
        super().__init__()
        self.rows, self.links, self._row, self._cell = [], [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def nt(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def scrape():
    home = Tables()
    home.feed(get(HOME))
    pages = sorted({u for u in home.links
                    if re.fullmatch(r"https://noapc\.com/[a-z0-9-]+/?", u or "") and not any(k in u for k in SKIP)})
    out = []
    for url in pages:
        t = Tables()
        t.feed(get(url))
        head = None
        for row in t.rows:
            low = [c.lower() for c in row]
            if any("title" in c for c in low) and any("issn" in c for c in low):
                head = {k: next(i for i, c in enumerate(low) if k in c) for k in ("title", "issn")}
                continue
            if head and len(row) > max(head.values()) and row[head["title"]]:
                out.append((row[head["title"]], row[head["issn"]]))
    return out


def main():
    rows = scrape()
    J = json.load(open("data/journals.json", encoding="utf-8"))["journals"]
    by_issn, by_title = {}, {}
    for j in J:
        for x in (j[4], j[5]):
            if x:
                by_issn.setdefault(x.upper(), set()).add(j[0])
        by_title.setdefault(nt(j[1]), set()).add(j[0])
    ids, missed = set(), 0
    for title, issn in rows:
        codes = [x.replace("-", "").upper() for x in re.findall(r"\d{4}-?\d{3}[\dXx]", issn)]
        hit = set().union(*[by_issn.get(c, set()) for c in codes]) if codes else by_title.get(nt(title), set())
        if hit:
            ids |= hit
        else:
            missed += 1
    data = {"source": HOME.rstrip("/"), "retrieved": date.today().isoformat(),
            "note": "Scopus source IDs of journals listed on noapc.com (no article processing charge), "
                    "matched by ISSN/eISSN, then title",
            "ids": sorted(ids)}
    with open("data/noapc.json", "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{len(rows)} rows scraped, {len(ids)} journals matched, {missed} rows not in data/journals.json")


if __name__ == "__main__":
    main()
