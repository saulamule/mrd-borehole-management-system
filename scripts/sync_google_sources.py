#!/usr/bin/env python3
"""Synchronise approved MRD sources from private Google Drive into the build workspace.

The source files are read-only. This script never commits source records to Git.
Only the generated dashboard is eligible for Pages publication, controlled by
the explicit MRD_DASHBOARD_PUBLIC_RELEASE_APPROVED Actions variable.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"

BOREHOLE_FILE = "Copy of Unreticulated_Boreholes_Updated261126 - tikina status.xlsx"
PURCHASING_FILE = "Copy of Draft ONE STAND PIPE MATERIAL LIST.xlsx"
RESOURCES_FILE = "Copy of Resources Required Consolidated"

# Used only when the first table's section heading is merged with other title cells.
FALLBACK_SECTIONS = [
    "SOLAR PUMP SYSTEM",
    "BOREHOLE",
    "BOREHOLE GAGE",
    "PUMPING LINE",
    "STORAGE TANK",
    "DISTRIBUTION LINE",
    "STANDPIPE",
]
TOTAL_LABELS = ("subtotal", "sub total", "grand total", "total materials", "total cost")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required GitHub Actions variable is missing: {name}")
    return value


def google_get(url: str, token: str, *, binary: bool = False):
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "*/*" if binary else "application/json",
            "User-Agent": "MRD-Borehole-Dashboard-Sync/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=90) as response:
            payload = response.read()
            return payload if binary else json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Google API request failed (HTTP {exc.code}). Response: {details[:1200]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Google API: {exc.reason}") from exc


def list_folder_items(folder_id: str, token: str) -> list[dict]:
    query = f"'{folder_id}' in parents and trashed = false"
    items: list[dict] = []
    page_token = None
    while True:
        params = {
            "q": query,
            "pageSize": 100,
            "orderBy": "name",
            "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,size)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        result = google_get(f"{DRIVE_API}/files?{urlencode(params)}", token)
        items.extend(result.get("files", []))
        if result.get("incompleteSearch"):
            raise RuntimeError("Google Drive returned an incomplete folder search.")
        page_token = result.get("nextPageToken")
        if not page_token:
            return items


def get_item(items: list[dict], name: str) -> dict:
    matches = [item for item in items if item.get("name") == name]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one Drive item named {name!r}; found {len(matches)}."
        )
    return matches[0]


def download_xlsx(item: dict, token: str):
    content = google_get(
        f"{DRIVE_API}/files/{quote(item['id'], safe='')}?alt=media",
        token,
        binary=True,
    )
    try:
        return load_workbook(BytesIO(content), read_only=False, data_only=True)
    except Exception as exc:
        raise RuntimeError(f"Could not open Excel workbook {item.get('name')}: {exc}") from exc


def cell_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def number(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def sync_boreholes(item: dict, token: str) -> int:
    workbook = download_xlsx(item, token)
    try:
        if "unreticulated" not in workbook.sheetnames:
            raise RuntimeError(
                f"Expected worksheet 'unreticulated' in {BOREHOLE_FILE}; found {workbook.sheetnames}."
            )
        sheet = workbook["unreticulated"]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            raise RuntimeError("The borehole source worksheet is empty.")
        headers = [re.sub(r"\\s+", " ", cell_text(value)).strip() for value in rows[0]]
        while headers and not headers[-1]:
            headers.pop()
        required = {
            "Borehole number", "Location", "Latitude", "Longitude", "Division", "Province"
        }
        missing = sorted(required.difference(headers))
        if missing:
            raise RuntimeError("Borehole workbook missing required columns: " + ", ".join(missing))
        if len(headers) != len(set(headers)):
            raise RuntimeError("Borehole source contains duplicate column headings.")

        records = []
        for row in rows[1:]:
            values = list(row[:len(headers)])
            if not any(value is not None and str(value).strip() for value in values):
                continue
            values.extend([""] * (len(headers) - len(values)))
            records.append({headers[i]: csv_value(values[i]) for i in range(len(headers))})
        if not records:
            raise RuntimeError("No borehole data rows were found in the source workbook.")

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        target = DATA_DIR / "boreholes.csv"
        with target.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return len(records)
    finally:
        workbook.close()


def looks_like_material_header(row) -> bool:
    values = [cell_text(x).casefold() for x in list(row[:5])]
    if len(values) < 5:
        return False
    return (
        "material" in values[0]
        and values[1] in ("qty", "quantity")
        and ("unit cost" in values[2] or "unit price" in values[2])
        and "supplier" in values[3]
        and ("amount" in values[4] or "total" in values[4])
    )


def find_section_label(rows, header_index: int, previous_header_index: int):
    # Section names are usually a standalone title cell in column A immediately before a table.
    for index in range(header_index - 1, previous_header_index, -1):
        row = rows[index]
        nonempty = [v for v in row[:5] if v is not None and str(v).strip()]
        if len(nonempty) == 1 and row and isinstance(row[0], str):
            label = row[0].strip()
            lowered = label.casefold()
            if label and lowered not in ("material", "materials", "all materials") and not is_total_label(label):
                return label
    return None


def is_total_label(label: str) -> bool:
    lower = label.casefold().strip()
    return any(term in lower for term in TOTAL_LABELS)


def parse_material_rows(rows, header_index: int, next_header_index: int):
    items = []
    for row in rows[header_index + 1:next_header_index]:
        if not row or len(row) < 5:
            row = list(row or []) + [None] * (5 - len(row or []))
        material = cell_text(row[0])
        if not material or is_total_label(material):
            continue
        qty_value, unit_value, supplier_value, amount_value = row[1:5]
        # Exclude section captions/notes that have no quantity, unit cost or amount.
        if all(value is None or str(value).strip() == "" for value in (qty_value, unit_value, amount_value)):
            continue

        qty = cell_text(qty_value) or None
        unit_cost = number(unit_value)
        amount = number(amount_value)
        # If an Excel amount formula has no cached value, calculate only when both
        # quantity and unit cost are clearly numeric.
        qty_number = number(qty_value)
        if amount is None and qty_number is not None and unit_cost is not None:
            amount = qty_number * unit_cost

        supplier = cell_text(supplier_value) or None
        items.append({
            "material": material,
            "qty": qty,
            "unit_cost": unit_cost,
            "supplier": supplier,
            "amount": amount,
        })
    return items


def sync_purchasing(item: dict, token: str) -> tuple[int, int, float]:
    old_file = DATA_DIR / "purchasing_materials.json"
    legacy_sections = []
    if old_file.exists():
        try:
            old = json.loads(old_file.read_text(encoding="utf-8"))
            legacy_sections = [section.get("name") for section in old.get("sections", [])]
        except Exception:
            legacy_sections = []

    workbook = download_xlsx(item, token)
    try:
        if "All Materials" not in workbook.sheetnames:
            raise RuntimeError("Purchasing workbook has no 'All Materials' worksheet.")
        sheet = workbook["All Materials"]
        rows = list(sheet.iter_rows(values_only=True))
        header_indexes = [i for i, row in enumerate(rows) if looks_like_material_header(row)]
        if len(header_indexes) != 7:
            raise RuntimeError(
                f"Expected 7 material tables in 'All Materials'; found {len(header_indexes)}. "
                "The workbook layout may have changed and needs review."
            )

        sections = []
        total_items = 0
        total_amount = 0.0
        for group_index, header_index in enumerate(header_indexes):
            previous_header = header_indexes[group_index - 1] if group_index else -1
            next_header = header_indexes[group_index + 1] if group_index + 1 < len(header_indexes) else len(rows)
            section_name = find_section_label(rows, header_index, previous_header)
            if not section_name:
                section_name = (
                    legacy_sections[group_index]
                    if group_index < len(legacy_sections) and legacy_sections[group_index]
                    else FALLBACK_SECTIONS[group_index]
                )
            items = parse_material_rows(rows, header_index, next_header)
            if not items:
                raise RuntimeError(f"No material rows were detected for section {section_name!r}.")
            subtotal = round(sum(x["amount"] or 0 for x in items), 2)
            total_items += len(items)
            total_amount += subtotal
            sections.append({
                "name": section_name,
                "items": items,
                "subtotal": subtotal,
                "line_total": subtotal,
            })

        total_amount = round(total_amount, 2)
        result = {
            "source_file": item.get("name"),
            "source_file_id": item.get("id"),
            "currency": "FJD",
            "quantity_basis": "One site (as recorded in the source workbook)",
            "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "sections": sections,
            "reported_summary": [
                {
                    "name": section["name"],
                    "amount": section["subtotal"],
                    "source_amount": section["subtotal"],
                    "mrd": "",
                    "waf": "",
                }
                for section in sections
            ] + [{
                "name": "Grand Total",
                "amount": total_amount,
                "source_amount": total_amount,
                "mrd": "",
                "waf": "",
            }],
            "source_grand_total": total_amount,
            "corrected_grand_total": total_amount,
            "quotation_note": "Refer to the source workbook's QUOTATIONS worksheet for quotation details.",
            "source_note": (
                "Imported from the selected Google Drive workbook. Section subtotals are calculated "
                "from material-line amounts; blank prices and amounts are left unestimated."
            ),
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "purchasing_materials.json").write_text(
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        missing_amounts = sum(1 for section in sections for line in section["items"] if line["amount"] is None)
        return total_items, missing_amounts, total_amount
    finally:
        workbook.close()


def read_google_sheet(file_id: str, title: str, token: str) -> dict:
    escaped_title = title.replace("'", "''")
    a1_range = f"'{escaped_title}'!A1:AG1001"
    params = {
        "valueRenderOption": "FORMATTED_VALUE",
        "dateTimeRenderOption": "FORMATTED_STRING",
    }
    url = (
        f"{SHEETS_API}/spreadsheets/{quote(file_id, safe='')}/values/"
        f"{quote(a1_range, safe='')}?{urlencode(params)}"
    )
    result = google_get(url, token)
    values = result.get("values", [])
    if not values:
        return {"title": title, "headers": [], "rows": []}
    headers = [cell_text(x) for x in values[0]]
    rows = []
    for row in values[1:]:
        cleaned = [cell_text(x) for x in row]
        if any(cleaned):
            cleaned.extend([""] * max(0, len(headers) - len(cleaned)))
            rows.append(cleaned[:len(headers)])
    return {"title": title, "headers": headers, "rows": rows}


def sync_resources(item: dict, token: str) -> tuple[int, int]:
    if item.get("mimeType") != SHEET_MIME:
        raise RuntimeError("Resources Required source must remain a native Google Sheets spreadsheet.")
    params = {
        "fields": "spreadsheetId,properties(title),sheets(properties(title,index))"
    }
    metadata = google_get(
        f"{SHEETS_API}/spreadsheets/{quote(item['id'], safe='')}?{urlencode(params)}",
        token,
    )
    sheets = []
    total_rows = 0
    for tab in sorted(metadata.get("sheets", []), key=lambda x: x.get("properties", {}).get("index", 0)):
        title = tab.get("properties", {}).get("title", "")
        if not title:
            continue
        sheet_data = read_google_sheet(item["id"], title, token)
        total_rows += len(sheet_data["rows"])
        sheets.append(sheet_data)

    payload = {
        "source_file": metadata.get("properties", {}).get("title", item.get("name")),
        "source_file_id": item.get("id"),
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sheets": sheets,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "resources_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return len(sheets), total_rows


def main() -> int:
    token = required_env("GOOGLE_ACCESS_TOKEN")
    folder_id = required_env("GOOGLE_DRIVE_FOLDER_ID")
    items = list_folder_items(folder_id, token)

    borehole = get_item(items, BOREHOLE_FILE)
    purchasing = get_item(items, PURCHASING_FILE)
    resources = get_item(items, RESOURCES_FILE)

    borehole_count = sync_boreholes(borehole, token)
    material_count, missing_prices, material_total = sync_purchasing(purchasing, token)
    resource_sheets, resource_rows = sync_resources(resources, token)

    result = {
        "borehole_records": borehole_count,
        "purchasing_material_lines": material_count,
        "purchasing_lines_without_amount": missing_prices,
        "purchasing_total_fjd": material_total,
        "resource_worksheets": resource_sheets,
        "resource_data_rows": resource_rows,
    }
    # Keep logs to aggregate diagnostics only; never print individual source records.
    print("MRD Google Drive source sync completed:")
    print(json.dumps(result, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write("# MRD Google Drive source sync\n\n")
            output.write("| Measure | Result |\n|---|---:|\n")
            for key, value in result.items():
                output.write(f"| {key.replace('_', ' ').title()} | {value} |\n")
            output.write("\nSource records are staged in the ephemeral runner workspace only; no source data is committed to Git.\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"::error title=MRD Google Drive sync failed::{exc}", file=sys.stderr)
        raise SystemExit(1)
