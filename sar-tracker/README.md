# SAR Tracker

SAR Tracker is a static GitHub Pages app for monitoring SAR acquisitions over Taiwan. It combines a Leaflet-based frontend in `index.html`, a Python data-generation script in `fetch_sar_data.py`, and scheduled deployment through `.github/workflows/update.yml`.

## Current Status

The project is usable and deployable, and the recent work focused on making the UI clearer while keeping the current single-file frontend architecture intact.

### Completed Recently

- Moved time shortcuts into the left filter area with `This Week` and `This Month`
- Removed the old top-right mode buttons
- Moved the satellite context card to the top-right map area
- Moved the legend to the lower-left and made it react to current visible data
- Reworked the bottom download bar into a lighter `Export` entry instead of a permanently dominant toolbar
- Widened and cleaned up the right-side detail drawer
- Added automatic map focus behavior for filtered data and selected frames
- Added product-filter summary behavior and reduced left-panel clutter
- Added safer metadata reconciliation logic so nearby records can fill missing `frame_number_norm` and `asf_url` when a valid local match exists
- Added automatic wrapping for long file titles in the right-side drawer
- Removed the non-functional filter summary pills such as `All Satellites`, date range, `DESCENDING`, and `All tracks`

## Repository Structure

```text
SAR_data_monitor/
|-- .github/
|   `-- workflows/
|       `-- update.yml
|-- data/
|   |-- sar_status.json
|   |-- asf_taiwan.meta4
|   |-- copernicus_taiwan.meta4
|   `-- catalog_db.json
|-- fetch_sar_data.py
|-- index.html
`-- README.md
```

## How It Works

### Frontend

`index.html` is a self-contained application. It currently handles:

- map rendering with Leaflet
- filter state
- satellite list rendering
- detail drawer rendering
- export button state
- legend and context updates
- data-source reconciliation at display time

### Data Pipeline

`fetch_sar_data.py` generates the data consumed by the frontend and writes:

- `data/sar_status.json`
- `data/asf_taiwan.meta4`
- `data/copernicus_taiwan.meta4`

The frontend mainly reads `data/sar_status.json`, especially the `taiwan_frames` array.

### Deployment

`.github/workflows/update.yml` updates the data outputs and deploys the site to GitHub Pages.

## Local Usage

Run the data script:

```bash
python fetch_sar_data.py
```

Run with a limited lookback window:

```bash
DAYS_BACK=14 python fetch_sar_data.py
```

For frontend-only changes, edit `index.html`, commit, and let GitHub Pages redeploy through the workflow.

## Versioning

- Bump `APP_VERSION` in [index.html](c:/Users/saris56/work/SAR_data_monitor/index.html) for every user-visible change
- Keep the browser tab title version-free; the version should appear in the in-page header only
- Treat `APP_VERSION` and `data/sar_status.json` `version` as different things:
  - `APP_VERSION` is the frontend/app version
  - `data.version` is the generated dataset version

## Progress Summary

### UI Progress

The UI is noticeably cleaner than before:

- the highest-friction controls were regrouped
- redundant summary badges were removed
- the map is given more visual priority
- the right drawer is more readable
- export actions are less intrusive

### Data Handling Progress

The frontend now tries to reconcile incomplete records more carefully. When the local dataset contains matching entries for the same event, missing frame numbers and ASF URLs can be filled into the selected view.

## Remaining Problems

The project still has structural and data-quality limits that should be treated explicitly.

### 1. `index.html` still contains duplicated logic

There are multiple definitions of functions such as `openFrameDrawer()` and render helpers inside the same file. The last definition wins at runtime, which makes the code fragile and difficult to maintain.

Impact:

- edits can accidentally target an older inactive implementation
- regressions are easy to introduce
- behavior is harder to reason about during debugging

### 2. Some local data records are incomplete by source

The UI cannot invent an ASF link or frame number when the local dataset does not contain a valid corresponding ASF record.

Confirmed example:

- `S1A / path 105 / DESCENDING / SLC / 2026-03-31` appears in local Copernicus data
- the nearest local ASF candidate is about 12 days away
- because it is not the same acquisition event, it should not be merged

Impact:

- some drawer entries correctly remain Copernicus-only
- users may interpret this as a UI error unless the interface explains it clearly

### 3. Legacy text and encoding residue still exist

Some old strings and comments in `index.html` still contain garbled characters from previous encoding issues.

Impact:

- source readability is reduced
- future copy edits are riskier

### 4. No browser-based regression verification yet

Recent work has been validated by source inspection and local data checks, but not by automated browser tests.

Impact:

- layout edge cases may still exist on some viewport sizes
- interaction regressions can slip through

### 5. Frontend state is still centralized in one large file

Rendering, filtering, map state, drawer state, and export state are all tightly coupled.

Impact:

- small changes have wide blast radius
- onboarding is slower

## Recommended Next Steps

### Priority 1: Stabilize User-Facing Truth

1. In the right drawer, explicitly label entries as:
   - `ASF + Copernicus`
   - `Copernicus only`
   - `ASF only`
2. When `frame_number_norm` is unavailable, show a clear reason such as `No matched ASF frame metadata in local dataset`
3. Keep the current conservative merge rule. Do not merge across days just to fill missing fields.

### Priority 2: Remove Dead and Duplicate Frontend Paths

1. Deduplicate repeated functions in `index.html`
2. Keep only one active implementation for:
   - data loading
   - frame rendering
   - drawer rendering
   - export panel updates
3. Add short comments at the real active implementation boundaries

### Priority 3: Improve Maintainability

1. Split `index.html` into:
   - `index.html`
   - `styles.css`
   - `app.js`
2. Move static configuration such as satellite metadata into a dedicated module
3. Normalize text language and encoding in the source

### Priority 4: Add Lightweight Verification

1. Add a small fixture dataset for frontend-only checks
2. Add a script that verifies required fields in generated JSON
3. Add a manual QA checklist for:
   - desktop layout
   - mobile layout
   - D105 descending drawer behavior
   - export button behavior
   - legend updates

## Suggested QA Checklist

Before shipping future UI changes, verify:

1. Left filters fit in one screen on common desktop widths without unnecessary scrolling
2. The map auto-focuses correctly when filters change
3. The legend reflects the selected or visible dataset
4. The right drawer wraps long titles and remains readable
5. A known `D105 DESCENDING` Copernicus-only record does not falsely show an ASF link
6. Export actions open, close, and disable correctly

## Notes for Future Contributors

- When editing `index.html`, search for duplicate function names before changing logic
- Treat the last function definition as the active one unless the file is refactored
- Validate data-source claims against `data/sar_status.json`, not assumptions from the UI
- Prefer explicit absence messaging over aggressive fallback inference

## License

MIT
