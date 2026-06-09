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
    "https://i.postimg.cc/R6dxS4Ph/per-crop-breakdown.png",
    "https://i.postimg.cc/JHhVtvgL/pipeline-comparison.png",
]


@mcp.tool()
def job_submit(payload: dict) -> str:
    """Submit a new job to the Temporal workflow queue.

    Accepts the Stage 4 experiment payload containing the full pipeline
    config YAML (events, prithvi tasks, output settings, etc.).

    Stores the payload and returns a unique job_id.
    In production, this triggers the Temporal workflow that runs the
    Prithvi pipeline on HPC.
    """
    job_id = str(uuid.uuid4())[:8]

    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "completed",
        "payload": payload,
        "workspace_name": payload.get("output", {}).get("dir", ""),
    }
    return json.dumps({"job_id": job_id})


@mcp.tool()
def job_status(job_id: str) -> str:
    """Get the status of a specific job by its ID.

    In production, this queries the Temporal workflow for real status.
    For the mock, returns "completed" for any submitted job.
    """
    job = _JOBS.get(job_id)
    if job:
        return json.dumps({"job_id": job_id, "status": job["status"]})
    return json.dumps({"job_id": job_id, "status": "completed"})


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


import asyncio
import random

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

_SCREEN_SLEEP = 90  # crank high to test background-task behavior


@mcp.tool(task=True)
async def screen_events(
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
    """Screen and manage a list of flood/burn events for the Prithvi pipeline.
    The number of events is controlled by ``max_events`` (read from
    ``events.max_events`` in the config YAML; default 5, max 20).

    Supports iterative refinement: reject events you don't like and get diverse
    replacements. Searches the pre-built catalog first; when the catalog is
    exhausted, discovers new events from the NOAA Storm Events API and verifies
    HLS satellite imagery with a lightweight clear-sky probe. Filters by region
    (US state), date range, bbox, cropland %."""
    await asyncio.sleep(_SCREEN_SLEEP)

    target = max(1, min(20, max_events))
    lo, hi = (year_range or [2017, 2025])

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
            "cdl_cropland_pct": round(random.uniform(60, 85), 1),
            "event_name": "Flood" if hazard_type == "flood" else "Wildfire",
            "damage_total_usd": None,
            "n_hls_clean": random.randint(20, 40),
            "hls_best_pre_date": f"{yr}-06-18",
            "hls_best_post_date": f"{yr}-06-22",
            "slot_index": i,
            "crop_dates": [f"{yr}-03-15", f"{yr}-05-30", f"{yr}-08-12"],
            "crop_clear_pcts": [88.0, 91.0, 85.0],
            "crop_collections": ["HLSS30", "HLSL30", "HLSS30"],
            "crop_gap_days": [76, 74],
        })

    out = {
        "events": events,
        "slots_filled": len(events),
        "total_candidates": 100,
        "source": "catalog",
        "message": (
            f"Screened {len(events)} {hazard_type} event(s) "
            f"(region={region or 'auto'}, years={lo}-{hi}, "
            f"min_cropland={min_cropland_pct or 0}%). [MOCK task=True]"
        ),
    }
    return json.dumps(out)
