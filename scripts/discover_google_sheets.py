#!/usr/bin/env python3
"""Read-only inventory of files and Google Sheets in the configured Drive folder.

For native Google Sheets, reads only spreadsheet metadata, worksheet names,
and row-1 column headings. Does not fetch data rows or modify Drive files.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
FOLDER_MIME = "application/vnd.google-apps.folder"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required GitHub Actions variable is missing: {name}")
    return value


def google_get(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
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
            "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,webViewLink)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        result = google_get(f"{DRIVE_API}/files?{urlencode(params)}", token)
        items.extend(result.get("files", []))
        if result.get("incompleteSearch"):
            raise RuntimeError("Google Drive reported an incomplete folder search.")
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return items


def get_spreadsheet_metadata(file_id: str, token: str) -> dict:
    params = {
        "fields": "spreadsheetId,spreadsheetUrl,properties(title),sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))"
    }
    return google_get(
        f"{SHEETS_API}/spreadsheets/{quote(file_id, safe='')}?{urlencode(params)}",
        token,
    )


def get_headers(file_id: str, tab_title: str, token: str) -> list[str]:
    escaped_title = tab_title.replace("'", "''")
    a1_range = f"'{escaped_title}'!1:1"
    url = (
        f"{SHEETS_API}/spreadsheets/{quote(file_id, safe='')}/values/"
        f"{quote(a1_range, safe='')}?majorDimension=ROWS"
    )
    values = google_get(url, token).get("values", [])
    return [str(value).strip() for value in values[0]] if values else []


def md(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ").strip()


def main() -> int:
    token = require_env("GOOGLE_ACCESS_TOKEN")
    folder_id = require_env("GOOGLE_DRIVE_FOLDER_ID")
    items = list_folder_items(folder_id, token)
    if not items:
        raise RuntimeError(
            "The configured Drive folder appears empty or is not accessible to the service account."
        )

    native_sheets = [item for item in items if item.get("mimeType") == SHEET_MIME]
    summary = [
        "# MRD Google Drive folder inventory",
        "",
        f"Found **{len(items)} direct item(s)**, including **{len(native_sheets)} native Google Sheets file(s)**.",
        "",
        "> Privacy: this check reads file names/types and, for native Google Sheets only, worksheet names and row-1 headings. "
        "It does not read data rows, download Excel files, or modify Drive content.",
        "",
        "| Name | File type | Last modified |",
        "|---|---|---|",
    ]

    for item in items:
        mime = item.get("mimeType", "Unknown")
        kind = (
            "Google Sheets"
            if mime == SHEET_MIME
            else "Folder"
            if mime == FOLDER_MIME
            else "Excel workbook"
            if mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-excel")
            else mime
        )
        summary.append(
            f"| {md(item.get('name', 'Untitled'))} | {md(kind)} | {md(item.get('modifiedTime', 'Not supplied'))} |"
        )

    for index, item in enumerate(native_sheets, start=1):
        file_id = item["id"]
        metadata = get_spreadsheet_metadata(file_id, token)
        title = metadata.get("properties", {}).get("title") or item.get("name", "Untitled")
        summary.extend([
            "",
            f"## Google Sheet {index}: {md(title)}",
            f"- Spreadsheet ID: {file_id}",
            f"- Spreadsheet URL: {item.get('webViewLink') or metadata.get('spreadsheetUrl') or 'Not supplied'}",
            "",
            "| Worksheet | Column headings in row 1 |",
            "|---|---|",
        ])
        tabs = sorted(
            metadata.get("sheets", []),
            key=lambda tab: tab.get("properties", {}).get("index", 0),
        )
        for tab in tabs:
            title = tab.get("properties", {}).get("title", "Untitled tab")
            headers = get_headers(file_id, title, token)
            summary.append(
                f"| {md(title)} | {md(', '.join(h for h in headers if h) or '(no headings in row 1)')} |"
            )

    summary.extend([
        "",
        "## Next action",
        "- Native Google Sheets can be read directly by the synchronisation workflow.",
        "- Excel workbooks need to be converted to Google Sheets or handled with a separate Excel-reading path.",
        "- Files inside nested folders are not included in this direct-folder inventory.",
    ])
    rendered = "\n".join(summary)
    print(rendered)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as output:
            output.write(rendered + "\n")
    print("DISCOVERY COMPLETE: Drive folder inventory succeeded.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"::error title=Google Drive folder inventory failed::{exc}", file=sys.stderr)
        raise SystemExit(1)
