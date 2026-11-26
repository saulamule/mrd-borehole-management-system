# MRD Borehole Management System — Stage 2

**Repository:** Private GitHub repository  
**Administration:** One designated administrator  
**Master register:** `data/boreholes.csv`

This project provides a single-administrator workflow for maintaining the MRD unreticulated borehole register and generating a read-only GIS and operational dashboard.

## Contents
- `data/boreholes.csv` — editable operational master register (93 source records).
- `data/source_register_2026-11-26.xlsx` — original workbook snapshot for reference.
- `dashboard_template.html` — responsive map and monitoring dashboard template.
- `generate_dashboard.py` — generates `docs/index.html` from the CSV.
- `validate_data.py` — checks required fields, duplicate IDs and coordinate quality.
- `docs/index.html` — generated dashboard preview.
- `.github/workflows/deploy-dashboard.yml` — currently runs validation and build checks only.
- `ADMIN_GUIDE.md` — register update and administration instructions.

## Current deployment status
The repository is private. **Public website deployment is intentionally not enabled yet** because the register includes borehole locations and coordinates. GitHub Pages sites are publicly available by default even if their source repository is private. Private Pages access control requires GitHub Enterprise Cloud. Confirm MRD data-release approval and the required website visibility before enabling deployment.

After approval, configure **Settings → Pages → Source → GitHub Actions**, then enable the deployment steps in the workflow. See [GitHub's publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Update the register
1. Download `data/boreholes.csv` and open it in Excel using UTF-8.
2. Edit the required record or append a new record. Keep the column headings unchanged.
3. Save as **CSV UTF-8** and retain the filename `boreholes.csv`.
4. Replace `data/boreholes.csv` in this repository and commit to `main`.
5. Review the **Actions** run and resolve any validation failures or coordinate warnings.

The dashboard is read-only. Only repository write/admin users can change the register. See `ADMIN_GUIDE.md`.

## Validation notes
The supplied register contains 93 rows. The validation script passes required-column and duplicate-ID checks, but flags missing borehole identifiers and several coordinates outside Fiji bounds or missing. These records are retained for review and are not plotted on the map. No coordinates have been guessed or automatically corrected.

## Limitations
- GitHub Pages is static hosting, not a transactional database.
- The map basemap depends on external tile providers and internet/firewall access.
- In-page editing, approvals, user roles and photo uploads require a backend beyond GitHub Pages.
- Do not add passwords, access tokens, personal information or confidential field notes to the register.
