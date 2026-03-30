"""Mock MCP server for CM1 experiment status and figure retrieval."""

import json

from fastmcp import FastMCP

mcp = FastMCP("cm1-experiment-status")

_EXPERIMENT_FIGURES: dict[str, list[str]] = {
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
def check_experiment_status(experiment_id: str) -> str:
    """Check the status of a CM1 experiment by ID.

    In production, this would query SLURM/job scheduler for real status.
    For the mock, always returns "completed" for any experiment ID.
    """
    return json.dumps({"experiment_id": experiment_id, "status": "completed"})


@mcp.tool()
def get_experiment_figures(experiment_id: str) -> str:
    """Retrieve figure URLs for a completed CM1 experiment.

    In production, this would query the experiment workspace filesystem or object storage.
    For the mock, returns hardcoded postimg.cc URLs mapped to known experiment IDs.
    """
    figures = _EXPERIMENT_FIGURES.get(experiment_id, [])
    return json.dumps({"experiment_id": experiment_id, "figures": figures})
