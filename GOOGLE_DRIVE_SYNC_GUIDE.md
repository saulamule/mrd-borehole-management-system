# Google Drive synchronisation — MRD Borehole Management Dashboard

## Connected sources

The workflow reads three items directly from the restricted Drive folder:

1. Copy of Unreticulated_Boreholes_Updated261126 - tikina status.xlsx — worksheet unreticulated.
2. Copy of Draft ONE STAND PIPE MATERIAL LIST.xlsx — worksheet All Materials.
3. Copy of Resources Required Consolidated — all four native Google Sheets worksheets.

The two Excel workbooks are downloaded into the GitHub Actions runner's temporary workspace and parsed with openpyxl. The Google Sheets document is read through the Sheets API.

## Schedule

The workflow runs every 15 minutes and can also be started manually from GitHub Actions.

## Data handling

- Google authentication uses Workload Identity Federation; no service-account JSON key is stored.
- The service account has Viewer access to the Drive folder.
- API scopes are read-only: Drive and Sheets.
- Synced source records are written only to the ephemeral GitHub Actions workspace. The workflow does not commit the source workbooks, CSV, or JSON data files to Git.
- Workflow logs contain aggregate counts and validation results, not source data rows.
- The GitHub repository is public and GitHub Pages is public. The workflow therefore has a publication gate.

## Publication gate

Set the repository Actions variable MRD_DASHBOARD_PUBLIC_RELEASE_APPROVED to true only after MRD has approved the dashboard fields for public release.

Until that variable is set to true, the workflow may synchronise and build the site in the temporary runner, but it will not upload a Pages artifact or deploy the updated data.

The existing Pages workflow is subject to the same gate.

## Validation and failure handling

The workflow validates the borehole register before generation. A source-layout change, missing source file, validation failure, or Google API permission error stops the run and leaves the currently deployed dashboard unchanged.
