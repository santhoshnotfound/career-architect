# app/routes/graph_data.py
# ============================================================
# Endpoint that serializes the knowledge graph into a format
# the frontend (React Flow) can consume directly.
#
# React Flow expects nodes and edges as plain JSON arrays:
#   nodes: [{ id, data: { label }, position }]
#   edges: [{ id, source, target }]
#
# This endpoint also accepts optional user state (known skills,
# roadmap path) so the frontend can color nodes correctly:
#   green  = skills user already has
#   red    = skills user is missing (required by role)
#   yellow = next recommended skill (first step in roadmap)
#   white  = skills not relevant to chosen role
# ============================================================

import math
from fastapi import APIRouter
from pydantic import BaseModel

from app.graph_engine import load_default_graph, TARGET_ROLES, compute_skill_gap, SKILL_DOMAINS

router = APIRouter(
    prefix="/graph-data",
    tags=["Graph Visualization"],
)


# ── Schemas ───────────────────────────────────────────────────

class GraphStateRequest(BaseModel):
    """
    Optional user context for coloring the graph.
    If omitted, returns the raw graph with no highlighting.
    """
    user_skills:  list[str] = []
    target_role:  str       = ""


class NodeData(BaseModel):
    id:       str
    label:    str
    status:   str   # "known" | "missing" | "next" | "neutral"
    domain:   str   # "programming" | "math" | "ml" | "engineering"
    x:        float
    y:        float


class EdgeData(BaseModel):
    id:     str
    source: str
    target: str


class GraphDataResponse(BaseModel):
    nodes:           list[NodeData]
    edges:           list[EdgeData]
    available_roles: list[str]


# ── Domain classification ──────────────────────────────────────
# SKILL_DOMAINS is defined in graph_engine.py (canonical location)
# and imported above. It maps skill names to domain strings:
# "programming" | "math" | "ml" | "engineering"

# ── Layout: position nodes in domain clusters ──────────────────
# Rather than using an auto-layout algorithm (which changes every
# render), we assign fixed positions grouped by domain.
# This makes the graph stable and easier to explain to an audience.
DOMAIN_LAYOUTS = {
    "programming": {"cx": 200,  "cy": 300},
    "math":        {"cx": 600,  "cy": 150},
    "ml":          {"cx": 950,  "cy": 300},
    "engineering": {"cx": 550,  "cy": 550},
    "web":         {"cx": 150,  "cy": 600},
    "data":        {"cx": 800,  "cy": 600},
}


def _compute_positions(nodes: list[str]) -> dict[str, tuple[float, float]]:
    """
    Assigns (x, y) positions by grouping nodes into domain clusters,
    then arranging each cluster in a small circle around its center.
    """
    # Group nodes by domain — fall back to "programming" for any unknown domain
    domain_groups: dict[str, list[str]] = {d: [] for d in DOMAIN_LAYOUTS}
    for node in nodes:
        domain = SKILL_DOMAINS.get(node, "programming")
        if domain not in domain_groups:
            domain = "programming"
        domain_groups[domain].append(node)

    positions = {}
    for domain, group_nodes in domain_groups.items():
        cx = DOMAIN_LAYOUTS[domain]["cx"]
        cy = DOMAIN_LAYOUTS[domain]["cy"]
        count = len(group_nodes)

        for i, node in enumerate(group_nodes):
            if count == 1:
                x, y = cx, cy
            else:
                # Arrange in a circle of radius ~120px around the cluster center
                angle = (2 * math.pi * i) / count
                radius = 130
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
            positions[node] = (round(x, 1), round(y, 1))

    return positions


# ── Endpoint ──────────────────────────────────────────────────

@router.post(
    "/",
    response_model=GraphDataResponse,
    summary="Get graph data formatted for React Flow visualization",
)
def get_graph_data(state: GraphStateRequest):
    """
    Returns the full knowledge graph as React Flow-compatible
    nodes and edges, with optional user state for highlighting.

    Node status values:
    - `known`   — user has this skill (render green)
    - `missing` — role requires it, user doesn't have it (render red)
    - `next`    — first skill to learn in any roadmap path (render yellow)
    - `neutral` — not relevant to chosen role (render light grey)

    ### Example Request (with user state)
    ```json
    {
      "user_skills": ["Python", "Git"],
      "target_role": "AI Researcher"
    }
    ```
    """
    G = load_default_graph()
    all_nodes = list(G.nodes())
    positions = _compute_positions(all_nodes)

    # ── Compute user state if role is provided ────────────────
    known_set   = set()
    missing_set = set()
    next_skills = set()

    if state.target_role and state.target_role in TARGET_ROLES:
        gap = compute_skill_gap(state.user_skills, state.target_role)
        known_set   = set(gap["known_skills"])
        missing_set = set(gap["missing_skills"])

        # "next" = first non-known skill in each learning path
        for path in gap["learning_paths"].values():
            for skill in path:
                if skill not in known_set:
                    next_skills.add(skill)
                    break  # Only the first step per path

    user_skill_set = {s.lower() for s in state.user_skills}

    # ── Build node list ───────────────────────────────────────
    nodes = []
    for node_name in all_nodes:
        x, y = positions.get(node_name, (400, 300))

        # Determine status for coloring
        if node_name in known_set or node_name.lower() in user_skill_set:
            node_status = "known"
        elif node_name in next_skills:
            node_status = "next"
        elif node_name in missing_set:
            node_status = "missing"
        else:
            node_status = "neutral"

        nodes.append(NodeData(
            id=node_name,
            label=node_name,
            status=node_status,
            domain=SKILL_DOMAINS.get(node_name, "programming"),
            x=x,
            y=y,
        ))

    # ── Build edge list ───────────────────────────────────────
    edges = []
    for i, (source, target) in enumerate(G.edges()):
        edges.append(EdgeData(
            id=f"e{i}-{source}-{target}",
            source=source,
            target=target,
        ))

    return GraphDataResponse(
        nodes=nodes,
        edges=edges,
        available_roles=list(TARGET_ROLES.keys()),
    )
