# Lead-Pilot

LeadPilot is an AI-powered CRM for small businesses: Django + React, with ML lead scoring,
GenAI writing, RAG search, a tool-calling agent with human approval, and Razorpay payments
(test mode). The full spec is in [CLAUDE.md](CLAUDE.md).

> Status: **Phase 3 (ML models)** done: JWT login with roles; companies, contacts (CSV
> import, activity timeline), leads and tasks; a drag-and-drop deal pipeline and KPI dashboard;
> support tickets; and five ML models (lead scoring with SHAP explanations, churn, RFM
> segmentation, ticket sentiment → priority, revenue forecast). Later features arrive phase by
> phase.

## Demo data and logins

```bash
cd backend
python manage.py seed_demo          # add --flush to wipe and re-seed
```

Creates 50 companies, 300 contacts, 400 leads, 150 pipeline deals plus 240 closed deals of
24-month history (for forecasting and segmentation), 500 activities, 120 tasks, 80 tickets and
invoices for recent won deals (demo payments use fake `pay_demo_…` ids).
If trained models exist it also scores every lead and segments customers.
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
| `/api/crm/deals/` · `GET deals/board/`     | Deals CRUD; Kanban columns with count + total    |
| `POST /api/crm/deals/<id>/move/`           | `{stage, position}`, atomic reorder              |
| `POST /api/crm/leads/<id>/convert/`        | Creates a deal, marks the lead converted         |
| `GET /api/analytics/summary/`              | Dashboard KPIs (cached 60 s, refreshed on change) |
| `/api/support/tickets/` (+ `comments/`)    | Tickets; sentiment + priority set automatically   |
| `POST /api/ml/score-lead/<id>/`            | Score one lead now (score, label, SHAP factors)  |
| `GET /api/ml/metrics/` · `forecast/` · `segments/` | Model metrics, revenue forecast, segments |
| `POST /api/ml/retrain/` · `rescore-all/`   | Admin only                                       |
| `POST /api/genai/draft-email/`             | `{contact_id, goal, tone}` → `{subject, body}`   |
| `POST /api/genai/summarize-activity/`      | `{activity_id}` → summary, action items, sentiment |
| `POST /api/genai/action-items-to-tasks/`   | `{activity_id, items: [index…]}` → tasks         |
| `POST /api/genai/ask/`                     | `{question, conversation_id?}` → answer + citations |
| `/api/genai/conversations/`                | Your Ask LeadPilot chat history                  |
| `POST /api/agent/runs/` · `GET runs/<id>/` | Start an agent run with `{goal}`; poll its steps |
| `POST /api/agent/steps/<id>/approve/` · `reject/` | Decide a pending write step                |
| `/api/billing/invoices/` (+ `create-order/`, `payment-link/`) | Invoices from Won deals; Razorpay order/link |
| `POST /api/billing/verify/`                | Checkout signature check → invoice processing    |
| `POST /api/billing/webhook/`               | Razorpay webhook (no auth, HMAC-verified, idempotent) |
| `POST /api/billing/payments/<id>/refund/`  | Admin only                                       |

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

Celery needs Redis; outside Docker run `celery -A config worker --pool=solo -l info` and
`celery -A config beat -l info`. Beat sends overdue-task reminders daily at 08:00 IST (printed
to the worker log in dev). To try it now: `python manage.py shell -c "from crm.tasks import
send_overdue_task_reminders as t; print(t())"`.

## Machine learning

Five models, each explored in a notebook (`backend/ml/notebooks/`) and shipped as a pipeline
(`backend/ml/pipelines/`). Trained models + metrics JSON live in `backend/ml/models/` and are
committed (all < 120 KB), so the app works right after cloning.

| Model | Trained on | Chosen (by CV) | Test result |
| --- | --- | --- | --- |
| Lead scoring | X Education leads (9,240) | XGBoost | ROC-AUC 0.858 · F1 0.749 |
| Churn | IBM Telco (7,043 customers) | XGBoost | ROC-AUC 0.834 · recall 0.80 |
| Segmentation | UCI Online Retail (4,338 customers) | K-Means, k=4 on RFM percentiles | silhouette 0.383 |
| Ticket sentiment | UCI labelled sentences (3,000) | TF-IDF + Logistic Regression | ROC-AUC 0.906 · F1 0.835 |
| Forecast | LeadPilot won deals by month | best of 3 regressions + 2 baselines in a 9-month backtest | see ML Insights |

Public datasets use different columns than a CRM, so every model trains on a small **shared
feature space** that `ml/features.py` can also compute from LeadPilot records (money and
counts as within-dataset percentiles). Scores refresh automatically: editing a lead or logging
an activity rescores it (Celery), winning a deal refreshes segments and churn, new tickets are
classified on save, and nightly Beat jobs rescore everything. A missing model never breaks the
CRM: fields stay empty and the API answers 503.

