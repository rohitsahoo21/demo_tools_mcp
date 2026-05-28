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
def job_plot(job_id: str) -> str:
    """Get figure URLs and report for a completed job.

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
