# TODO — SAR Tracker Bug Fixes

Functional issues identified during code review. No appearance/styling changes.

## index.html

### Bug

- [x] **Duplicate HTML IDs** — removed IDs from static template; `setupReadableUI()` and `rebuildDownloadBar()` own the canonical elements
- [x] **`liveFetchASF()` missing `response.ok` check** — added error throw on non-2xx response
- [x] **`updateStats` DOM access without null check** — `st-frames`, `st-sats`, `st-period` now guarded
- [x] **`openFrameDrawer` / `openDrawer` DOM access without null check** — `d-name`, `d-agency`, `d-week-wrap`, `d-grid`, `d-desc`, `drawer` all guarded
- [x] **`loadData` `hdr-time` access without null check** — guarded

### Dead Code

- [x] **`state.frames` dead assignment** — removed

## fetch_sar_data.py

### Logic Error

- [x] **Partial fetch marked as full success** — watermark only advances when both ASF and Copernicus return data

### Data Integrity

- [x] **Empty result can overwrite catalog** — write aborted with error log if merged count is 0 and catalog had prior data
