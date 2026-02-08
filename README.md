# QVest Reading Momentum POC

A proof-of-concept recommender for a school district library system. It uses lending history and the catalog to produce personalized book lists and clear rationales that librarians can trust. The POC is intentionally lightweight so it runs locally while still mirroring a production-ready architecture.

## What this demonstrates
- A collaborative-filtering style recommender based on historical co-borrowing.
- Simple, explainable rationales that can be swapped for LLM-generated explanations later.
- A minimal API plus a clean UI for demoing with partners.

## Architecture
```mermaid
flowchart LR
  subgraph Data
    A[Library Catalog]
    B[Loan History]
  end

  subgraph Services
    C[Ingestion + Validation]
    D[Recommender Engine]
    E[Explanation Layer]
  end

  subgraph Experience
    F[Librarian UI]
  end

  A --> C
  B --> C
  C --> D
  D --> E
  E --> F
```

```mermaid
sequenceDiagram
  participant L as Librarian UI
  participant API as Recommendation API
  participant R as Recommender
  participant D as Data Store

  L->>API: Request recommendations
  API->>D: Fetch catalog + loan history
  D-->>API: Data snapshot
  API->>R: Build similarity scores
  R-->>API: Ranked list + reasons
  API-->>L: Recommendations
```

## Repository layout
- `backend/app.py` FastAPI service
- `backend/recommender.py` co-occurrence recommender
- `backend/data_loader.py` CSV loader
- `data/` sample catalog, students, and loans
- `frontend/` static demo UI

## Quickstart
1. Create and activate the virtual environment:

```bash
python3 -m venv .qvest
source .qvest/bin/activate
```

2. Install dependencies:

```bash
pip install -r <(python - <<'PY'
import tomllib
import pathlib
pyproject = pathlib.Path('pyproject.toml').read_bytes()
config = tomllib.loads(pyproject)
print("\n".join(config["project"]["dependencies"]))
PY
)
```

3. Start the backend:

```bash
uvicorn backend.app:app --reload --port 8000
```

4. Open the frontend:
- Open `frontend/index.html` in a browser.

## API Examples
```bash
curl "http://localhost:8000/health"
```

```bash
curl "http://localhost:8000/recommendations?student_id=S001&k=5"
```

## Agent Lab (demo)
Front-end pages:
- `frontend/agents.html` hub
- `frontend/concierge.html` librarian concierge
- `frontend/onboarding.html` student onboarding
- `frontend/holds.html` availability & holds
- `frontend/gaps.html` collection gap analyst
- `frontend/feedback.html` feedback loop

Agent endpoints:
- `POST /agents/concierge`
- `GET /agents/onboarding/{student_id}`
- `POST /agents/onboarding`
- `GET /agents/availability`
- `GET /agents/holds`
- `POST /agents/holds`
- `POST /agents/holds/{hold_id}/cancel`
- `GET /agents/collection-gaps`
- `POST /agents/feedback`
- `GET /agents/feedback`
- `GET /agents/feedback/insights`
- `GET /agents/feedback/recommendations`

Agent state persistence lives in `data/agent_state.json`.

## How the POC works
- Build a student → books map from the loan history.
- Count how often pairs of books appear together.
- Score candidate books using cosine-style similarity.
- Provide human-readable reasons based on the closest book in a student’s history.

## LLM augmentation (next iteration)
The POC includes deterministic reasons for trust and reproducibility. In production, the explanation layer can call an LLM to:
- Tailor the language to student reading level.
- Highlight connections between themes and characters.
- Suggest read-alikes and librarian talking points.

## Rollout plan (proposal draft)
1. **Discovery (2-3 weeks)**
   - Validate data quality, privacy constraints, and catalog coverage.
   - Conduct librarian workshops to define recommendation success criteria.
2. **Pilot (4-6 weeks)**
   - Run on two schools with opt-in librarians.
   - Weekly feedback loops and model tuning.
3. **District rollout (6-8 weeks)**
   - Train-the-trainer model for librarians.
   - Add dashboards for reading outcomes and engagement.
4. **Operations (ongoing)**
   - Monthly data refresh and drift checks.
   - Quarterly model review and explanation audits.

## Estimated effort (full project)
- Data pipeline + privacy review: 4-6 weeks
- Recommendation system + evaluation: 4-5 weeks
- LLM explanation service + guardrails: 3-4 weeks
- UX + change management + rollout: 4-6 weeks
- Total: 15-21 weeks (can be compressed with parallel workstreams)

## Demo story for partners
- Show how a librarian picks a student and receives a ranked list.
- Explain why each recommendation is made.
- Discuss how LLMs can personalize tone without changing the core ranking.
- Close with a roadmap for production readiness.
