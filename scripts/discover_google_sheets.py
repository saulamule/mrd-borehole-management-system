#!/usr/bin/env python3
"""Read-only inspection of selected MRD Drive sources."""
from __future__ import annotations
import json, os, sys
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from openpyxl import load_workbook

DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
TARGETS = {
    "Copy of Draft ONE STAND PIPE MATERIAL LIST.xlsx",
    "Copy of Unreticulated_Boreholes_Updated261126 - tikina status.xlsx",
}
HEADER_TERMS = (
    "borehole", "location", "latitude", "longitude", "division", "province",
    "material", "supplier", "unit cost", "quantity", "qty", "amount", "total",
    "mrd", "waf", "pump", "depth", "discharge", "status", "year", "item",
    "description", "section", "cost", "team", "transport", "reticulation",
)

def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Missing required environment variable: " + name)
    return value

def get(url, token, binary=False):
    request = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "*/*" if binary else "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
            return payload if binary else json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Google API HTTP " + str(exc.code) + ": " + details[:1000]) from exc
    except URLError as exc:
        raise RuntimeError("Google API connection failed: " + str(exc.reason)) from exc

def list_items(folder_id, token):
    query = "'" + folder_id + "' in parents and trashed = false"
    items, page_token = [], None
    while True:
        params = {
            "q": query, "pageSize": 100, "orderBy": "name",
            "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,webViewLink,size)",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        result = get(DRIVE_API + "/files?" + urlencode(params), token)
        items.extend(result.get("files", []))
        if result.get("incompleteSearch"):
            raise RuntimeError("Drive returned an incomplete search.")
        page_token = result.get("nextPageToken")
        if not page_token:
            return items

def sheet_meta(file_id, token):
    params = {"fields": "spreadsheetId,spreadsheetUrl,properties(title),sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))"}
    return get(SHEETS_API + "/spreadsheets/" + quote(file_id, safe="") + "?" + urlencode(params), token)

def sheet_headers(file_id, tab_title, token):
    title = tab_title.replace("'", "''")
    a1 = "'" + title + "'!1:1"
    url = SHEETS_API + "/spreadsheets/" + quote(file_id, safe="") + "/values/" + quote(a1, safe="") + "?majorDimension=ROWS"
    values = get(url, token).get("values", [])
    return [str(x).strip() for x in values[0]] if values else []

def inspect_xlsx(item, token):
    raw = get(DRIVE_API + "/files/" + quote(item["id"], safe="") + "?alt=media", token, binary=True)
    wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        rows = min(ws.max_row or 0, 25)
        cols = min(ws.max_column or 0, 80)
        candidates = []
        for row_no, row in enumerate(ws.iter_rows(min_row=1, max_row=rows, max_col=cols, values_only=True), start=1):
            cells, terms = [], 0
            for col_no, val in enumerate(row, start=1):
                if val is None or str(val).strip() == "" or isinstance(val, (int, float)):
                    continue
                label = str(val).strip()
                if len(label) > 100:
                    continue
                cells.append((col_no, label))
                if any(term in label.casefold() for term in HEADER_TERMS):
                    terms += 1
            if len(cells) >= 2:
                uniq = len({v.casefold() for _, v in cells}) / len(cells)
                candidates.append((terms * 4 + len(cells) + uniq, row_no, cells))
        candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        lines.append("### Worksheet: " + ws.title)
        lines.append("- Dimensions: " + str(ws.max_row or 0) + " rows x " + str(ws.max_column or 0) + " columns")
        if candidates:
            lines.append("- Likely header candidates (text labels only; numeric/data samples omitted):")
            for _, row_no, cells in candidates[:3]:
                labels = ", ".join("column " + str(col) + ": " + label for col, label in cells)
                lines.append("  - Row " + str(row_no) + ": " + labels)
        else:
            lines.append("- No likely header row found in first 25 rows.")
    wb.close()
    return lines

def main():
    token, folder_id = env("GOOGLE_ACCESS_TOKEN"), env("GOOGLE_DRIVE_FOLDER_ID")
    items = list_items(folder_id, token)
    if not items:
        raise RuntimeError("No direct items found in the configured Drive folder.")
    by_name = {x.get("name"): x for x in items}
    lines = [
        "# MRD selected source workbook inspection", "",
        "Read-only inspection: worksheet names, dimensions, and likely header labels only. "
        "No data rows are printed and no Drive files are modified.", "",
        "Drive folder contains " + str(len(items)) + " direct items.", "",
    ]
    native = by_name.get("Copy of Resources Required Consolidated")
    if native and native.get("mimeType") == SHEET_MIME:
        meta = sheet_meta(native["id"], token)
        lines.extend(["## Google Sheet: " + meta.get("properties", {}).get("title", native["name"]),
                      "- Spreadsheet ID: " + native["id"], "",
                      "| Worksheet | Headings in row 1 |", "|---|---|"])
        for tab in sorted(meta.get("sheets", []), key=lambda x: x.get("properties", {}).get("index", 0)):
            title = tab.get("properties", {}).get("title", "Untitled")
            headers = sheet_headers(native["id"], title, token)
            lines.append("| " + title + " | " + (", ".join(x for x in headers if x) or "(no row-1 headings)") + " |")
        lines.append("")
    for target in sorted(TARGETS):
        item = by_name.get(target)
        if not item:
            lines.extend(["## Missing selected workbook: " + target, ""])
            continue
        lines.extend(["## Excel workbook: " + target,
                      "- Drive file ID: " + item["id"],
                      "- Size: " + str(item.get("size", "not supplied")) + " bytes", ""])
        lines.extend(inspect_xlsx(item, token))
        lines.append("")
    output = "\n".join(lines)
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fp:
            fp.write(output + "\n")
    print("INSPECTION COMPLETE: no source data rows printed or modified.")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error title=Selected workbook inspection failed::" + str(exc), file=sys.stderr)
        raise SystemExit(1)
