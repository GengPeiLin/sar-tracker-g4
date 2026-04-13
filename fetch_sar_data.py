#!/usr/bin/env python3
"""
Fetch Sentinel-1 and NISAR SAR inventory for the Taiwan dashboard.

Storage model:
  1. Build and keep a local metadata catalog in data/catalog_db.json
  2. Export the current merged catalog to data/sar_status.json
  3. After bootstrap, only fetch data newer than the recorded watermark

Output:
  data/catalog_db.json
  data/sar_status.json
  data/asf_taiwan.meta4
  data/copernicus_taiwan.meta4
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

__version__ = datetime.now(timezone.utc).strftime("%Y-%m-%d")


DAYS_BACK = int(os.environ.get("DAYS_BACK", "7"))
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "1000"))
TAIWAN_WKT = "POLYGON((119 21,123 21,123 26.5,119 26.5,119 21))"
NISAR_LAUNCH = datetime(2024, 3, 1, tzinfo=timezone.utc)

OUTPUT_DIR = Path(__file__).parent / "data"
CATALOG_FILE = OUTPUT_DIR / "catalog_db.json"
JSON_FILE = OUTPUT_DIR / "sar_status.json"
ASF_META4 = OUTPUT_DIR / "asf_taiwan.meta4"
COP_META4 = OUTPUT_DIR / "copernicus_taiwan.meta4"
S1_EARLIEST = datetime(2014, 4, 3, tzinfo=timezone.utc)
INCREMENTAL_OVERLAP_DAYS = int(os.environ.get("INCREMENTAL_OVERLAP_DAYS", "2"))
FORCE_FULL_REBUILD = os.environ.get("FORCE_FULL_REBUILD", "").lower() in {"1", "true", "yes"}


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def http_json(url: str, timeout: int = 60) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "sar-tracker/3.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        log(f"HTTP {exc.code}: {url[:120]}")
    except Exception as exc:
        log(f"Request failed: {exc}")
    return None


def chunk_range(start: datetime, end: datetime, days: int) -> list[tuple[datetime, datetime]]:
    chunks: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks


def load_catalog() -> dict:
    if not CATALOG_FILE.exists() or FORCE_FULL_REBUILD:
        return {
            "version": __version__,
            "updated_at": "",
            "last_successful_fetch": "",
            "bootstrap_completed": False,
            "frames": [],
        }
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": __version__,
            "updated_at": "",
            "last_successful_fetch": "",
            "bootstrap_completed": False,
            "frames": [],
        }


def save_catalog(payload: dict) -> None:
    CATALOG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_asf(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SUTC")


def fmt_odata(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def normalize_direction(value: str) -> str:
    text = str(value or "").upper()
    if text.startswith("A"):
        return "ASCENDING"
    if text.startswith("D"):
        return "DESCENDING"
    return "UNKNOWN"


def safe_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def infer_product_type(*values: str) -> str:
    known = [
        "L1_RSLC",
        "L1_GSLC",
        "L2_GCOV",
        "L2_GUNW",
        "GSLC",
        "RSLC",
        "SLC",
        "GRD_HD",
        "GRD_MS",
        "GRD_HS",
        "GRD_FD",
        "GRD",
        "GCOV",
        "GUNW",
        "RAW",
        "SSC",
    ]
    for raw in values:
        text = str(raw or "").upper().replace(".SAFE", "")
        for item in known:
            if item in text:
                return item
    return "UNKNOWN"


def track_label(satellite_id: str, direction: str, path_number: int | None) -> str:
    sat = str(satellite_id or "").upper()
    if "NISAR" in sat:
        return "NISAR"
    if direction == "ASCENDING" and path_number == 69:
        return "A69"
    if direction == "DESCENDING" and path_number == 105:
        return "D105"
    return "OTHER_S1"


def wkt_to_geojson(wkt: str):
    text = str(wkt or "")
    if not text.startswith("POLYGON(("):
        return wkt
    try:
        points = []
        for pair in text.replace("POLYGON((", "").replace("))", "").split(","):
            lon, lat = pair.strip().split()
            points.append([float(lon), float(lat)])
        return {"type": "Polygon", "coordinates": [points]}
    except Exception:
        return wkt


def asf_search(dataset: str, start: datetime, end: datetime, processing_levels: str) -> list[dict]:
    params = {
        "intersectsWith": TAIWAN_WKT,
        "dataset": dataset,
        "start": fmt_asf(start),
        "end": fmt_asf(end),
        "processingLevel": processing_levels,
        "output": "geojson",
        "maxresults": MAX_RESULTS,
    }
    url = "https://api.daac.asf.alaska.edu/services/search/param?" + urllib.parse.urlencode(params)
    payload = http_json(url)
    return payload.get("features", []) if payload and "features" in payload else []


def asf_search_windowed(dataset: str, start: datetime, end: datetime, processing_levels: str, chunk_days: int) -> list[dict]:
    features: list[dict] = []
    for chunk_start, chunk_end in chunk_range(start, end, chunk_days):
        log(f"ASF {dataset}: {chunk_start.date()} -> {chunk_end.date()}")
        features.extend(asf_search(dataset, chunk_start, chunk_end, processing_levels))
    return features


def process_asf_feature(feature: dict) -> dict:
    props = feature.get("properties", {})
    platform = props.get("platform", "")
    direction = normalize_direction(props.get("flightDirection", ""))
    path_number = safe_int(props.get("pathNumber"))
    return {
        "source": "ASF",
        "granule": props.get("sceneName", ""),
        "platform": platform,
        "sensor": props.get("sensor", ""),
        "date": props.get("startTime", ""),
        "stop_time": props.get("stopTime", ""),
        "mode": props.get("beamModeType") or props.get("beamMode", ""),
        "polarization": props.get("polarization", ""),
        "orbit": props.get("orbit", ""),
        "path_number": props.get("pathNumber", ""),
        "frame_number": props.get("frameNumber", ""),
        "direction": direction,
        "product_type": infer_product_type(props.get("processingLevel"), props.get("sceneName", "")),
        "processing_level": props.get("processingLevel", ""),
        "footprint": feature.get("geometry"),
        "asf_url": props.get("url", ""),
        "download_url": "",
        "copernicus_url": "",
        "browse_url": (props.get("browse") or [None])[0] if isinstance(props.get("browse"), list) else props.get("browse", ""),
        "file_size_mb": round(float(props.get("sizeMB") or 0), 1),
        "satellite_id": platform,
        "track_label": track_label(platform, direction, path_number),
    }


def fetch_asf_frames(s1_start: datetime, nisar_start: datetime, end: datetime, bootstrap: bool) -> list[dict]:
    log("Fetching ASF Sentinel-1 inventory")
    sentinel = asf_search_windowed(
        "SENTINEL-1",
        s1_start,
        end,
        "SLC,GRD_HD,GRD_MS,GRD_HS,GRD_FD,GRD",
        30 if bootstrap else 14,
    )
    log(f"ASF Sentinel-1 features: {len(sentinel)}")

    log(f"Fetching ASF NISAR inventory since {nisar_start.date()}")
    nisar = asf_search_windowed(
        "NISAR",
        nisar_start,
        end,
        "RSLC,GSLC,GCOV,GUNW,L1_RSLC,L1_GSLC,L2_GCOV,L2_GUNW",
        30 if bootstrap else 14,
    )
    log(f"ASF NISAR features: {len(nisar)}")

    return [process_asf_feature(feature) for feature in [*sentinel, *nisar]]


def fetch_copernicus_frames(start: datetime, end: datetime, bootstrap: bool) -> list[dict]:
    log("Fetching Copernicus Sentinel-1 inventory")
    frames: list[dict] = []
    for chunk_start, chunk_end in chunk_range(start, end, 30 if bootstrap else 14):
        query = (
            f"OData.CSC.Intersects(area=geography'SRID=4326;{TAIWAN_WKT}')"
            f" and Collection/Name eq 'SENTINEL-1'"
            f" and ContentDate/Start gt {fmt_odata(chunk_start)}"
            f" and ContentDate/Start lt {fmt_odata(chunk_end)}"
        )
        params = {
            "$filter": query,
            "$orderby": "ContentDate/Start desc",
            "$top": min(MAX_RESULTS, 1000),
            "$expand": "Attributes",
        }
        url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?" + urllib.parse.urlencode(params)
        payload = http_json(url, timeout=90)
        if not payload or "value" not in payload:
            continue

        for item in payload["value"]:
            attrs = {attr["Name"]: attr.get("Value", "") for attr in item.get("Attributes", [])}
            platform = str(item.get("Name", "")).split("_")[0]
            direction = normalize_direction(attrs.get("orbitDirection", ""))
            path_number = safe_int(attrs.get("relativeOrbitNumber"))
            product_id = item.get("Id", "")
            frames.append(
                {
                    "source": "Copernicus",
                    "granule": str(item.get("Name", "")).replace(".SAFE", ""),
                    "platform": platform,
                    "sensor": "C-SAR",
                    "date": item.get("ContentDate", {}).get("Start", ""),
                    "stop_time": item.get("ContentDate", {}).get("End", ""),
                    "mode": str(item.get("Name", "")).split("_")[1] if "_" in str(item.get("Name", "")) else "",
                    "polarization": attrs.get("polarisationChannels", ""),
                    "orbit": attrs.get("relativeOrbitNumber", ""),
                    "path_number": attrs.get("relativeOrbitNumber", ""),
                    "frame_number": attrs.get("frameNumber", ""),
                    "direction": direction,
                    "product_type": infer_product_type(item.get("Name", "")),
                    "processing_level": infer_product_type(item.get("Name", "")),
                    "footprint": wkt_to_geojson(item.get("GeoFootprint") or item.get("Footprint")),
                    "asf_url": "",
                    "download_url": f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value" if product_id else "",
                    "copernicus_url": f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value" if product_id else "",
                    "browse_url": "",
                    "file_size_mb": round((item.get("ContentLength") or 0) / 1_000_000, 1),
                    "satellite_id": platform,
                    "track_label": track_label(platform, direction, path_number),
                }
            )
    log(f"Copernicus Sentinel-1 products: {len(frames)}")
    return frames


def scene_key(frame: dict) -> str:
    granule = str(frame.get("granule", "")).replace(".SAFE", "").strip().upper()
    if granule:
        return granule
    return "|".join(
        [
            frame.get("platform", ""),
            frame.get("date", ""),
            frame.get("direction", ""),
            str(frame.get("path_number", "")),
            str(frame.get("frame_number", "")),
            frame.get("product_type", ""),
        ]
    )


def merge_frames(frames: list[dict]) -> list[dict]:
    def source_rank(item: dict) -> int:
        return 0 if item.get("source") == "ASF" else 1

    merged: dict[str, dict] = {}
    for frame in sorted(frames, key=source_rank):
        key = scene_key(frame)
        current = merged.get(key)
        if not current:
            merged[key] = dict(frame)
            continue

        if current.get("source") != "ASF" and frame.get("source") == "ASF":
            preferred = dict(frame)
            preferred["download_url"] = preferred.get("download_url") or current.get("download_url")
            preferred["copernicus_url"] = preferred.get("copernicus_url") or current.get("copernicus_url")
            preferred["browse_url"] = preferred.get("browse_url") or current.get("browse_url")
            preferred["file_size_mb"] = preferred.get("file_size_mb") or current.get("file_size_mb")
            merged[key] = preferred
            current = merged[key]

        current["asf_url"] = current.get("asf_url") or frame.get("asf_url")
        current["download_url"] = current.get("download_url") or frame.get("download_url")
        current["copernicus_url"] = current.get("copernicus_url") or frame.get("copernicus_url")
        current["browse_url"] = current.get("browse_url") or frame.get("browse_url")
        current["file_size_mb"] = current.get("file_size_mb") or frame.get("file_size_mb")
        current["frame_number"] = current.get("frame_number") or frame.get("frame_number")
        current["path_number"] = current.get("path_number") or frame.get("path_number")
        current["direction"] = current.get("direction") or frame.get("direction")
    return sorted(merged.values(), key=lambda item: item.get("date", ""), reverse=True)


def write_meta4(frames: list[dict], target: Path, source: str) -> None:
    selected = [frame for frame in frames if (frame.get("asf_url") if source == "ASF" else frame.get("download_url"))]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<metalink xmlns="urn:ietf:params:xml:ns:metalink">',
        f'  <!-- generated {datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")} -->',
        f'  <!-- {len(selected)} scenes -->',
    ]
    for frame in selected:
        url = frame.get("asf_url") if source == "ASF" else frame.get("download_url")
        name = f'{frame.get("granule", "scene")}{".SAFE.zip" if source == "Copernicus" else ""}'
        size = int(float(frame.get("file_size_mb") or 0) * 1_000_000)
        lines.append(f'  <file name="{name}">')
        if size:
            lines.append(f"    <size>{size}</size>")
        lines.append(f"    <url priority=\"1\">{url}</url>")
        lines.append("  </file>")
    lines.append("</metalink>")
    target.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog()
    bootstrap = FORCE_FULL_REBUILD or not catalog.get("bootstrap_completed")

    if bootstrap:
        s1_start = S1_EARLIEST
        nisar_start = NISAR_LAUNCH
        cop_start = S1_EARLIEST
        existing_frames: list[dict] = []
        log("Starting full metadata bootstrap")
    else:
        last_success = catalog.get("last_successful_fetch")
        try:
            watermark = datetime.fromisoformat(last_success)
        except Exception:
            watermark = now - timedelta(days=DAYS_BACK)
        incremental_start = watermark - timedelta(days=INCREMENTAL_OVERLAP_DAYS)
        s1_start = incremental_start
        nisar_start = max(incremental_start, NISAR_LAUNCH)
        cop_start = incremental_start
        existing_frames = catalog.get("frames", [])
        log(f"Starting incremental update from {incremental_start.isoformat()}")

    asf_frames = fetch_asf_frames(s1_start, nisar_start, now, bootstrap)
    cop_frames = fetch_copernicus_frames(cop_start, now, bootstrap)

    # Only update watermark if at least one source returned data
    asf_ok = len(asf_frames) > 0
    cop_ok = len(cop_frames) > 0
    if not asf_ok:
        log("WARNING: ASF returned 0 frames — watermark will not advance")
    if not cop_ok:
        log("WARNING: Copernicus returned 0 frames — watermark will not advance")

    all_frames = merge_frames([*existing_frames, *asf_frames, *cop_frames])

    # Guard: skip overwrite if merged result is empty but catalog had data
    if len(all_frames) == 0 and len(existing_frames) > 0:
        log("ERROR: Merged frame count is 0 but catalog had data — aborting write to prevent data loss")
        return 1

    track_summary: dict[str, int] = {}
    satellite_summary: dict[str, int] = {}
    for frame in all_frames:
        track_summary[frame["track_label"]] = track_summary.get(frame["track_label"], 0) + 1
        satellite_summary[frame["platform"]] = satellite_summary.get(frame["platform"], 0) + 1

    # Only advance watermark if both sources succeeded
    fetch_timestamp = now.isoformat() if (asf_ok and cop_ok) else catalog.get("last_successful_fetch", now.isoformat())

    catalog_payload = {
        "version": __version__,
        "updated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "last_successful_fetch": fetch_timestamp,
        "bootstrap_completed": True,
        "bootstrap_started_at": catalog.get("bootstrap_started_at") or (s1_start.isoformat() if bootstrap else catalog.get("bootstrap_started_at")),
        "incremental_overlap_days": INCREMENTAL_OVERLAP_DAYS,
        "frames": all_frames,
    }
    save_catalog(catalog_payload)

    payload = {
        "version": __version__,
        "updated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "query_start": s1_start.isoformat(),
        "query_end": now.isoformat(),
        "days_back": DAYS_BACK if not bootstrap else None,
        "bootstrap_completed": True,
        "last_successful_fetch": fetch_timestamp,
        "total_frames": len(all_frames),
        "asf_count": len([frame for frame in all_frames if frame.get("asf_url")]),
        "copernicus_count": len([frame for frame in all_frames if frame.get("download_url")]),
        "focus_tracks": ["A69", "D105", "NISAR", "OTHER_S1"],
        "track_summary": track_summary,
        "satellite_summary": satellite_summary,
        "taiwan_frames": all_frames,
    }

    JSON_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_meta4(all_frames, ASF_META4, "ASF")
    write_meta4(all_frames, COP_META4, "Copernicus")
    log(f"Wrote {JSON_FILE.name} with {len(all_frames)} scenes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
