# Career Architect

> A knowledge-graph-based learning assessment system that analyzes a student's skills, computes prerequisite gaps, and generates a structured roadmap and readiness score for a target technical career.

---

## Project Structure

```
career_architect/
├── app/
│   ├── main.py              # FastAPI app, router registration
│   ├── database.py          # SQLite engine + session factory
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # Database operations
│   ├── graph_engine.py      # Knowledge graph + gap analysis (core engine)
│   │
│   ├── routes/              # HTTP endpoints (thin layer — no logic)
│   │   ├── health.py
│   │   ├── skills.py
│   │   ├── roadmap.py
│   │   ├── extract.py
│   │   ├── graph_data.py
│   │   ├── readiness.py
│   │   ├── study_plan.py
│   │   ├── report.py
│   │   ├── github_scan.py
│   │   └── feedback.py
│   │
│   ├── ai/                  # AI/extraction logic
│   │   ├── skill_extractor.py   # LLM + keyword fallback
│   │   └── github_scanner.py    # GitHub profile scanner
│   │
│   └── analytics/           # Scoring and planning
│       ├── readiness.py         # 0–100 readiness score engine
│       ├── planner.py           # Semester study plan generator
│       └── report.py            # Academic PDF report generator
│
├── index.html               # Single-page frontend (D3 graph visualization)
├── requirements.txt
└── .env.example
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment (optional — app works without these)
cp .env.example .env
# Edit .env to add OPENAI_API_KEY and/or GITHUB_TOKEN

# 3. Run the server
uvicorn app.main:app --reload

# 4. Open API docs
open http://localhost:8000/docs

# 5. Open frontend
open index.html   # or serve it via any static file server
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| POST | `/extract-skills/` | Extract skills from resume text |
| POST | `/scan-github/` | Scan GitHub profile for skills |
| POST | `/roadmap/` | Generate prerequisite-ordered learning roadmap |
| GET | `/roadmap/graph-info` | Knowledge graph metadata |
| POST | `/graph-data/` | Graph nodes + edges for D3 visualization |
| POST | `/readiness/` | Compute 0–100 career readiness score |
| POST | `/study-plan/` | Generate week-by-week study schedule |
| GET | `/report/` | Download academic PDF report |
| POST | `/feedback/` | Submit skill extraction rating |
| GET | `/feedback/summary` | Aggregate feedback stats |

## Knowledge Graph

- **83 skills** across 6 domains: Programming, Math, ML/AI, Engineering, Web, Data Engineering
- **7 target roles**: AI Researcher, ML Engineer, Backend Engineer, Data Scientist, Full-Stack Developer, MLOps Engineer, Data Engineer
- Gap analysis uses NetworkX shortest-path (Dijkstra) to find prerequisite chains
- Readiness score = Coverage (0–60) + Proximity (0–40), fully explainable

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite, NetworkX
- **PDF**: ReportLab
- **Frontend**: Vanilla JS + D3.js (force-directed graph)
- **AI**: OpenAI-compatible API (optional) + deterministic keyword fallback
