#!/usr/bin/env python3
"""Validate the CSV master register before GitHub Pages deployment."""
from pathlib import Path
import csv, re, sys

ROOT=Path(__file__).resolve().parent
FILE=ROOT/"data"/"boreholes.csv"
REQUIRED=["Borehole number","Location","Latitude","Longitude","Division","Province"]

def coord(v):
    try: return float(re.sub(r"\s+","",str(v).strip()).replace("°","").replace(",",""))
    except: return None

def main():
    with FILE.open("r",encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames: raise SystemExit("FAIL: missing CSV headers")
        missing=[x for x in REQUIRED if x not in reader.fieldnames]
        if missing: raise SystemExit("FAIL: missing columns: "+", ".join(missing))
        rows=list(reader)
    if not rows: raise SystemExit("FAIL: register has no data rows")
    ids=[r.get("Borehole number","").strip() for r in rows if r.get("Borehole number","").strip()]
    duplicates=sorted({x for x in ids if ids.count(x)>1})
    if duplicates: raise SystemExit("FAIL: duplicate borehole numbers: "+", ".join(duplicates))
    print(f"PASS: {len(rows)} rows; required columns present; borehole IDs unique.")
    issues=[]
    for i,r in enumerate(rows, start=2):
        lat,lon=coord(r.get("Latitude","")),coord(r.get("Longitude",""))
        if not r.get("Borehole number","").strip(): issues.append(f"CSV row {i}: blank Borehole number")
        if not r.get("Location","").strip(): issues.append(f"CSV row {i}: blank Location")
        if lat is None or lon is None:
            issues.append(f"CSV row {i}: missing/non-numeric coordinates")
        elif not (-25<=lat<=-10 and (175<=lon<=180 or -180<=lon<=-175)):
            issues.append(f"CSV row {i}: coordinates outside Fiji bounds ({lat}, {lon})")
    if issues:
        print("WARNINGS (these records remain in the table but will not appear on the map):")
        for x in issues: print(" - "+x)
    else:
        print("PASS: all coordinates fall within the configured Fiji bounds.")

if __name__=="__main__": main()