```bash
cd backend
python manage.py ml_download_data      # public datasets -> ml/data/raw (gitignored)
python manage.py ml_train              # train all (or: ml_train lead_score churn ...)
python ml/notebooks/run_notebooks.py   # execute every notebook top to bottom
```

## Generative AI

All LLM calls go through one wrapper, `backend/genai/llm.py` (`chat(messages, tools=None,
json_schema=None)`), with timeouts, retries with backoff and a token-usage log (`LLMCall`).
Providers: **Groq** (default, `GROQ_API_KEY`), **Claude** via the official Anthropic SDK
(`ANTHROPIC_API_KEY`, model `claude-opus-5-5`), OpenAI, or an offline mock that returns
placeholders when no key is set. Prompts are text files in `backend/genai/prompts/`; JSON
output is validated with Pydantic and retried once before failing with a clean 502.
CRM text is fenced as untrusted data, so notes saying "ignore previous instructions" are
treated as data (tested).

- **Draft with AI** (contact page): follow-up email from the last 10 activities + deals.
- **Summarize** (long activities): summary, sentiment and action items → tasks.
- 20 AI requests per minute per user (`GENAI_RATE_LIMIT`).
- **Ask LeadPilot** (RAG): activities, tickets and lead notes are chunked (~500 chars, 50
  overlap), embedded with `all-MiniLM-L6-v2` (384-d) and stored in **pgvector** with an HNSW
  cosine index. A question is scoped to what the user may see, narrowed by any company/contact
  name or date phrase it contains ("last month"), then the top 5 chunks ground the answer,
  which cites its sources. Weak matches answer "I don't know" without calling the LLM.
  Signals + Celery keep the index fresh; `python manage.py reindex_all` rebuilds it.
  (On SQLite the same data is searched with NumPy, so it also works without Docker.)

## CRM agent

Give it a goal ("Find hot leads not contacted in 7 days, draft follow-ups and create tasks").
`backend/agent/agent.py` runs a tool-calling loop through the same LLM wrapper:

- **Read tools run automatically**: `search_leads`, `get_contact_history`, `draft_email`
  (drafts only, never sends), `ask_crm` (RAG).
- **Write tools pause the run for your approval**: `create_task`, `update_deal_stage` (plus
  invoice/payment-link tools from Phase 7). Rejecting a step tells the agent to skip it.
- Max 10 steps per run, every step logged (`AgentStep`), no delete or money-moving tools,
  everything scoped to the user's own data. Runs execute in Celery; the page polls every 2 s.
- Without an LLM key a labelled offline planner demonstrates the approval flow.

## Invoicing & Razorpay (test mode)

Invoice a **Won** deal (GST 18%), then collect with **Pay Now** (Razorpay Checkout) or a
**payment link** Razorpay emails to the customer. Money is stored as Decimal rupees and sent to
Razorpay in paise (₹499.50 → 49950). The key secret never reaches the browser, and only test
keys (`rzp_test_…`) are accepted; live keys are refused.

Flow: create order → Checkout.js → backend verifies the payment signature (invoice
"processing") → **webhook is the source of truth**: `payment.captured` / `payment_link.paid`
→ signature checked (`X-Razorpay-Signature`), event stored in `WebhookEvent` (duplicates are
skipped) → invoice paid, deal Won, "Payment received" activity, dashboard refreshed.
`payment.failed` marks the invoice failed. Admins can refund.

**Set up test mode**
1. Razorpay Dashboard → switch to **Test Mode** → Settings → API Keys → generate a key.
2. In `.env`: `RAZORPAY_KEY_ID=rzp_test_…`, `RAZORPAY_KEY_SECRET=…`.
3. Webhooks need a public URL. Run [ngrok](https://ngrok.com): `ngrok http 8000`, then in
   Razorpay → Settings → Webhooks add `https://<your-ngrok-id>.ngrok-free.app/api/billing/webhook/`
   with events `payment.captured`, `payment.failed`, `payment_link.paid`, and a secret →
   put the same secret in `RAZORPAY_WEBHOOK_SECRET`.
4. Pay with a [Razorpay test card](https://razorpay.com/docs/payments/payments/test-card-details/)
   (e.g. `4111 1111 1111 1111`, any future expiry, any CVV) and watch the invoice turn **Paid**.

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
- [x] Phase 2: Pipeline, tasks & dashboard
- [x] Phase 3: ML models
- [x] Phase 4: GenAI writer & summarizer
- [x] Phase 5: RAG (Ask LeadPilot)
- [x] Phase 6: Agent
- [x] Phase 7: Invoicing & Razorpay
- [ ] Phase 8: Testing, polish & deploy
