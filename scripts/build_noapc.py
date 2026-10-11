"""
Rebuild data/noapc.json from DOAJ (Directory of Open Access Journals).

Usage (run where doaj.org is reachable):
    python scripts/build_noapc.py

For every ISSN/eISSN in data/journals.json, queries the DOAJ public search API in
batches and keeps the journals whose DOAJ record says bibjson.apc.has_apc == false.
Journals not in DOAJ, or recorded with an APC, are not marked No APC.
Takes ~5 minutes (about 1,100 requests, throttled).
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date

API = "https://doaj.org/api/search/journals/"
BATCH = 40


def fmt(issn):
    return f"{issn[:4]}-{issn[4:]}" if issn and len(issn) == 8 else ""


def search(issns):
    q = "issn:(" + " OR ".join(f'"{i}"' for i in issns) + ")"
    url = API + urllib.parse.quote(q) + "?pageSize=100"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qsjournal data refresh"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("results", [])
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"DOAJ query failed for batch starting {issns[0]}")


def main():
    J = json.load(open("data/journals.json", encoding="utf-8"))["journals"]
    issn_to_ids = {}
    for j in J:
        for x in (j[4], j[5]):
            f = fmt(x)
            if f:
                issn_to_ids.setdefault(f, set()).add(j[0])
    issns = list(issn_to_ids)
    status = {}  # scopus id -> has_apc
    for n in range(0, len(issns), BATCH):
        for rec in search(issns[n:n + BATCH]):
            bj = rec.get("bibjson", {})
            has_apc = (bj.get("apc") or {}).get("has_apc")
            for s in (bj.get("pissn"), bj.get("eissn")):
                for sid in issn_to_ids.get(s, ()):
                    status[sid] = has_apc
        time.sleep(0.25)
    ids = sorted(sid for sid, has in status.items() if has is False)
    data = {"source": "https://doaj.org", "retrieved": date.today().isoformat(),
            "note": "Scopus source IDs of journals that DOAJ records as charging no APC "
                    "(bibjson.apc.has_apc = false), matched by ISSN/eISSN",
            "ids": ids}
    with open("data/noapc.json", "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{len(status)} journals found in DOAJ; {len(ids)} without APC")


if __name__ == "__main__":
    main()
