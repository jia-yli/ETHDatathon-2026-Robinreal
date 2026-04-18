"""Strip taxi routes (route_type=1500) + orphan trips/stop_times from the
Swiss GTFS so r5py can load it.

R5 (the routing engine behind r5py) rejects unknown extended GTFS route_types
with `IllegalArgumentException: Taxi route_type code not supported: 1500`.
The Swiss feed has 5 such routes (184 trips, 3.2k stop_times).

Run once after refreshing the GTFS dump:

    uv run python scripts/clean_gtfs.py

Reads:  ~/datathon_prep/gtfs/ch_gtfs_2026_latest.zip
Writes: ~/datathon_prep/gtfs/clean/ch_gtfs_2026_no_taxi.zip
"""

from __future__ import annotations

import csv
import sys
import tempfile
import zipfile
from pathlib import Path

SRC = Path.home() / "datathon_prep/gtfs/ch_gtfs_2026_latest.zip"
DST = Path.home() / "datathon_prep/gtfs/clean/ch_gtfs_2026_no_taxi.zip"

# Increase CSV field-size limit (stop_times.txt has wide rows).
csv.field_size_limit(sys.maxsize)


def main() -> None:
    DST.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with zipfile.ZipFile(SRC) as z:
            z.extractall(td)

        # 1. Drop taxi routes
        rows = list(csv.DictReader(open(td / "routes.txt", encoding="utf-8-sig")))
        bad_routes = {r["route_id"] for r in rows if r["route_type"] == "1500"}
        keep = [r for r in rows if r["route_type"] != "1500"]
        print(f"routes:     {len(rows)} -> {len(keep)} (dropped {len(bad_routes)} taxi)")
        with open(td / "routes.txt", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(keep)

        # 2. Drop trips referencing those routes
        rows = list(csv.DictReader(open(td / "trips.txt", encoding="utf-8-sig")))
        bad_trips = {r["trip_id"] for r in rows if r["route_id"] in bad_routes}
        keep = [r for r in rows if r["route_id"] not in bad_routes]
        print(f"trips:      {len(rows)} -> {len(keep)} (dropped {len(bad_trips)})")
        with open(td / "trips.txt", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(keep)

        # 3. Stream stop_times (file is ~1.3 GB) — drop orphan trip references.
        n_in = n_out = 0
        with open(td / "stop_times.txt", encoding="utf-8-sig") as fin, \
             open(td / "stop_times_clean.txt", "w", encoding="utf-8", newline="") as fout:
            r = csv.DictReader(fin)
            w = csv.DictWriter(fout, fieldnames=r.fieldnames)
            w.writeheader()
            for row in r:
                n_in += 1
                if row["trip_id"] not in bad_trips:
                    w.writerow(row)
                    n_out += 1
        (td / "stop_times.txt").unlink()
        (td / "stop_times_clean.txt").rename(td / "stop_times.txt")
        print(f"stop_times: {n_in} -> {n_out}")

        # 4. Repackage
        if DST.exists():
            DST.unlink()
        with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(td.glob("*.txt")):
                z.write(f, arcname=f.name)
        print(f"wrote {DST} ({DST.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
