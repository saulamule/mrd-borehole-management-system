#!/usr/bin/env python3
"""Build the MRD Borehole Management System dashboard from data/boreholes.csv."""
from pathlib import Path
from datetime import datetime, timezone
import csv, json, re, sys

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "data" / "boreholes.csv"
TEMPLATE = ROOT / "dashboard_template.html"
OUTPUT = ROOT / "docs" / "index.html"
PURCHASING_JSON = ROOT / "data" / "purchasing_materials.json"

def text(v):
    return (v or "").strip()

def num(v):
    s = text(v).replace(",", "").replace("°", "")
    if not s:
        return None
    try:
        return float(re.sub(r"\s+", "", s))
    except ValueError:
        return None

def in_fiji(lat, lon):
    return lat is not None and lon is not None and -25 <= lat <= -10 and (
        175 <= lon <= 180 or -180 <= lon <= -175
    )

def main():
    if not CSV_FILE.exists():
        raise SystemExit(f"Missing source register: {CSV_FILE}")
    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("The CSV file is empty or has no header row.")
        required = ["Borehole number", "Location", "Latitude", "Longitude",
                    "Division", "Province"]
        missing = [h for h in required if h not in reader.fieldnames]
        if missing:
            raise SystemExit("Required CSV columns missing: " + ", ".join(missing))
        raw = list(reader)

    records = []
    for row in raw:
        lat, lon = num(row.get("Latitude")), num(row.get("Longitude"))
        records.append({
            "record_no": text(row.get("No.")),
            "year": text(row.get("Year / FY drilled")),
            "borehole": text(row.get("Borehole number")),
            "location": text(row.get("Location")),
            "latitude": lat, "longitude": lon, "mapped": in_fiji(lat, lon),
            "division": text(row.get("Division")) or "Unspecified",
            "province": text(row.get("Province")) or "Unspecified",
            "depth": num(row.get("Depth (m)")),
            "discharge": num(row.get("Preliminary discharge (L/s)")),
            "status": text(row.get("Status")) or "Not recorded",
            "pump_test": text(row.get("Pump-test status")) or "Not recorded",
            "reticulation": text(row.get("Reticulation status")) or "Not recorded",
            "community_water": text(row.get("Community Water Status")) or "Not recorded",
            "support": text(row.get("Options for support")) or "Not recorded",
            "tikina": text(row.get("Tikina")) or "Not recorded",
            "tikina_water_status": text(row.get("NDRMO Tikina water status (22 Nov)")) or "Not recorded",
            "tikina_critical_share": num(row.get("% of people in Critical or worse communities (tikina)")),
            "tikina_critical_communities": text(row.get("Communities Critical or worse (tikina)")) or "Not recorded",
            "tikina_note": text(row.get("Tikina note")) or "Not recorded",
            "additional_source_field_1": text(row.get("Additional source field 1")) or "Not recorded",
            "additional_source_field_2": text(row.get("Additional source field 2")) or "Not recorded",
        })

    template = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    if not PURCHASING_JSON.exists():
        raise SystemExit(f"Missing purchasing list: {PURCHASING_JSON}")
    purchasing = json.loads(PURCHASING_JSON.read_text(encoding="utf-8"))
    purchasing_payload = json.dumps(purchasing, ensure_ascii=False).replace("</", "<\\/")
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = (template.replace("__DATA_JSON__", payload)
                    .replace("__TOTAL__", str(len(records)))
                    .replace("__MAPPED__", str(sum(r["mapped"] for r in records)))
                    .replace("__PURCHASING_DATA_JSON__", purchasing_payload)
                    .replace("__BUILT_AT__", built))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Dashboard generated: {OUTPUT}")
    print(f"Register records: {len(records)}")
    print(f"Mapped records: {sum(r['mapped'] for r in records)}")
    print(f"Coordinate review: {sum(not r['mapped'] for r in records)}")

if __name__ == "__main__":
    main()
