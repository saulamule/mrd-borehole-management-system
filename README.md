# MRD Borehole Management System — Stage 2

**Repository:** Private GitHub repository  
**Administration:** One designated administrator  
**Master register:** `data/boreholes.csv`

This project provides a single-administrator workflow for maintaining the MRD unreticulated borehole register and generating a read-only GIS and operational dashboard.

## Contents
- `data/boreholes.csv` — operational master register (93 source records).
- `dashboard_template.html` — responsive map and monitoring dashboard template.
- `generate_dashboard.py` — generates `docs/index.html` from the CSV.
- `validate_data.py` — checks required fields, duplicate IDs and coordinate quality.
- `docs/index.html` — current generated dashboard preview.
- `ADMIN_GUIDE.md` — register update and administration instructions.
- `.github/workflows/deploy-dashboard.yml` — currently runs validation and build checks only.

## Current deployment status
The repository is private. **Public website deployment is intentionally not enabled yet** because the register includes borehole locations and coordinates. GitHub Pages sites are publicly available by default even when their source repository is private. Private Pages access control requires GitHub Enterprise Cloud. Confirm MRD data-release approval and the intended website visibility before enabling deployment.

After approval, configure **Settings → Pages → Source → GitHub Actions**, then enable the deployment steps in the workflow. See the official [GitHub Pages publishing documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

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
