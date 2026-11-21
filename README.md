# Lead-Pilot

LeadPilot is an AI-powered CRM for small businesses: Django + React, with ML lead scoring,
GenAI writing, RAG search, a tool-calling agent with human approval, and Razorpay payments
(test mode). The full spec is in [CLAUDE.md](CLAUDE.md).

> Status: **Phase 1 (auth + core CRM)** done: JWT login with roles, companies, contacts
> (CSV import, activity timeline), leads and tasks. Later features arrive phase by phase.

## Demo data and logins

```bash
cd backend
python manage.py seed_demo          # add --flush to wipe and re-seed
```

Creates 50 companies, 300 contacts, 400 leads, 500 activities and 120 tasks.
Every demo user has the password `LeadPilot@123`:

| Username | Role      | Sees                                         |
| -------- | --------- | -------------------------------------------- |
| `admin`  | Admin     | Everything, all reps' data, user management  |
| `priya`  | Sales Rep | Only her own companies, contacts, leads, tasks |
| `rahul`  | Sales Rep | Only his own records                         |
| `sneha`  | Support   | All contacts (read-only); tickets from Phase 3 |

## API (so far)

| Endpoint                                   | Notes                                            |
| ------------------------------------------ | ------------------------------------------------ |
| `POST /api/auth/login/`                    | `{username, password}` → access, refresh, user   |
| `POST /api/auth/refresh/` · `GET /api/auth/me/` | Token refresh, current user                 |
| `POST /api/auth/register/`                 | Admin only (no public sign-up)                   |
| `/api/crm/companies/` `contacts/` `leads/` `activities/` `tasks/` | CRUD with `search`, filters, `ordering`, `page`, `page_size` |
| `POST /api/crm/contacts/import/`           | Multipart `file` (CSV); returns per-row errors   |

Full, interactive docs: http://localhost:8000/api/docs/

## Stack

| Layer    | Tech                                                                    |
| -------- | ----------------------------------------------------------------------- |
| Backend  | Python 3.11, Django 5, DRF, SimpleJWT, django-filter, drf-spectacular   |
| Data     | PostgreSQL 16 + pgvector, Redis                                         |
| Async    | Celery worker + Celery Beat                                             |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, React Router, TanStack Query  |
| Quality  | pytest, Vitest, ruff, black, ESLint, Prettier, pre-commit, GitHub Actions |

## Run with Docker (recommended)

Needs Docker Desktop.

```bash
cp .env.example .env          # then edit values if needed
docker compose up --build
```

This starts 6 services: `postgres`, `redis`, `backend`, `celery`, `celery-beat`, `frontend`.

| What           | URL                               |
| -------------- | --------------------------------- |
| App            | http://localhost:5173             |
| API health     | http://localhost:8000/api/health/ |
| Swagger docs   | http://localhost:8000/api/docs/   |
| Django admin   | http://localhost:8000/admin/      |

Create an admin user:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Run without Docker

Needs Python 3.11+ and Node 22+. Without `DATABASE_URL` the backend uses a local SQLite file,
which is fine for Phases 0–4. Phase 5 (pgvector) needs Postgres.

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver        # http://localhost:8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to :8000
```

Celery needs Redis; outside Docker run `celery -A config worker --pool=solo -l info`.

## Tests and linting

```bash
cd backend && pytest --cov                 # backend tests
cd backend && ruff check . && black --check .

cd frontend && npm test                    # Vitest
cd frontend && npm run lint && npm run typecheck
```

Install the git hooks once with `pip install pre-commit && pre-commit install`.
CI (`.github/workflows/ci.yml`) runs lint, tests and the frontend build on every push and PR.

## Project layout

```
backend/   config/ (settings base/dev/prod/test, urls, celery)
           accounts/ crm/ support/ ml/ genai/ agent/ billing/ analytics/ common/
frontend/  src/ api/ components/ hooks/ layouts/ pages/ routes/
```

## Roadmap

- [x] Phase 0: Setup & skeleton
- [x] Phase 1: Auth + core CRM
- [ ] Phase 2: Pipeline, tasks & dashboard
- [ ] Phase 3: ML models
- [ ] Phase 4: GenAI writer & summarizer
- [ ] Phase 5: RAG (Ask LeadPilot)
- [ ] Phase 6: Agent
- [ ] Phase 7: Invoicing & Razorpay
- [ ] Phase 8: Testing, polish & deploy
