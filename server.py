"""Mock MCP server for CM1 experiment job management.

Simulates the Temporal-based job management system that Stage 4A and Stage 5
agents interact with. Implements the same tool spec as the production server:
- job_submit: accepts experiment payload, returns a job_id
- job_status: checks if a job is finished
- job_plot: returns figure URLs for a completed job
- jobs_list: lists all submitted jobs

Deploy: fastmcp deploy server.py:mcp --name cm1-job-management
"""

import json
import uuid

from fastmcp import FastMCP

mcp = FastMCP("cm1-job-management")

# In-memory job store (resets on server restart)
_JOBS: dict[str, dict] = {}

# Hardcoded figure URLs per experiment for demo purposes
_DEMO_FIGURES: dict[str, list[str]] = {
    "EXP_stability_baseline": [
        "https://i.postimg.cc/26k9d2qD/01-wind-intensity-evolution.png",
        "https://i.postimg.cc/sXjHPwBx/02-pressure-evolution.png",
    ],
    "EXP_stability_001": [
        "https://i.postimg.cc/sXjHPwB1/03-rmw-structure-evolution.png",
        "https://i.postimg.cc/wvq450ty/04-convective-response-proxies.png",
    ],
    "EXP_stability_002": [
        "https://i.postimg.cc/cHxk7XKv/05-end-of-run-summary.png",
        "https://i.postimg.cc/85ZKZMWC/06-energy-vorticity-evolution.png",
    ],
}


@mcp.tool()
def job_submit(payload: dict) -> str:
    """Submit a new job to the Temporal workflow queue.

    Accepts the Stage 4A experiment payload containing:
    - workspace_name: str
    - base_template: str
    - experiments: list of ExperimentSpec objects, each with:
      - experiment_id, description, is_baseline, feasibility_flag
      - edits: list of FileEdit objects (namelist_param, sounding_profile, file_replace)

    Stores the full experiment_specs JSON and returns a unique job_id.
    In production, this triggers the Temporal workflow that builds
    the experiment workspace and runs CM1 simulations.
    """
    job_id = str(uuid.uuid4())[:8]

    # Extract experiment IDs from payload
    experiment_ids = [
        exp.get("experiment_id", "")
        for exp in payload.get("experiments", [])
        if exp.get("experiment_id")
    ]

    # Store the full experiment specs JSON — same structure as experiment_specs.json
    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "completed",
        "experiment_specs": {
            "workspace_name": payload.get("workspace_name", ""),
            "base_template": payload.get("base_template", ""),
            "experiments": payload.get("experiments", []),
        },
        "experiment_ids": experiment_ids,
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
    """Get figure URLs for a completed job.

    In production, this reads from the experiment output directory
    or object storage where CM1 results and analysis plots are saved.
    For the mock, returns all demo figure URLs for any valid job.
    """
    job = _JOBS.get(job_id)

    if job:
        experiment_ids = job.get("experiment_ids", [])
        # Distribute demo figures evenly across experiments
        all_figures = [
            "https://i.postimg.cc/26k9d2qD/01-wind-intensity-evolution.png",
            "https://i.postimg.cc/sXjHPwBx/02-pressure-evolution.png",
            "https://i.postimg.cc/sXjHPwB1/03-rmw-structure-evolution.png",
            "https://i.postimg.cc/wvq450ty/04-convective-response-proxies.png",
            "https://i.postimg.cc/cHxk7XKv/05-end-of-run-summary.png",
            "https://i.postimg.cc/85ZKZMWC/06-energy-vorticity-evolution.png",
        ]
        figures_by_experiment = {}
        for i, eid in enumerate(experiment_ids):
            start = i * 2
            end = start + 2
            figures_by_experiment[eid] = all_figures[start:end] if end <= len(all_figures) else all_figures[start:]
    else:
        figures_by_experiment = {}

    return json.dumps({
        "job_id": job_id,
        "figures": figures_by_experiment,
    })



@mcp.tool()
def jobs_list(filter: str = "all") -> str:
    """List all jobs in the system.

    Args:
        filter: Optional filter — "all" (default) returns everything.

    Returns all submitted jobs with their IDs, status, and payload metadata.
    """
    jobs = [
        {
            "job_id": j["job_id"],
            "status": j["status"],
            "workspace_name": j["experiment_specs"].get("workspace_name", ""),
            "experiment_ids": j.get("experiment_ids", []),
        }
        for j in _JOBS.values()
    ]
    return json.dumps({"jobs": jobs})

