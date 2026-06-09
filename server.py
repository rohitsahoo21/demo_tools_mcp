"""Mock MCP server for Prithvi experiment job management.

Simulates the Temporal-based job management system that Stage 4 and Stage 5
agents interact with. Implements the same tool spec as the production server:
- job_submit: accepts experiment payload, returns a job_id
- job_status: checks if a job is finished
- job_plot: returns figure URLs for a completed job
- jobs_list: lists all submitted jobs

Deploy: fastmcp deploy server.py:mcp --name prithvi-job-management
"""

import json
import uuid

from fastmcp import FastMCP

mcp = FastMCP("prithvi-job-management")

# In-memory job store (resets on server restart)
_JOBS: dict[str, dict] = {}

# Demo result assets
_REPORT_URL = (
    "https://gist.githubusercontent.com/rohitsahoo21/"
    "891147be5e172f27583d4d5655669e8b/raw/"
    "b8c531bf7e533b2a8c643e3007abe2857e035275/run_report.md"
)
_FIGURE_URLS = [
    "https://i.postimg.cc/qvcFRLNR/per-crop-breakdown.png",
    "https://i.postimg.cc/HLph7yMV/pipeline-comparison.png",
]

import time

_JOB_DELAY = 60   # seconds the mock job "runs" before completing (0 = instant)


@mcp.tool()
def job_submit(payload: dict) -> str:
    """Submit a job; returns job_id and echoes the config received."""
    job_id = str(uuid.uuid4())[:8]
    _JOBS[job_id] = {
        "job_id": job_id,
        "started_at": time.time(),          # <-- stamp submit time
        "payload": payload,
        "workspace_name": payload.get("output", {}).get("dir", ""),
    }
    return json.dumps({
        "job_id": job_id,
        "workspace_name": payload.get("output", {}).get("dir", ""),
        "config_received": payload,
    })


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
    """Get figure URLs and report for a completed job.

    Args:
        job_id: The job ID to fetch plots for.
        workspace_name: Workspace name (used by production server to locate outputs).
        user_name: User name (used by production server for auth/routing).

    In production, this reads from the experiment output directory
    or object storage where Prithvi results are saved.
    For the mock, returns demo figure URLs and a report link.
    """
    return json.dumps({
        "job_id": job_id,
        "report_url": _REPORT_URL,
        "figures": _FIGURE_URLS,
    })


@mcp.tool()
def jobs_list(filter: str = "all") -> str:
    """List all jobs in the system.

    Args:
        filter: Optional filter — "all" (default) returns everything.

    Returns all submitted jobs with their IDs, status, and metadata.
    """
    jobs = [
        {
            "job_id": j["job_id"],
            "status": j["status"],
            "workspace_name": j.get("workspace_name", ""),
        }
        for j in _JOBS.values()
    ]
    return json.dumps({"jobs": jobs})


# ── add to imports ──────────────────────────────────────────────────────
import time
import base64
import random

# ── config + helpers (no storage) ───────────────────────────────────────
_STATE_BBOX = {
    "IA": ([-96.83, 42.02, -94.89, 43.70], "Iowa"),
    "IL": ([-90.20, 39.80, -88.30, 41.40], "Illinois"),
    "IN": ([-87.20, 39.50, -85.30, 41.00], "Indiana"),
    "KS": ([-98.50, 38.00, -96.50, 39.50], "Kansas"),
    "MN": ([-95.50, 43.80, -93.50, 45.40], "Minnesota"),
    "MO": ([-93.80, 38.50, -91.90, 40.10], "Missouri"),
    "NE": ([-98.76, 40.06, -95.43, 43.03], "Nebraska"),
    "ND": ([-98.20, 46.50, -96.30, 48.00], "North Dakota"),
    "OH": ([-84.20, 39.80, -82.30, 41.30], "Ohio"),
    "SD": ([-99.73, 43.30, -96.25, 44.63], "South Dakota"),
}

_SCREEN_DELAY = 60   # seconds the mock pretends screening takes (adjust to taste)


