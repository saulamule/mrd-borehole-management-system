#!/usr/bin/env python3
"""Inspect approved MRD source-file structures without printing operational rows."""
from __future__ import annotations
import json, os, sys
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from openpyxl import load_workbook

DRIVE = "https://www.googleapis.com/drive/v3"
SHEETS = "https://sheets.googleapis.com/v4"
TARGET_BOREHOLES = "Copy of Unreticulated_Boreholes_Updated261126 - tikina status.xlsx"
TARGET_PURCHASING = "Copy of Draft ONE STAND PIPE MATERIAL LIST.xlsx"
TARGET_RESOURCES = "Copy of Resources Required Consolidated"

def api_get(url: str, token: str, binary: bool = False):
    req = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "*/*" if binary else "application/json"})
    try:
        with urlopen(req, timeout=60) as response:
            payload = response.read()
            return payload if binary else json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Google API HTTP " + str(exc.code) + ": " + msg[:1000]) from exc
    except URLError as exc:
        raise RuntimeError("Google API connection error: " + str(exc.reason)) from exc

def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Missing environment variable " + name)
    return value

def list_items(folder_id: str, token: str):
    q = "'" + folder_id + "' in parents and trashed=false"
    params = {
        "q": q, "pageSize": 100, "orderBy": "name",
        "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime)",
        "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
    }
    out, page = [], None
    while True:
        if page:
            params["pageToken"] = page
        res = api_get(DRIVE + "/files?" + urlencode(params), token)
        out.extend(res.get("files", []))
        page = res.get("nextPageToken")
        if not page:
            return out

def download_workbook(item, token):
    raw = api_get(DRIVE + "/files/" + quote(item["id"], safe="") + "?alt=media", token, binary=True)
    return load_workbook(BytesIO(raw), read_only=False, data_only=True)

def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None

def nonempty(values):
    return [x for x in values if x is not None and str(x).strip()]

def main():
    token = require("GOOGLE_ACCESS_TOKEN")
    folder_id = require("GOOGLE_DRIVE_FOLDER_ID")
    items = list_items(folder_id, token)
    by_name = {x.get("name"): x for x in items}
    lines = [
        "# MRD approved source structure", "",
        "Read-only inspection. This report contains worksheet layouts and aggregate counts only; "
        "it does not print borehole records, community details, supplier line items, or raw financial rows.", "",
    ]

    bore = by_name.get(TARGET_BOREHOLES)
    if not bore:
        raise RuntimeError("Selected borehole workbook is missing from the Drive folder: " + TARGET_BOREHOLES)
    wb = download_workbook(bore, token)
    ws = wb["unreticulated"] if "unreticulated" in wb.sheetnames else wb[wb.sheetnames[0]]
    all_rows = list(ws.iter_rows(values_only=True))
    headers = [str(x).strip() if x is not None else "" for x in all_rows[0]]
    data_rows = [r for r in all_rows[1:] if nonempty(r)]
    lines.extend([
        "## Borehole register",
        "- Source worksheet: " + ws.title,
        "- Non-empty data rows: " + str(len(data_rows)),
        "- Column headings: " + ", ".join(x for x in headers if x),
        "",
    ])
    wb.close()

    purchase = by_name.get(TARGET_PURCHASING)
    if not purchase:
        raise RuntimeError("Selected purchasing workbook is missing from the Drive folder: " + TARGET_PURCHASING)
    wb = download_workbook(purchase, token)
    ws = wb["All Materials"] if "All Materials" in wb.sheetnames else wb[wb.sheetnames[0]]
    values = list(ws.iter_rows(values_only=True))
    header_rows = []
    for idx, row in enumerate(values, start=1):
        vals = [str(x).strip().casefold() if x is not None else "" for x in row[:5]]
        if len(vals) >= 5 and "material" in vals[0] and vals[1] in ("qty", "quantity") and ("unit cost" in vals[2] or "unit price" in vals[2]) and "supplier" in vals[3] and ("amount" in vals[4] or "total" in vals[4]):
            header_rows.append(idx)
    lines.extend([
        "## Purchasing materials",
        "- Source worksheet: " + ws.title,
        "- Detected material-table header rows: " + str(len(header_rows)),
    ])
    last_end = 0
    for group_no, row_no in enumerate(header_rows, start=1):
        section = None
        for prior in range(row_no - 1, last_end, -1):
            row = values[prior - 1] if prior - 1 < len(values) else ()
            cells = nonempty(row[:5])
            if len(cells) == 1 and row and isinstance(row[0], str):
                label = row[0].strip()
                if label and label.casefold() not in ("material", "materials", "all materials"):
                    section = label
                    break
        stop = header_rows[group_no] if group_no < len(header_rows) else len(values) + 1
        item_count, amount_total, missing_amounts = 0, 0.0, 0
        for row in values[row_no:stop - 1]:
            if not row or not row[0] or not str(row[0]).strip():
                continue
            label = str(row[0]).strip().casefold()
            if label in ("material", "subtotal", "sub total", "total", "grand total") or any(x in label for x in ("subtotal", "sub total", "grand total")):
                continue
            item_count += 1
            amount = num(row[4] if len(row) > 4 else None)
            if amount is None:
                missing_amounts += 1
            else:
                amount_total += amount
        lines.append(
            "- Table " + str(group_no) + ": header row " + str(row_no)
            + "; section label: " + (section or "(not detected)")
            + "; material rows: " + str(item_count)
            + "; rows without amount: " + str(missing_amounts)
            + "; computed amount subtotal: FJD " + format(amount_total, ",.2f")
        )
        last_end = row_no
    if not header_rows:
        lines.append("- No matching Material/Qty/Unit Cost/Supplier/Amount table header detected.")
    lines.extend(["- Worksheets in workbook: " + ", ".join(wb.sheetnames), ""])
    wb.close()

    native = by_name.get(TARGET_RESOURCES)
    if not native:
        raise RuntimeError("Selected Resources Required spreadsheet is missing from the Drive folder.")
    if native.get("mimeType") != "application/vnd.google-apps.spreadsheet":
        raise RuntimeError("Resources Required source is no longer a native Google Sheets file.")
    meta_url = SHEETS + "/spreadsheets/" + quote(native["id"], safe="") + "?" + urlencode({
        "fields": "spreadsheetId,properties(title),sheets(properties(title,gridProperties(rowCount,columnCount)))"
    })
    metadata = api_get(meta_url, token)
    lines.extend([
        "## Resources Required",
        "- Google Sheet: " + metadata.get("properties", {}).get("title", TARGET_RESOURCES),
        "- Spreadsheet ID: " + native["id"],
    ])
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        lines.append(
            "- Worksheet: " + props.get("title", "Untitled")
            + " (grid " + str(props.get("gridProperties", {}).get("rowCount", 0)) + " rows x "
            + str(props.get("gridProperties", {}).get("columnCount", 0)) + " columns)"
        )
    lines.append("")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    print("SOURCE INSPECTION COMPLETE: no operational data rows were printed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error title=MRD source inspection failed::" + str(exc), file=sys.stderr)
        raise SystemExit(1)
