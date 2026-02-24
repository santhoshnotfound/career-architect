# app/analytics/readiness.py
# ============================================================
# READINESS SCORE ENGINE
#
# Computes a 0–100 "career readiness" score for a student
# targeting a specific role. Every component of the score
# is fully explainable — no machine learning, no black boxes.
#
# HOW THE SCORE IS COMPOSED
# ──────────────────────────
# The score has two independent components:
#
#   Component A — Coverage (60 points max)
#     "How many of the required skills does the student already have?"
#     score_A = (known_count / total_required) × 60
#
#     Rationale: Knowing 6/10 required skills is a direct signal
#     of readiness. This component rewards breadth of coverage.
#
#   Component B — Proximity (40 points max)
#     "How close is the student to the skills they're missing?"
#     score_B = (1 − avg_distance / max_possible_distance) × 40
#
#     For each missing required skill, we compute the shortest
#     directed path in the prerequisite graph from any skill the
#     student has. A student who knows Python is "1 hop" from
#     Data Structures, which is "2 hops" from Algorithms.
#     Shorter distances → higher proximity score.
#
#     This rewards students who are "nearly ready" even if they
#     haven't yet crossed the finish line.
#
# WHY 60/40 SPLIT?
#   Coverage is weighted higher because it directly answers
#   the evaluation question ("does this student have the skills?").
#   Proximity is a forward-looking bonus: it captures how much
#   work remains, not just how much has been done.
#
# DIFFICULTY CLASSIFICATION
#   Based on average graph distance to missing skills:
#     Low    — avg distance < 2   (close, mostly surface-level gaps)
#     Medium — avg distance 2–4   (moderate prerequisite chains)
#     High   — avg distance > 4   (deep prerequisite chains needed)
# ============================================================

import networkx as nx
from app.graph_engine import load_default_graph, TARGET_ROLES, compute_skill_gap


# Maximum graph distance we consider for normalization.
# In a ~30-node DAG, diameter is unlikely to exceed 8 hops.
# Skills with no path (isolated) are assigned this penalty distance.
MAX_DISTANCE = 8


def calculate_readiness(user_skills: list[str], role: str) -> dict:
    """
    Compute an explainable readiness score for a student targeting a role.

    This is the primary evaluation function in Career Architect.
    It is designed to be used by professors to score student profiles
    against a target career path objectively and reproducibly.

    Args:
        user_skills: List of canonical skill names the student has.
        role:        A key from TARGET_ROLES.

    Returns:
        dict with keys:
            score                — int 0–100, overall readiness
            component_coverage   — float, contribution from skill coverage (0–60)
            component_proximity  — float, contribution from graph proximity (0–40)
            known_skills_count   — number of required skills already held
            missing_skills_count — number of required skills still needed
            total_required       — total required skills for this role
            avg_graph_distance   — mean shortest path from student to missing skills
            estimated_difficulty — "Low" | "Medium" | "High"
            role                 — the target role name
            interpretation       — plain-English explanation of the score

    Raises:
        ValueError: if role is not in TARGET_ROLES.

    Academic use:
        A professor could run this function against each student's
        GitHub/resume profile to produce a ranked cohort readiness table.
        Scores are fully reproducible and audit-able step by step.

    Example:
        calculate_readiness(["Python", "Git"], "AI Researcher")
        → score ≈ 18  (knows 1/10 skills, but Python is 1 hop from many gaps)
    """
    if role not in TARGET_ROLES:
        raise ValueError(f"Role '{role}' not found. Valid: {list(TARGET_ROLES.keys())}")

    G   = load_default_graph()
    gap = compute_skill_gap(user_skills, role)

    known_count   = len(gap["known_skills"])
    missing_count = len(gap["missing_skills"])
    total_req     = known_count + missing_count

    # ── Component A: Coverage Score (0–60) ───────────────────────
    # Simple fraction of required skills the student already holds.
    # If student knows all skills → 60 points. Knows none → 0 points.
    if total_req == 0:
        coverage_score = 60.0  # Edge case: no requirements defined
    else:
        coverage_score = (known_count / total_req) * 60.0

    # ── Component B: Proximity Score (0–40) ──────────────────────
    # For each missing skill, find the shortest directed path from
    # any of the student's known skills to that target skill.
    # Average those distances and normalize to 0–40.

    user_skill_set = set(gap["known_skills"])
    # Include user skills not in required set (still valid launch points)
    graph_nodes_lower = {n.lower(): n for n in G.nodes()}
    for s in user_skills:
        canonical = graph_nodes_lower.get(s.lower(), s)
        user_skill_set.add(canonical)

    distances = []
    for missing_skill in gap["missing_skills"]:
        best_dist = _shortest_distance_from_any(G, user_skill_set, missing_skill)
        distances.append(best_dist)

    if distances:
        avg_dist = sum(distances) / len(distances)
    else:
        avg_dist = 0.0  # No missing skills → perfect proximity

    # Normalize: distance 0 → 40 pts, distance MAX_DISTANCE → 0 pts
    # Clamp to [0, MAX_DISTANCE] before normalizing
    avg_dist_clamped = min(avg_dist, MAX_DISTANCE)
    proximity_score  = (1.0 - avg_dist_clamped / MAX_DISTANCE) * 40.0

    # ── Final score ───────────────────────────────────────────────
    total_score = round(coverage_score + proximity_score)
    total_score = max(0, min(100, total_score))  # Clamp to [0, 100]

    # ── Difficulty classification ─────────────────────────────────
    # Based on average distance to missing skills, not on score.
    # This reflects "how much work is still needed", independent
    # of the score (a student with 0 skills can still have Low difficulty
    # if all gaps are just one prerequisite away).
    difficulty = _classify_difficulty(avg_dist)

    # ── Plain-language interpretation ─────────────────────────────
    interpretation = _interpret_score(total_score, known_count, missing_count, difficulty)

    return {
        "score":                total_score,
        "component_coverage":   round(coverage_score, 2),
        "component_proximity":  round(proximity_score, 2),
        "known_skills_count":   known_count,
        "missing_skills_count": missing_count,
        "total_required":       total_req,
        "avg_graph_distance":   round(avg_dist, 2),
        "estimated_difficulty": difficulty,
        "role":                 role,
        "interpretation":       interpretation,
    }


