# Administrator Guide — MRD Borehole Management System

## Access control
Keep this repository private unless MRD formally authorises a public release. Maintain one designated administrator with write/admin access. Enable two-factor authentication. Do not share passwords or personal access tokens.

## Update the register in Excel
1. Download `data/boreholes.csv` from the repository.
2. Open it in Excel. Import as UTF-8 if prompted.
3. Edit an existing record or add a new row.
4. Keep every column heading unchanged.
5. Keep `Borehole number` unique. Check latitude and longitude carefully; Fiji latitudes are generally negative. Do not swap coordinate columns.
6. Save/export as **CSV UTF-8 (Comma delimited)** with the filename `boreholes.csv`.
7. Upload/replace `data/boreholes.csv` in GitHub and commit to `main`.
8. Open **Actions** and review the validation/build result.

## Validation behaviour
- Required columns must exist and the file must contain records.
- Duplicate nonblank borehole numbers stop validation.
- Blank borehole identifiers and locations are reported.
- Missing, non-numeric or out-of-Fiji-bounds coordinates are reported.
- Records with invalid/missing coordinates remain in the table but are not plotted.

## Existing source-register review flags
The initial 93-row source register includes blank borehole numbers and several coordinate issues. The validation output identifies affected CSV rows. Review against the original MRD records before amending; do not guess or auto-correct coordinates.

## Deployment and data protection
The current GitHub Actions workflow validates and builds the dashboard only. It does **not** publish a website. Do not enable GitHub Pages deployment until MRD approves the data release and required website visibility is confirmed. GitHub Pages is normally public even with a private source repository; private Pages access control requires GitHub Enterprise Cloud.

## Restore a previous version
GitHub retains commit history. Locate the last known-good `data/boreholes.csv` in the repository history, restore that version, and commit it. The validation/build workflow will run again.
