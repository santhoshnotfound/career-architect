# CLAUDE.md — Career Architect

> Written for AI agents. Read this before modifying any part of the project.

---

## What This Project Does

**Career Architect** is a career readiness assessment tool for students and developers. It:

1. Accepts a resume (text) or GitHub profile URL as input
2. Extracts skills using an LLM or deterministic keyword matching (fallback)
3. Compares extracted skills against a hardcoded knowledge graph of 83 skills and 7 target roles
4. Computes a 0–100 readiness score using graph-distance math (no ML)
5. Generates a prerequisite-ordered learning roadmap and week-by-week study plan
6. Produces a downloadable PDF report
7. Displays an interactive D3.js skill graph in a single-page frontend

The codebase is designed to be fully auditable — scoring is deterministic and the graph is static.

---

## Repository Layout

```
/
├── app/                    # All backend Python code
│   ├── main.py             # FastAPI app factory, CORS, router registration
│   ├── database.py         # SQLite engine, SessionLocal, Base
│   ├── models.py           # SQLAlchemy ORM models
│   ├── schemas.py          # Pydantic request/response models
│   ├── crud.py             # DB CRUD helpers
│   ├── graph_engine.py     # Knowledge graph + gap analysis (CORE)
│   ├── routes/             # One file per API endpoint group
│   ├── ai/                 # Skill extraction and GitHub scanning
│   └── analytics/          # Readiness scoring, study planner, PDF report
├── index.html              # Entire frontend (vanilla JS + D3.js, no build step)
├── career.db               # SQLite database (auto-created on startup)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── Procfile                # Deployment: uvicorn on $PORT
├── runtime.txt             # python-3.11.9
└── README.md               # User-facing docs
```

---

## Backend Architecture

### Framework & Runtime
- **FastAPI** (async, auto OpenAPI docs at `/docs`)
- **Python 3.11.9**
- **Uvicorn** as ASGI server
- **SQLite** via SQLAlchemy ORM (no migrations — tables created on startup)

### Startup Flow (`app/main.py`)
1. `Base.metadata.create_all(bind=engine)` — creates `skills` and `feedback` tables if absent
2. All routers registered with `app.include_router(...)`
3. CORS middleware allows all origins (development-safe; tighten for production)

### Database (`app/database.py`, `app/models.py`)

Two tables:

| Table | Columns | Purpose |
|-------|---------|---------|
| `skills` | id, name (unique) | Persisted skill records |
| `feedback` | id, rating, resume_snippet, detected_skills, correct_skills, target_role, source, created_at | User feedback on extraction quality |

`career.db` is committed to the repo and auto-created if deleted. For production use PostgreSQL by changing `DATABASE_URL` in `database.py` — the ORM abstracts the rest.

### Schemas (`app/schemas.py`)
Pydantic models for request/response validation. Keep these in sync with route handlers. `from_attributes = True` is set to support ORM → Pydantic conversion.

### CRUD (`app/crud.py`)
Thin wrappers: `create_skill`, `get_all_skills`, `get_skill_by_name`. All DB writes go through here — do not write raw SQL in routes.

---

## Routes (`app/routes/`)

Each file registers one logical group. All files follow the same pattern:
`router = APIRouter()` → decorated handlers → imported in `main.py`.

| File | Endpoints | Notes |
|------|-----------|-------|
| `health.py` | `GET /health` | Returns `{"status": "ok"}` |
| `skills.py` | `POST /skills/`, `GET /skills/` | Simple CRUD for skill records |
| `roadmap.py` | `POST /roadmap/`, `GET /roadmap/graph-info` | Calls `graph_engine.compute_skill_gap()` |
| `extract.py` | `POST /extract-skills/` | Delegates to `ai/skill_extractor.py` |
| `graph_data.py` | `POST /graph-data/` | Returns D3-formatted nodes/edges |
| `readiness.py` | `POST /readiness/` | Calls `analytics/readiness.py` |
| `study_plan.py` | `POST /study-plan/` | Calls `analytics/planner.py` |
| `report.py` | `GET /report/` | Streams a PDF via `analytics/report.py` |
| `github_scan.py` | `POST /scan-github/` | Delegates to `ai/github_scanner.py` |
| `feedback.py` | `POST /feedback/`, `GET /feedback/summary` | Stores user ratings |

