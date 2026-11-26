# Administrator Guide — MRD Borehole Management System

## Repository and publication access

The GitHub repository and GitHub Pages website are public. Keep repository write/admin access limited to the designated administrator(s), use two-factor authentication, and do not store passwords, personal access tokens, service-account keys or other credentials in the repository.

The Google Drive source folder must remain restricted. The dedicated service account has Viewer access and the GitHub Actions workflow uses Workload Identity Federation with read-only Drive and Sheets API scopes.

## Official Google Drive sources

The scheduled sync reads these three source files from the dedicated Drive folder:

1. Borehole register: Copy of Unreticulated_Boreholes_Updated261126 - tikina status.xlsx, worksheet unreticulated.
2. Purchasing materials: Copy of Draft ONE STAND PIPE MATERIAL LIST.xlsx, worksheet All Materials.
3. Resources Required: Copy of Resources Required Consolidated, worksheets Personnel, Total Cost Reticulation, Equipment & Materials, and Transport.

The Excel workbooks are read directly from Drive and do not need conversion to Google Sheets. Do not rename the source files or worksheet tabs without updating the sync configuration.

## Updating source records

1. Open the source file in the restricted Google Drive folder.
2. Update the required values in the appropriate worksheet.
3. Keep the required column headings and worksheet names intact.
4. Allow the scheduled 15-minute sync to run, or start it manually from GitHub: **Actions → Sync MRD Dashboard from Google Drive → Run workflow**.
5. Review the workflow summary and validation results.

The service account reads the source files only. It does not edit or overwrite the Google Drive workbooks.

## Validation and failure handling

- The borehole register must contain the required headings and unique nonblank borehole identifiers where supplied.
- Missing or invalid coordinates are reported. Such records remain in the table but are not plotted.
- Material rows without an amount remain blank; the workflow does not invent supplier prices.
- A missing source file, changed worksheet layout, validation error or Google API failure stops the build.
- Failed builds do not replace the currently deployed dashboard.

## Public-release approval

Because the repository and Pages website are public, the synchronisation workflow does not publish new source data by default.

Only after MRD approves the exact fields and figures for public release, set the repository Actions variable:

- Name: MRD_DASHBOARD_PUBLIC_RELEASE_APPROVED
- Value: true

Location: **Repository Settings → Secrets and variables → Actions → Variables**.

When this variable is not set to true, the workflow can read, validate and build the data in the temporary runner, but it skips the Pages artifact upload and deployment. When approval is enabled, the dashboard will automatically deploy after each successful sync.

Only the generated dashboard is published. The source Excel workbooks, Google Sheet and synced CSV/JSON workspace files are not committed to Git.

## Manual recovery

If a source layout changes, review the failed workflow log and restore the required column headings/worksheet names or update the sync script. Do not guess missing coordinates, quantities or supplier prices. The committed data files remain as fallback snapshots; the live sync writes fresh copies only inside the runner workspace.
