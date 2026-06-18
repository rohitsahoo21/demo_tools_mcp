"""Mock MCP server for Prithvi closed-loop demo.

Serves every tool the Prithvi stages call, in one server:
  Stage 3: geocode, reverse_geocode
  Stage 4: screen_events, check_screening, job_submit
  Stage 5: job_status, job_plot
  (+ jobs_list)

Deploy: fastmcp deploy server.py:mcp --name prithvi-job-management
"""

import json
import uuid
import time
import base64

import requests
from fastmcp import FastMCP

mcp = FastMCP("prithvi-job-management")

# ── demo timing (low = fast demo) ───────────────────────────────────────
_JOB_DELAY = 5      # seconds a submitted job "runs" before job_status = completed
_SCREEN_DELAY = 5   # seconds screening "runs" before check_screening returns events

# ── in-memory job store (resets on restart) ─────────────────────────────
_JOBS: dict[str, dict] = {}

# ── demo result assets ──────────────────────────────────────────────────
_REPORT_URL = (
    "https://gist.githubusercontent.com/rohitsahoo21/"
    "891147be5e172f27583d4d5655669e8b/raw/"
    "b8c531bf7e533b2a8c643e3007abe2857e035275/run_report.md"
)
_FIGURE_URLS = [
    "https://i.postimg.cc/qvcFRLNR/per-crop-breakdown.png",
    "https://i.postimg.cc/HLph7yMV/pipeline-comparison.png",
]