**Guiding rule:** Routes are thin — no business logic. Pass inputs to the relevant engine/analytics module and return the result.

---

## Knowledge Graph (`app/graph_engine.py`)

This is the core of the system. **Read this file before touching anything.**

### Structure
- **83 skill nodes** across 6 domains: Programming, Math, ML/AI, Engineering/DevOps, Web, Data Engineering
- **~80+ directed edges** representing prerequisite relationships (A → B means "learn A before B")
- **7 target roles**, each with a list of required skills
- **NetworkX DiGraph** — verified to be a DAG (`nx.is_directed_acyclic_graph`)

### Key Functions

```python
load_default_graph() -> nx.DiGraph
    # Builds the in-memory graph. Called once at module load (singleton pattern).
    # All 83 nodes and edges are defined here. Edit here to add/remove skills.

compute_skill_gap(user_skills: list[str], role: str) -> dict
    # Core gap analysis.
    # Returns: known_skills, missing_skills, learning_paths
    # learning_paths: {missing_skill: [prerequisite_chain_to_reach_it]}
    # Uses nx.shortest_path (Dijkstra) from each known skill toward each missing skill.

get_graph_summary() -> dict
    # Returns: total_nodes, total_edges, all_skills, available_roles, is_dag
```

### Domains and Colors
Each skill node stores a `domain` attribute. The frontend uses domain to color-code nodes.