def _shortest_distance_from_any(
    G: nx.DiGraph,
    sources: set[str],
    target: str,
) -> float:
    """
    Find the shortest directed path from any node in `sources` to `target`.

    Returns the hop count (number of edges) of the shortest path found.
    Returns MAX_DISTANCE if no path exists from any source (penalty).

    This is used to measure how "close" a student is to acquiring
    a missing skill given their current knowledge base.

    Args:
        G:       The prerequisite knowledge graph.
        sources: Set of skills the student already knows.
        target:  The missing skill we want to reach.

    Returns:
        Float hop count. Lower is better (closer to acquiring the skill).
    """
    if target not in G.nodes():
        return MAX_DISTANCE  # Skill not in graph: treat as maximally distant

    best = MAX_DISTANCE  # Pessimistic starting value

    for src in sources:
        if src not in G.nodes():
            continue
        if src == target:
            return 0.0  # Already there (shouldn't happen but guard anyway)
        try:
            path = nx.shortest_path(G, source=src, target=target)
            dist = len(path) - 1  # path includes src; distance = edges
            if dist < best:
                best = dist
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue  # No directed path from this source

    return float(best)


def _classify_difficulty(avg_distance: float) -> str:
    """
    Classify overall acquisition difficulty from average graph distance.

    Educational interpretation:
        Low    → Most missing skills are 1–2 prerequisites away.
                  Student can likely fill gaps in a single semester.
        Medium → Several deep prerequisite chains needed.
                  Realistic with 2–3 semesters of focused study.
        High   → Many foundational skills are missing.
                  Student would benefit from a structured multi-year plan.
    """
    if avg_distance < 2.0:
        return "Low"
    elif avg_distance <= 4.0:
        return "Medium"
    else:
        return "High"


def _interpret_score(score: int, known: int, missing: int, difficulty: str) -> str:
    """
    Generate a one-sentence plain-English summary of the score.

    Designed to be readable in an academic report without further context.
    """
    if missing == 0:
        return "Fully qualified: student meets all requirements for this role."
    if score >= 75:
        return (
            f"Strong profile: {known} of {known + missing} required skills are in place. "
            f"Remaining gaps have {difficulty.lower()} acquisition difficulty."
        )
    if score >= 45:
        return (
            f"Developing profile: {known} of {known + missing} required skills are in place. "
            f"Acquisition difficulty is {difficulty.lower()}; a structured study plan is recommended."
        )
    return (
        f"Early-stage profile: {known} of {known + missing} required skills are in place. "
        f"Substantial foundational work is needed (difficulty: {difficulty.lower()})."
    )
