"""Domain isolation rules for the job dependency graph.

A dependency edge is only legal when the job and every job it depends on belong
to the same business domain.  These helpers are shared by the configuration-time
guard (job domain updates) and the orchestration-time guard (execution graph).
"""

from __future__ import annotations

from typing import Any, Iterable


def dependency_edges(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return known dependency edges (unknown dependency names are skipped)."""
    by_name = {j["name"]: j for j in jobs}
    edges: list[dict[str, Any]] = []
    for job in jobs:
        for dep_name in job["depends_on"]:
            dep = by_name.get(dep_name)
            if dep is None:
                continue
            edges.append(_edge(job, job["domain"], dep_name, dep["domain"]))
    return edges


def cross_domain_edges(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """All known edges whose endpoints live in different domains."""
    return [e for e in dependency_edges(jobs) if e["job_domain"] != e["dep_domain"]]


def cross_domain_edges_for_job(
    job: dict[str, Any], all_jobs_by_name: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Cross-domain edges from this job to its declared upstreams."""
    edges: list[dict[str, Any]] = []
    for dep_name in job["depends_on"]:
        dep = all_jobs_by_name.get(dep_name)
        if dep is None:
            continue
        edge = _edge(job, job["domain"], dep_name, dep["domain"])
        if edge["job_domain"] != edge["dep_domain"]:
            edges.append(edge)
    return edges


def cross_domain_conflicts_for_change(
    jobs: Iterable[dict[str, Any]], job_id: int, new_domain: str
) -> list[dict[str, Any]]:
    """Conflicts introduced by moving ``job_id`` to ``new_domain``.

    Only edges that touch the changed job are returned, so an unrelated bad
    edge elsewhere in the graph does not make every domain edit impossible.
    """
    jobs = list(jobs)
    target = next((j for j in jobs if j["id"] == job_id), None)
    if target is None:
        return []

    by_name = {j["name"]: j for j in jobs}
    conflicts: list[dict[str, Any]] = []

    # The job's own upstream dependencies.
    for dep_name in target["depends_on"]:
        dep = by_name.get(dep_name)
        if dep is None:
            continue
        edge = _edge(target, new_domain, dep_name, dep["domain"])
        if edge["job_domain"] != edge["dep_domain"]:
            conflicts.append(edge)

    # Downstream jobs that depend on the changed job.
    for other in jobs:
        if other["id"] == job_id:
            continue
        if target["name"] not in other["depends_on"]:
            continue
        edge = _edge(other, other["domain"], target["name"], new_domain)
        if edge["job_domain"] != edge["dep_domain"]:
            conflicts.append(edge)

    return _dedupe(conflicts)


def _edge(
    job: dict[str, Any], job_domain: str, dep_name: str, dep_domain: str
) -> dict[str, Any]:
    return {
        "job": job["name"],
        "job_domain": job_domain,
        "depends_on": dep_name,
        "dep_domain": dep_domain,
    }


def _dedupe(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for e in edges:
        key = (e["job"], e["job_domain"], e["depends_on"], e["dep_domain"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