| Domain | Color var |
|--------|-----------|
| Programming | `--prog` (#3b82f6) |
| Math | `--math` (#7c3aed) |
| ML/AI | `--ml` (#db2777) |
| Engineering/DevOps | `--eng` (#0d9488) |
| Web | cyan |
| Data Engineering | orange |

### Adding a Skill
1. Add the node: `G.add_node("New Skill", domain="Programming")`
2. Add prerequisite edges: `G.add_edge("Existing Skill", "New Skill")`
3. Add it to any role's required list in `ROLES`
4. Add keyword/synonym rules in `ai/skill_extractor.py` (keyword fallback dict)
5. Verify the graph is still a DAG: `nx.is_directed_acyclic_graph(G)` must be `True`

### Adding a Role
Add to the `ROLES` dict in `graph_engine.py`:
```python
"New Role": ["Skill A", "Skill B", ...]
```
Skills listed must already exist as nodes.

---

## AI Modules (`app/ai/`)

### `skill_extractor.py` — Dual-Mode Extraction

**Mode 1: LLM (if `OPENAI_API_KEY` is set)**
- OpenAI-compatible API call (configurable via `OPENAI_BASE_URL`, `OPENAI_MODEL`)
- System prompt includes all 83 canonical skill names
- Temperature = 0 (deterministic)
- Response must be JSON: `{"skills": [...]}`
- Falls back to keyword mode on any error

**Mode 2: Keyword Fallback (always available)**
- 550+ rules across 4 strategies:
  1. Exact phrase match ("pytorch", "linear algebra")
  2. Synonym map ("torch" → PyTorch, "ml" → Machine Learning)
  3. Concept phrase match ("random variables" → Probability)
  4. Library/package name match ("matplotlib" → Data Science)
- Fully deterministic, no network call needed
- Useful for demos without API keys

**Safe to modify:** Add new synonym rules to the keyword dicts. Do not remove existing canonical skill names — they must match node names in `graph_engine.py` exactly (case-sensitive).

### `github_scanner.py` — GitHub Profile Scanning

Scans up to 15 most-recent public repos per user. For each repo it reads:
- Primary language
- Topic tags
- `requirements.txt` (Python deps)
- `package.json` (Node deps)
- File tree (detects Dockerfiles, `.ipynb`, `.sql`, shell scripts)
- Repo name and description

Maps findings to canonical skill names via `PYTHON_IMPORT_MAP`, `PACKAGE_NAME_MAP`, `FILE_SIGNAL_MAP`, `LANGUAGE_MAP`.

**Rate limits:**
- Without `GITHUB_TOKEN`: 60 req/hour
- With `GITHUB_TOKEN`: 5000 req/hour

Only accesses **public** repositories. Never stores GitHub data to the DB.

---

## Analytics Modules (`app/analytics/`)

### `readiness.py` — Career Readiness Score

Score = **Coverage (0–60)** + **Proximity (0–40)**

```
Coverage  = (known_required / total_required) * 60
Proximity = (1 - avg_shortest_path_distance / 8) * 40
```

- `avg_shortest_path_distance`: for each missing required skill, find the shortest graph path from any user-known skill to that missing skill; average those hop counts
- Capped at distance 8 (≥8 hops → 0 proximity points)
- `estimated_difficulty`: Low (<2 avg hops), Medium (2–4), High (>4)

The score is fully reproducible from the graph and skill list alone. Do not add randomness.

### `planner.py` — Study Plan Generator

1. Flattens `learning_paths` from `compute_skill_gap` into a prerequisite-ordered list
2. Assigns each skill a difficulty weight (float, in study-weeks)
3. Scales weights to fit the requested `total_weeks`
4. Distributes skills across weeks, outputting per-week study tips

Skill weights are defined as a dict in `planner.py`. Edit there to change pacing.

### `report.py` — PDF Generation

Uses **ReportLab** (pure Python, no headless browser). The PDF includes:
1. Header (student name, role, date)
2. Executive summary (score breakdown)
3. Skills inventory table (known vs missing)
4. Gap analysis (missing skills + learning paths)
5. Recommended learning roadmap (ordered skill list)
6. Semester study plan (week-by-week table)
7. Score methodology explanation

Colors match the frontend: green (known), red (missing), amber (next), grey (neutral).

**Safe to modify:** Section order, fonts, colors. Do not change the `StreamingResponse` pattern in the route — the PDF is streamed as bytes, not saved to disk.

---

## Frontend Architecture (`index.html`)

Single HTML file. No build step, no npm, no React.

### Technology
- **Vanilla JavaScript** (ES6+)
- **D3.js v7** (loaded from CDN) — force-directed graph
- **CSS Grid + Flexbox** — layout
- **CSS custom properties** — color theming

### Page Structure
A sidebar with 8 links drives a `showPage(id)` function that shows/hides `<section>` elements:

| Page | ID | Description |
|------|----|-------------|
| Resume Upload | `resume` | Textarea + Extract Skills button |
| Skill Review | `skills` | Editable list of extracted skills |
| Roadmap | `roadmap` | Missing skills + learning paths |
| Graph | `graph` | D3 force-directed visualization |
| Score | `score` | Readiness score + components |
| Study Plan | `study-plan` | Week-by-week schedule |
| PDF Report | `report` | Form + download button |
| GitHub Scan | `github` | GitHub URL/username input |

### D3 Graph
Rendered inside `<svg id="graph-svg">`. Key parameters:
- `forceSimulation` with `forceManyBody`, `forceLink`, `forceCenter`
- Nodes colored by skill status (known/missing/next/neutral) and domain
- Draggable via `d3.drag`
- Zoom/pan via `d3.zoom`
- Tooltip on hover (shows skill name and domain)

Data comes from `POST /graph-data/` — returns `{nodes: [...], edges: [...]}`.

### API Base URL
Set at the top of the `<script>` block:
```js
const API = "https://career-architect-production.up.railway.app";
```
Change this for local development: `const API = "http://localhost:8000";`

---

## API Endpoints (Full Reference)

All requests/responses are JSON unless noted. Interactive docs: `GET /docs`.

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `POST` | `/skills/` | `{"name": "Python"}` | `{"id": 1, "name": "Python"}` |
| `GET` | `/skills/` | — | `[{"id":1,"name":"Python"},...]` |
| `POST` | `/extract-skills/` | `{"text": "...resume text..."}` | `{"skills":[],"total_found":N,"available_skills_in_graph":M}` |
| `POST` | `/roadmap/` | `{"user_skills":[],"target_role":""}` | `{"target_role":"","known_skills":[],"missing_skills":[],"learning_paths":{}}` |
| `GET` | `/roadmap/graph-info` | — | `{"total_nodes":83,"total_edges":N,"all_skills":[],"available_roles":[],"is_dag":true}` |
| `POST` | `/graph-data/` | `{"user_skills":[],"target_role":""}` | `{"nodes":[],"edges":[],"available_roles":[]}` |
| `POST` | `/readiness/` | `{"user_skills":[],"target_role":""}` | `{"score":0,"component_coverage":0,"component_proximity":0,...}` |
| `POST` | `/study-plan/` | `{"user_skills":[],"target_role":"","total_weeks":16,"hours_per_week":6}` | `{"target_role":"","total_weeks":16,"weeks":[...]}` |
| `GET` | `/report/` | Query params: `user_skills`, `target_role`, `student_name` | PDF binary (`application/pdf`) |
| `POST` | `/scan-github/` | `{"github_input":"github.com/username"}` | `{"username":"","skills":[],"repos_scanned":N,"signals":[]}` |
| `POST` | `/feedback/` | `{"rating":"good"/"bad","resume_snippet":"","detected_skills":"","target_role":"","source":""}` | `{"id":1,"rating":"good","message":"..."}` |
| `GET` | `/feedback/summary` | — | `{"total":N,"good":N,"bad":N,"good_pct":0.0}` |

---

## Environment Variables

```bash
# Optional — LLM-based skill extraction (falls back to keyword matching if absent)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # Default; change for other providers
OPENAI_MODEL=gpt-4o-mini                     # Default model

# Optional — raises GitHub API rate limit from 60 → 5000 req/hour
GITHUB_TOKEN=ghp_...
```

Copy `.env.example` to `.env` and fill in values. Never commit `.env`.

---

## Deployment

Hosted on **Railway**. The backend URL is hardcoded in `index.html`:
```js
const API = "https://career-architect-production.up.railway.app";
```

**Procfile:**
```
web: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway injects `$PORT` automatically. The SQLite database (`career.db`) is ephemeral on Railway — on redeploy, it resets. For persistent data, switch to PostgreSQL (Railway provides it as an add-on; only `DATABASE_URL` in `database.py` needs to change).

---

## Common Modification Patterns

### Add a new skill
1. `app/graph_engine.py` → `load_default_graph()`: add node + edges
2. `app/ai/skill_extractor.py` → keyword/synonym dicts: add recognition rules
3. Optionally add to a role's required list in `ROLES`

### Add a new target role
1. `app/graph_engine.py` → `ROLES` dict: add role name and skill list
2. All skills in the list must already be graph nodes

### Add a new API endpoint
1. Create `app/routes/my_feature.py` with `router = APIRouter()`
2. Import and register in `app/main.py`: `app.include_router(my_router, tags=["My Feature"])`
3. Put business logic in a new `app/analytics/` or `app/ai/` module, not in the route

### Change the frontend API URL (local dev)
In `index.html`, find:
```js
const API = "https://career-architect-production.up.railway.app";
```
Change to `http://localhost:8000` for local development. Do not commit that change.

### Run locally
```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in values
uvicorn app.main:app --reload
# open index.html in a browser (or serve it with any static server)
```

---

## Invariants — Do Not Break

- The graph **must remain a DAG**. After any edge change, verify: `nx.is_directed_acyclic_graph(G) == True`
- Canonical skill names in `graph_engine.py` (`ROLES`, node names) must exactly match what `skill_extractor.py` returns. Case-sensitive.
- The readiness score formula (Coverage + Proximity) must stay deterministic — no random elements.
- `GET /report/` must return a `StreamingResponse` with `media_type="application/pdf"`. Do not save PDFs to disk.
- SQLite tables are created automatically on startup. Never require manual DB setup in development.
- The frontend is a single `index.html` file with no build step. Keep it that way unless explicitly migrating to a framework.
