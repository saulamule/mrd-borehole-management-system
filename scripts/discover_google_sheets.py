#!/usr/bin/env python3
"""Read-only discovery of Google Sheets in the configured MRD Drive folder.

Only spreadsheet metadata, worksheet names, and row-1 column headings are read.
No spreadsheet data rows are fetched or written.
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


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required GitHub Actions variable is missing: {name}")
    return value


def google_get(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "MRD-Borehole-Dashboard-Sheets-Discovery/1.0",
        },
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


def list_spreadsheets(folder_id: str, token: str) -> list[dict]:
    query = f"'{folder_id}' in parents and trashed = false and mimeType = '{SHEET_MIME}'"
    files: list[dict] = []
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
        files.extend(result.get("files", []))
        if result.get("incompleteSearch"):
            raise RuntimeError("Google Drive reported an incomplete folder search.")
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return files


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
    result = google_get(url, token)
    values = result.get("values", [])
    if not values:
        return []
    return [str(value).strip() for value in values[0]]


def markdown_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ").strip()


def main() -> int:
    token = require_env("GOOGLE_ACCESS_TOKEN")
    folder_id = require_env("GOOGLE_DRIVE_FOLDER_ID")
    spreadsheets = list_spreadsheets(folder_id, token)

    if not spreadsheets:
        raise RuntimeError(
            "No Google Sheets files were found directly inside the configured Drive folder. "
            "Check the folder ID, file types, and Viewer sharing permission."
        )

    summary: list[str] = [
        "# MRD Google Sheets connection discovery",
        "",
        f"Found **{len(spreadsheets)}** Google Sheets spreadsheet(s) directly in the configured folder.",
        "",
        "> Privacy: this discovery reads spreadsheet titles, worksheet names, and first-row column headings only. "
        "It does not read data rows or modify any Drive file.",
        "",
    ]

    if len(spreadsheets) != 3:
        summary.append(
            f"> **Review:** The folder currently contains {len(spreadsheets)} Google Sheets file(s); "
            "the expected count discussed for this integration is three."
        )
        summary.append("")

    for index, file in enumerate(spreadsheets, start=1):
        file_id = file.get("id", "")
        metadata = get_spreadsheet_metadata(file_id, token)
        title = metadata.get("properties", {}).get("title") or file.get("name", "Untitled")
        summary.extend([
            f"## {index}. {markdown_cell(title)}",
            f"- Spreadsheet ID: {file_id}",
            f"- Last modified: {markdown_cell(file.get('modifiedTime', 'Not supplied'))}",
            f"- Spreadsheet URL: {file.get('webViewLink') or metadata.get('spreadsheetUrl') or 'Not supplied'}",
            "",
        ])

        tabs = sorted(
            metadata.get("sheets", []),
            key=lambda item: item.get("properties", {}).get("index", 0),
        )
        if not tabs:
            summary.extend(["No worksheets were returned.", ""])
            continue

        summary.append("| Worksheet | Column headings in row 1 |")
        summary.append("|---|---|")
        for tab in tabs:
            props = tab.get("properties", {})
            tab_name = props.get("title", "Untitled tab")
            headers = get_headers(file_id, tab_name, token)
            header_text = ", ".join(h for h in headers if h) or "(no headings found in row 1)"
            summary.append(f"| {markdown_cell(tab_name)} | {markdown_cell(header_text)} |")
        summary.append("")

    rendered = "\n".join(summary)
    print(rendered)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as output:
            output.write(rendered + "\n")

    print("DISCOVERY COMPLETE: folder access and spreadsheet header inspection succeeded.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"::error title=Google Sheets discovery failed::{exc}", file=sys.stderr)
        raise SystemExit(1)