# ── the 8 real RQ2 events returned by screening ─────────────────────────
_RQ2_EVENTS = [
    {"event_id": "NOAA_EP_129415", "state": "WI", "state_name": "Wisconsin", "year": 2018,
     "date_start": "2018-08-22", "date_end": "2018-08-22", "bbox": [-90.1278, 42.3532, -89.1666, 43.4052],
     "cdl_cropland_pct": 68.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 32,
     "hls_best_pre_date": "2018-06-05", "hls_best_post_date": "2018-08-22", "slot_index": 1,
     "crop_dates": ["2018-03-15", "2018-04-24", "2018-06-05"], "crop_clear_pcts": [88.0, 91.0, 85.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [40, 42]},
    {"event_id": "NOAA_EP_203833", "state": "IL", "state_name": "Illinois", "year": 2025,
     "date_start": "2025-07-23", "date_end": "2025-07-23", "bbox": [-89.4353, 41.5155, -87.7149, 42.3523],
     "cdl_cropland_pct": 74.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 35,
     "hls_best_pre_date": "2025-04-06", "hls_best_post_date": "2025-07-23", "slot_index": 2,
     "crop_dates": ["2025-01-09", "2025-02-25", "2025-04-06"], "crop_clear_pcts": [86.0, 90.0, 88.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [47, 40]},
    {"event_id": "NOAA_EP_158305", "state": "IN", "state_name": "Indiana", "year": 2021,
     "date_start": "2021-06-16", "date_end": "2021-06-16", "bbox": [-87.6589, 38.7129, -85.2288, 40.2622],
     "cdl_cropland_pct": 71.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 30,
     "hls_best_pre_date": "2021-04-12", "hls_best_post_date": "2021-06-16", "slot_index": 3,
     "crop_dates": ["2021-01-12", "2021-03-03", "2021-04-12"], "crop_clear_pcts": [85.0, 89.0, 87.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [50, 40]},
    {"event_id": "NOAA_EP_172019", "state": "IL", "state_name": "Illinois", "year": 2022,
     "date_start": "2022-07-24", "date_end": "2022-07-24", "bbox": [-90.4567, 38.106, -89.4387, 39.2971],
     "cdl_cropland_pct": 77.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 36,
     "hls_best_pre_date": "2022-03-26", "hls_best_post_date": "2022-07-24", "slot_index": 4,
     "crop_dates": ["2022-01-05", "2022-02-14", "2022-03-26"], "crop_clear_pcts": [84.0, 88.0, 90.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [40, 40]},
    {"event_id": "NOAA_EP_141424", "state": "ND", "state_name": "North Dakota", "year": 2019,
     "date_start": "2019-09-22", "date_end": "2019-09-22", "bbox": [-99.7912, 47.1947, -96.9759, 49.1023],
     "cdl_cropland_pct": 62.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 28,
     "hls_best_pre_date": "2019-07-15", "hls_best_post_date": "2019-09-22", "slot_index": 5,
     "crop_dates": ["2019-04-26", "2019-06-05", "2019-07-15"], "crop_clear_pcts": [83.0, 87.0, 86.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [40, 40]},
    {"event_id": "NOAA_EP_184328", "state": "IL", "state_name": "Illinois", "year": 2023,
     "date_start": "2023-07-04", "date_end": "2023-07-04", "bbox": [-88.2399, 41.501, -87.483, 42.2749],
     "cdl_cropland_pct": 75.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 34,
     "hls_best_pre_date": "2023-04-09", "hls_best_post_date": "2023-07-04", "slot_index": 6,
     "crop_dates": ["2023-01-10", "2023-02-19", "2023-04-09"], "crop_clear_pcts": [85.0, 89.0, 88.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [40, 49]},
    {"event_id": "SD_SIOUX_2024", "state": "SD", "state_name": "South Dakota", "year": 2024,
     "date_start": "2024-06-24", "date_end": "2024-06-24", "bbox": [-97.15, 42.5, -96.41, 43.14],
     "cdl_cropland_pct": 66.0, "event_name": "Flood", "damage_total_usd": None, "n_hls_clean": 31,
     "hls_best_pre_date": "2024-06-16", "hls_best_post_date": "2024-06-24", "slot_index": 7,
     "crop_dates": ["2024-02-11", "2024-04-13", "2024-06-16"], "crop_clear_pcts": [84.0, 88.0, 90.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [62, 64]},
    {"event_id": "SPAIN_VALENCIA_2024", "state": "Valencia", "state_name": "Valencia (Spain)", "year": 2024,
     "date_start": "2024-10-30", "date_end": "2024-10-30", "bbox": [-0.45, 39.15, -0.32, 39.47],
     "cdl_cropland_pct": None, "event_name": "Flood (DANA)", "damage_total_usd": None, "n_hls_clean": 33,
     "hls_best_pre_date": "2024-08-10", "hls_best_post_date": "2024-10-30", "slot_index": 8,
     "crop_dates": ["2024-03-05", "2024-05-30", "2024-08-10"], "crop_clear_pcts": [86.0, 89.0, 87.0],
     "crop_collections": ["HLSS30", "HLSL30", "HLSS30"], "crop_gap_days": [86, 72]},
]

# ── task helpers for async screening ────────────────────────────────────
def _encode_task(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_task(task_id: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(task_id.encode()))


# ── geocoding (Stage 3) ─────────────────────────────────────────────────
_NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
_GEO_HEADERS = {"User-Agent": "prithvi-workshop-agent/1.0"}
_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "puerto rico": "PR", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


# ── Stage 4: screening ──────────────────────────────────────────────────
@mcp.tool()
def screen_events(
    hazard_type: str = "flood",
    kept_event_ids: list[str] = [],
    rejected_event_ids: list[str] = [],
    region: str | None = None,
    year_range: list[int] | None = None,
    bbox: list[float] | None = None,
    min_cropland_pct: float | None = None,
    prefer_diverse_states: bool = True,
    max_events: int = 8,
) -> str:
    """Start screening flood/burn events. Returns a task_id IMMEDIATELY (no
    events on this call). Tell the user screening has started and to check
    back; then call check_screening with the task_id."""
    task_id = _encode_task({"t": time.time(), "max_events": max(1, min(20, max_events))})
    return json.dumps({
        "status": "running",
        "task_id": task_id,
        "eta_seconds": _SCREEN_DELAY,
        "message": "Screening started — tell the user it's running, then call check_screening with this task_id.",
    })


@mcp.tool()
def check_screening(task_id: str) -> str:
    """Poll a screening job started by screen_events. Returns 'running' until
    done, then 'completed' with the 'events' list."""
    try:
        job = _decode_task(task_id)
    except Exception:
        return json.dumps({"status": "unknown", "message": f"Invalid task_id '{task_id}'."})

    remaining = _SCREEN_DELAY - (time.time() - job["t"])
    if remaining > 0:
        return json.dumps({"status": "running", "seconds_remaining": round(remaining),
                           "message": "Still screening — check again shortly."})

    target = job.get("max_events", 8)
    events = _RQ2_EVENTS[:target] if target and target < len(_RQ2_EVENTS) else _RQ2_EVENTS
    return json.dumps({
        "status": "completed",
        "task_id": task_id,
        "events": events,
        "slots_filled": len(events),
        "total_candidates": len(_RQ2_EVENTS),
        "source": "catalog",
        "message": f"Screened {len(events)} flood event(s): 7 CONUS + 1 Spain (Valencia). [MOCK]",
    })


@mcp.tool()
def job_submit(payload: dict) -> str:
    """Submit a job; returns job_id and echoes the config received."""
    job_id = str(uuid.uuid4())[:8]
    _JOBS[job_id] = {
        "job_id": job_id,
        "started_at": time.time(),
        "payload": payload,
        "workspace_name": payload.get("output", {}).get("dir", ""),
    }
    return json.dumps({
        "job_id": job_id,
        "workspace_name": payload.get("output", {}).get("dir", ""),
        "config_received": payload,
    })


# ── Stage 5: status + plots ─────────────────────────────────────────────
@mcp.tool()
def job_status(job_id: str) -> str:
    """Return 'running' until _JOB_DELAY seconds elapse, then 'completed'."""
    job = _JOBS.get(job_id)
    if not job:
        return json.dumps({"job_id": job_id, "status": "completed"})
    elapsed = time.time() - job.get("started_at", 0)
    status = "completed" if elapsed >= _JOB_DELAY else "running"
    return json.dumps({"job_id": job_id, "status": status})


@mcp.tool()
def job_plot(job_id: str, workspace_name: str = "", user_name: str = "") -> str:
    """Get figure URLs and report for a completed job."""
    return json.dumps({
        "job_id": job_id,
        "report_url": _REPORT_URL,
        "figures": _FIGURE_URLS,
    })


@mcp.tool()
def jobs_list(filter: str = "all") -> str:
    """List all submitted jobs with computed status."""
    jobs = []
    for j in _JOBS.values():
        elapsed = time.time() - j.get("started_at", 0)
        jobs.append({
            "job_id": j["job_id"],
            "status": "completed" if elapsed >= _JOB_DELAY else "running",
            "workspace_name": j.get("workspace_name", ""),
        })
    return json.dumps({"jobs": jobs})


# ── Stage 3: geocoding ──────────────────────────────────────────────────
@mcp.tool()
def geocode(query: str) -> str:
    """Convert a place name to a bbox [west, south, east, north]."""
    params = {"q": query, "format": "json", "limit": 5}
    try:
        resp = requests.get(_NOMINATIM_SEARCH, params=params, headers=_GEO_HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        return json.dumps({"message": f"Geocoding service unavailable: {e}"})
    finally:
        time.sleep(1)

    if not results:
        return json.dumps({"message": f"No results for '{query}'."})

    def _bbox(r):
        bb = r["boundingbox"]  # [south, north, west, east]
        return [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]

    if len(results) == 1:
        return json.dumps({"bbox": _bbox(results[0]),
                           "display_name": results[0]["display_name"], "message": "ok"})
    return json.dumps({
        "candidates": [{"display_name": r["display_name"], "bbox": _bbox(r)} for r in results[:3]],
        "message": "Multiple matches found. Please choose one.",
    })


@mcp.tool()
def reverse_geocode(bbox: list[float]) -> str:
    """Convert a bbox [west, south, east, north] to US state/county/location."""
    west, south, east, north = bbox
    lat, lon = (south + north) / 2, (west + east) / 2
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 5, "addressdetails": 1}
    try:
        resp = requests.get(_NOMINATIM_REVERSE, params=params, headers=_GEO_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return json.dumps({"message": f"Reverse geocoding service unavailable: {e}"})
    finally:
        time.sleep(1)

    if "error" in data:
        return json.dumps({"message": f"No results for centroid ({lat}, {lon})."})

    addr = data.get("address", {})
    state_name = addr.get("state", "")
    return json.dumps({
        "state": _NAME_TO_CODE.get(state_name.lower()),
        "state_name": state_name or None,
        "county": addr.get("county") or None,
        "country": addr.get("country") or None,
        "display_name": data.get("display_name"),
        "centroid_lat": round(lat, 4), "centroid_lon": round(lon, 4),
        "message": "ok",
    })
