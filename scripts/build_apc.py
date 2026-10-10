"""
Build data/apc.json (publication fee, frequency, review speed) from
"Database Jurnal Scopus Gratis APC.xlsx" and match it to data/journals.json.

Usage:
    pip install openpyxl
    python scripts/build_apc.py "path/to/Database Jurnal Scopus Gratis APC.xlsx"

Matching: ISSN / eISSN first (closest title wins if several journals share an ISSN),
then exact normalised title, then title without "(MDPI)"-style suffixes.
When one journal appears in several subject sheets with different values,
each field takes the most common value (first one on a tie).
Unmatched rows are written to data/apc_unmatched.csv for review.

Corrections: data/overrides/mdpi_apc.csv (MDPI's official APC list, from
https://www.mdpi.com/apc) overrides the workbook for every MDPI journal. The workbook
wrongly lists MDPI journals as Diamond OA / free; MDPI is fully Gold OA with an APC.
MDPI journals missing from the workbook also get their APC from this list.
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
MDPI_ALIASES = {"c journal of carbon research": "c", "oral health diseases therapies and technologies": "oral"}


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

    # --- MDPI correction from the publisher's official APC list ---
    mdpi = {}
    with open("data/overrides/mdpi_apc.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mdpi[nt(row["journal"])] = (row["basic_apc"], row["retrieved"])
    fixed = added = 0
    for j in J:
        if "mdpi" not in j[2].lower() and "multidisciplinary digital" not in j[2].lower():
            continue
        t = nt(re.sub(r"\s*\([^)]*\)$|\s*-\s*MDPI$", "", j[1]))
        t = MDPI_ALIASES.get(t, t)
        if t not in mdpi or mdpi[t][0].lower().startswith("see"):
            continue
        apc, when = mdpi[t]
        if apc.lower() == "free":
            apc_txt, model = "Gratis (APC ditiadakan MDPI)", "Diamond OA"
        else:
            apc_txt, model = f"{apc} (Gold OA, dibayar penulis setelah diterima)", "Gold OA"
        src = f"mdpi.com/apc, {when}"
        row = out.get(str(j[0]))
        if row:
            note = re.sub(r"Diamond OA;?\s*", "", row[6]).strip("; ")
            out[str(j[0])] = [apc_txt, model, row[2], row[3], row[4], row[5], note, src]
            fixed += 1
        else:
            out[str(j[0])] = [apc_txt, model, "", "", "", "", "", src]
            added += 1
    print(f"MDPI: corrected {fixed} workbook rows, added APC for {added} more MDPI journals")

    with open("data/apc.json", "w", encoding="utf-8") as f:
        json.dump({"fields": OUT_KEYS, "source": "Database Jurnal Scopus Gratis APC", "journals": out},
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