def _encode_task(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_task(task_id: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(task_id.encode()))


# ── screen_events: starts screening, returns a task_id immediately ──────
@mcp.tool
def screen_events(
    hazard_type: str = "flood",
    kept_event_ids: list[str] = [],
    rejected_event_ids: list[str] = [],
    region: str | None = None,
    year_range: list[int] | None = None,
    bbox: list[float] | None = None,
    min_cropland_pct: float | None = None,
    prefer_diverse_states: bool = True,
    max_events: int = 5,
) -> str:
    """Start screening flood/burn events for the Prithvi pipeline. Returns a
    task_id IMMEDIATELY — it does NOT return events on this call. Screening
    runs in the background (catalog + NOAA discovery + HLS/cropland/crop-date
    verification) and takes several minutes. Tell the user screening has
    started and they can ask you to check on it; then call ``check_screening``
    with the returned task_id when the user asks. ``max_events`` controls the
    count (default 5, max 20). Filters by region (US state), year_range, bbox,
    and min cropland %. Supports refinement via kept/rejected_event_ids."""
    task_id = _encode_task({
        "t": time.time(),
        "hazard_type": hazard_type,
        "region": region,
        "year_range": year_range or [2017, 2025],
        "max_events": max(1, min(20, max_events)),
        "min_cropland_pct": min_cropland_pct,
    })
    return json.dumps({
        "status": "running",
        "task_id": task_id,
        "eta_seconds": _SCREEN_DELAY,
        "message": (
            f"Screening started (~{max(1, _SCREEN_DELAY // 60)} min). "
            f"Tell the user it's running and to check back shortly; then call "
            f"check_screening with this task_id."
        ),
    })


# ── check_screening: poll a screening job (stateless, decodes task_id) ──
@mcp.tool
def check_screening(task_id: str) -> str:
    """Poll a screening job started by ``screen_events`` using its task_id.
    Returns status 'running' (with seconds_remaining) until screening is done,
    then 'completed' with the 'events' list. Call this only when the user asks
    to check on screening — do not poll continuously."""
    try:
        job = _decode_task(task_id)
    except Exception:
        return json.dumps({
            "status": "unknown",
            "message": f"Invalid or unknown task_id '{task_id}'.",
        })

    remaining = _SCREEN_DELAY - (time.time() - job["t"])
    if remaining > 0:
        return json.dumps({
            "status": "running",
            "seconds_remaining": round(remaining),
            "message": "Still screening — ask me to check again shortly.",
        })

    lo, hi = job["year_range"]
    target = job["max_events"]
    region = job["region"]
    hazard_type = job["hazard_type"]
    rng = random.Random(task_id)   # deterministic per task

    if region and region.upper() in _STATE_BBOX:
        states = [region.upper()] * target
    else:
        pool = list(_STATE_BBOX.keys())
        states = [pool[i % len(pool)] for i in range(target)]

    events = []
    for i, st in enumerate(states, start=1):
        bb, full = _STATE_BBOX[st]
        yr = lo + ((i - 1) % max(1, (hi - lo + 1)))
        events.append({
            "event_id": f"NOAA_EP_{100000 + i * 137}",
            "state": st,
            "state_name": full,
            "year": yr,
            "date_start": f"{yr}-06-20",
            "date_end": f"{yr}-06-30",
            "bbox": bb,
            "cdl_cropland_pct": round(rng.uniform(60, 85), 1),
            "event_name": "Flood" if hazard_type == "flood" else "Wildfire",
            "damage_total_usd": None,
            "n_hls_clean": rng.randint(20, 40),
            "hls_best_pre_date": f"{yr}-06-18",
            "hls_best_post_date": f"{yr}-06-22",
            "slot_index": i,
            "crop_dates": [f"{yr}-03-15", f"{yr}-05-30", f"{yr}-08-12"],
            "crop_clear_pcts": [88.0, 91.0, 85.0],
            "crop_collections": ["HLSS30", "HLSL30", "HLSS30"],
            "crop_gap_days": [76, 74],
        })

    return json.dumps({
        "status": "completed",
        "task_id": task_id,
        "events": events,
        "slots_filled": len(events),
        "total_candidates": 100,
        "source": "catalog",
        "message": f"Screened {len(events)} {hazard_type} event(s). [MOCK]",
    })


# ── add to imports ──────────────────────────────────────────────────────
import time
import requests

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


@mcp.tool()
def geocode(query: str) -> str:
    """Convert a place name or description to a bounding box
    [west, south, east, north]. Returns a single bbox when unambiguous,
    or a candidates list when multiple matches are found."""
    params = {"q": query, "format": "json", "limit": 5}
    try:
        resp = requests.get(_NOMINATIM_SEARCH, params=params,
                            headers=_GEO_HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        return json.dumps({"message": f"Geocoding service unavailable: {e}"})
    finally:
        time.sleep(1)  # Nominatim: 1 req/sec

    if not results:
        return json.dumps({
            "message": f"No results for '{query}'. Try rephrasing or provide coordinates."
        })

    def _bbox(r):
        bb = r["boundingbox"]  # [south, north, west, east]
        return [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]

    if len(results) == 1:
        return json.dumps({
            "bbox": _bbox(results[0]),
            "display_name": results[0]["display_name"],
            "message": "ok",
        })
    return json.dumps({
        "candidates": [
            {"display_name": r["display_name"], "bbox": _bbox(r)}
            for r in results[:3]
        ],
        "message": "Multiple matches found. Please choose one.",
    })


@mcp.tool()
def reverse_geocode(bbox: list[float]) -> str:
    """Convert a bounding box [west, south, east, north] to a location:
    US state code, state name, county, and display name. Uses the bbox
    centroid for the lookup."""
    west, south, east, north = bbox
    lat = (south + north) / 2
    lon = (west + east) / 2
    params = {"lat": lat, "lon": lon, "format": "json",
              "zoom": 5, "addressdetails": 1}
    try:
        resp = requests.get(_NOMINATIM_REVERSE, params=params,
                            headers=_GEO_HEADERS, timeout=10)
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
        "centroid_lat": round(lat, 4),
        "centroid_lon": round(lon, 4),
        "message": "ok",
    })
