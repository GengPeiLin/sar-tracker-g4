# SAR Tracker — Taiwan Satellite Acquisition Dashboard

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen)](https://gengpeilin.github.io/sar-tracker-g4/)
[![Data Update](https://github.com/GengPeiLin/sar-tracker-g4/actions/workflows/update.yml/badge.svg)](https://github.com/GengPeiLin/sar-tracker-g4/actions/workflows/update.yml)

An interactive dashboard for tracking SAR (Synthetic Aperture Radar) satellite acquisitions over Taiwan. Data is fetched daily from ASF DAAC and Copernicus CDSE and served as a zero-dependency static site via GitHub Pages.

**[Live site → gengpeilin.github.io/sar-tracker-g4](https://gengpeilin.github.io/sar-tracker-g4/)**

---

## Features

- **Interactive map** — Leaflet.js map displaying satellite acquisition footprint polygons; click any frame to open a detailed metadata drawer
- **Multi-mission coverage** — 27 satellites across C, L, X, and S bands (22 operational)
- **Advanced filtering** — filter by satellite, orbit direction, date range, track number, frame number, product type, and frequency band
- **Data export** — ASF .meta4 and Copernicus .meta4 for batch download managers, CSV export, and one-click URL copy
- **Appearance settings** — 4 themes (Soft Slate / Night Ops / Paper Radar / Field Survey) and font-size options, persisted to localStorage
- **Mobile feed** — condensed frame list optimized for small screens
- **Daily auto-update** — GitHub Actions fetches fresh data every day and redeploys automatically

---

## Data Sources

| Source | API | Datasets |
|--------|-----|----------|
| [ASF DAAC](https://asf.alaska.edu/) | `api.daac.asf.alaska.edu` | Sentinel-1 (SLC, GRD variants), NISAR |
| [Copernicus CDSE](https://dataspace.copernicus.eu/) | `catalogue.dataspace.copernicus.eu` | Sentinel-1 (all product types) |

**Coverage area:** `POLYGON((119 21, 123 21, 123 26.5, 119 26.5, 119 21))`

**Focus tracks:**
- `A69` — Sentinel-1 ascending pass, path 69
- `D105` — Sentinel-1 descending pass, path 105
- `NISAR` — all NISAR passes
- `OTHER_S1` — remaining Sentinel-1 passes over Taiwan

---

## Satellites Covered

| Satellite | Agency | Band | Status |
|-----------|--------|------|--------|
| Sentinel-1A / 1C / 1D | ESA | C | Operational |
| Sentinel-1B | ESA | C | Retired (2021) |
| NISAR | NASA / ISRO | L | Operational |
| ALOS-2 / ALOS-4 | JAXA | L | Operational |
| SAOCOM-1A / 1B | CONAE | L | Operational |
| RADARSAT-2 | CSA | C | Operational |
| RCM-1 / 2 / 3 | CSA | C | Operational |
| COSMO-SkyMed SG-1 / 2 | ASI | X | Operational (commercial) |
| TerraSAR-X / TanDEM-X | DLR / Airbus | X | Operational (commercial) |
| ICEYE / Capella / Umbra / Synspective | Various | X | Operational (commercial) |
| NovaSAR-1 | SSTL / UKSA | S | Operational |
| ERS-1 / ERS-2 / ALOS-1 | ESA / JAXA | C / L | Retired |

---

## Project Structure

```
sar-tracker-g4/
├── index.html                  # Single-file web app (UI + CSS + JS, no build step)
├── fetch_sar_data.py           # Python data fetcher (ASF + Copernicus APIs)
├── data/
│   ├── sar_status.json         # Current SAR inventory (~18,000 frames)
│   ├── catalog_db.json         # Full persistent catalog (all historical frames)
│   ├── asf_taiwan.meta4        # Metalink4 file for ASF batch downloads
│   └── copernicus_taiwan.meta4 # Metalink4 file for Copernicus batch downloads
└── .github/workflows/
    ├── update.yml              # Daily data fetch + automatic Pages deployment
    └── deploy-pages.yml        # Manual GitHub Pages deployment trigger
```

---

## Local Development

No build tools required — open the file directly or serve it locally:

```bash
git clone https://github.com/GengPeiLin/sar-tracker-g4.git
cd sar-tracker-g4

# Recommended: serve locally to avoid fetch CORS issues
python -m http.server 8080
# Then open http://localhost:8080 in your browser
```

---

## Data Update

### Automatic
GitHub Actions runs daily at **UTC 02:00 (Taiwan time 10:00)** and commits updated data files to `main`, which triggers a redeployment.

### Manual

```bash
pip install requests
python fetch_sar_data.py

# Optional environment variables:
# DAYS_BACK=30          fetch data from the past 30 days (default: 7)
# FULL_REBUILD=true     rebuild the full catalog from Sentinel-1 launch (2014-04-03)
```

Output files:
- `data/sar_status.json` — frame inventory consumed by the frontend
- `data/catalog_db.json` — persistent catalog including all historical records

---

## Deployment

The site is hosted on **GitHub Pages**:

- **Branch:** `main`, **folder:** `/` (root)
- Redeployment is triggered automatically after each data update
- To deploy manually: GitHub → Actions → `deploy-pages` → Run workflow

---

## Dependencies

**Frontend** (all loaded from CDN, nothing to install):
- [Leaflet.js 1.9.4](https://leafletjs.com/) — interactive map
- IBM Plex Mono, Noto Sans TC (Google Fonts)

**Python script:**
- `requests` — the only external dependency

---

## License

No license has been set for this project. Please contact the author before reusing code or data.
