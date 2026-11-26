# MRD Borehole Management System — Stage 2

**Repository:** Public GitHub repository (website and repository content are publicly accessible)  
**Administration:** One designated administrator  
**Live source:** Restricted Google Drive folder containing the borehole register, materials workbook and Resources Required spreadsheet.

This project provides a single-administrator workflow for maintaining the MRD unreticulated borehole register and generating a read-only GIS and operational dashboard.

## Contents
- `data/boreholes.csv` — fallback/bootstrap snapshot; the live sync replaces this file only in the temporary Actions workspace.
- `dashboard_template.html` — responsive map and monitoring dashboard template.
- `generate_dashboard.py` — generates `docs/index.html` from the CSV.
- `validate_data.py` — checks required fields, duplicate IDs and coordinate quality.
- `docs/index.html` — current generated dashboard preview.
- `ADMIN_GUIDE.md` — register update and administration instructions.
- `.github/workflows/deploy-dashboard.yml` — validates and builds repository data; Pages publishing is approval-gated.
- `.github/workflows/google-drive-sync.yml` — scheduled read-only Google Drive synchronisation and approval-gated Pages deployment.
- `GOOGLE_DRIVE_SYNC_GUIDE.md` — setup, data-protection and publication instructions.
- `scripts/sync_google_sources.py` — imports the three selected sources into the temporary runner workspace.

## Current deployment status
The repository is private. **Public website deployment is intentionally not enabled yet** because the register includes borehole locations and coordinates. GitHub Pages sites are publicly available by default even when their source repository is private. Private Pages access control requires GitHub Enterprise Cloud. Confirm MRD data-release approval and the intended website visibility before enabling deployment.

After approval, configure **Settings → Pages → Source → GitHub Actions**, then enable the deployment steps in the workflow. See the official [GitHub Pages publishing documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Update the source data
1. Open the restricted MRD Borehole Dashboard Data folder in Google Drive.
2. Update the selected borehole workbook (worksheet `unreticulated`), materials workbook (worksheet `All Materials`), or Resources Required Google Sheet.
3. Keep the source filenames, worksheet names and required column headings unchanged. The sync workflow reads the Excel workbooks directly; they do not need to be converted to Google Sheets.
4. The workflow runs every 15 minutes. To run it manually, open **Actions → Sync MRD Dashboard from Google Drive → Run workflow**.
5. Review the run result. Validation failures stop the build and leave the currently deployed dashboard unchanged.


## Validation notes
The supplied register contains 93 rows. The validation script passes required-column and duplicate-ID checks, but flags missing borehole identifiers and several coordinates outside Fiji bounds or missing. These records are retained for review and are not plotted on the map. No coordinates have been guessed or automatically corrected.

## Limitations
- GitHub Pages is static hosting, not a transactional database.
- The map basemap depends on external tile providers and internet/firewall access.
- In-page editing, approvals, user roles and photo uploads require a backend beyond GitHub Pages.
- Do not add passwords, access tokens, personal information or confidential field notes to the register.
