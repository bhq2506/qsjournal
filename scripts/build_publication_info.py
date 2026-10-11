"""
Build data/publication_info.json (publication frequency, review speed) from
"Database Jurnal Scopus Gratis APC.xlsx" and match it to data/journals.json.

Usage:
    pip install openpyxl
    python scripts/build_publication_info.py "path/to/Database Jurnal Scopus Gratis APC.xlsx"

Matching: ISSN / eISSN first (closest title wins if several journals share an ISSN),
then exact normalised title, then title without "(MDPI)"-style suffixes.
When one journal appears in several subject sheets with different values,
each field takes the most common value (first one on a tie).
Unmatched rows are written to data/apc_unmatched.csv for review.

"""
import collections
import csv
import difflib
import json
import re
import sys
import unicodedata

import openpyxl

FIELDS = {
    "t": "Nama Jurnal", "rev": "Kecepatan Review", "rev_alt": "Timeline Review",
    "tp": "Estimasi dari Submit→Terbit", "freq": "Frekuensi Terbit", "apc": "Biaya Publikasi",
    "url": "URL", "issn": "ISSN/ E-ISSN", "model": "Model", "note": "Keterangan",
}
OUT_KEYS = ["apc", "model", "rev", "tp", "freq", "url", "note", "src"]
PUBLIC_KEYS = ["rev", "tp", "freq", "url", "note"]  # fee, model and fee source are not published


def clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


def nt(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def read_records(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    recs = []
    for ws in wb.worksheets[1:]:  # first sheet is the index
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        head = [clean(x) for x in rows[0]]
        ix = {k: (head.index(v) if v in head else None) for k, v in FIELDS.items()}
        if ix["t"] is None:
            continue
        for r in rows[1:]:
            if not r[ix["t"]]:
                continue
            g = lambda k: clean(r[ix[k]]) if ix[k] is not None else ""
            rec = {k: g(k) for k in FIELDS}
            rec["rev"] = rec["rev"] or rec.pop("rev_alt")
            rec.pop("rev_alt", None)
            rec["apc"] = re.sub(r"^[✓✔]\s*", "", rec["apc"])
            rec["sheet"] = ws.title
            recs.append(rec)
    return recs


def main(path):
    data = json.load(open("data/journals.json", encoding="utf-8"))
    J = data["journals"]
    by_issn, by_title = collections.defaultdict(set), collections.defaultdict(set)
    for i, j in enumerate(J):
        for x in (j[4], j[5]):
            if x:
                by_issn[x.upper()].add(i)
        by_title[nt(j[1])].add(i)

    matched, unmatched = collections.defaultdict(list), []
    for r in read_records(path):
        issns = [x.replace("-", "").upper() for x in re.findall(r"\d{4}-?\d{3}[\dXx]", r["issn"])]
        hits = set().union(*[by_issn.get(x, set()) for x in issns]) if issns else set()
        if len(hits) > 1:
            hits = {max(hits, key=lambda i: difflib.SequenceMatcher(None, nt(r["t"]), nt(J[i][1])).ratio())}
        if not hits:
            hits = by_title.get(nt(r["t"]), set())
        if not hits:
            hits = by_title.get(nt(re.sub(r"\(.*?\)|—.*$", "", r["t"])), set())
        if len(hits) == 1:
            matched[J[next(iter(hits))][0]].append(r)
        else:
            unmatched.append(r)

    out = {}
    for sid, rs in matched.items():
        # pick one whole record (most common combination) so fields stay consistent
        key = lambda r: tuple(r[k] for k in OUT_KEYS if k != "src")
        best = collections.Counter(key(r) for r in rs).most_common(1)[0][0]
        out[str(sid)] = list(best) + [""]

    # Fee and publishing-model information in the source workbook is unreliable
    # (e.g. every MDPI journal listed as free), so neither is published. Keep only
    # review speed, submit-to-publish time, frequency, journal URL and a cleaned note.
    fee_words = re.compile(r"gratis|apc|biaya|\$|waiver|free|diskon|default track|\bOA\b|murni|sejati|"
                           r"pembaca|subscription|hybrid|diamond|gold", re.I)
    public = {}
    for k, row in out.items():
        rec = dict(zip(OUT_KEYS, row))
        rec["note"] = "; ".join(p.strip() for p in rec["note"].split(";") if p.strip() and not fee_words.search(p))
        vals = [rec[f] for f in PUBLIC_KEYS]
        if any(vals[:3]):
            public[k] = vals
    out = public

    with open("data/publication_info.json", "w", encoding="utf-8") as f:
        json.dump({"fields": PUBLIC_KEYS, "source": "Database Jurnal Scopus Gratis APC", "journals": out},
                  f, ensure_ascii=False, separators=(",", ":"))
    with open("data/apc_unmatched.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sheet", "title", "issn", "model", "apc"])
        for r in unmatched:
            w.writerow([r["sheet"], r["t"], r["issn"], r["model"], r["apc"]])
    print(f"Matched {len(out)} journals; {len(unmatched)} rows unmatched -> data/apc_unmatched.csv")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
