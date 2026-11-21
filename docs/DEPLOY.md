# Deploying LeadPilot

Backend, worker, Postgres and Redis go on **Render** (Blueprint in `render.yaml`); the React
app goes on **Vercel**. Total time: about 20 minutes.

## 1. Backend on Render

1. Push the repo to GitHub (already done if you're reading this there).
2. Render dashboard → **New → Blueprint** → select the repo. Render reads `render.yaml` and
   proposes: `leadpilot-db` (Postgres), `leadpilot-redis` (Key Value), `leadpilot-api` (web),
   `leadpilot-worker` (Celery worker + Beat).
3. Fill the variables marked *sync: false* (you can leave AI and Razorpay empty to start):
   - `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`: your Vercel URL (step 2),
     e.g. `https://leadpilot.vercel.app`. You can set them after the frontend exists.
   - `GROQ_API_KEY` (or `ANTHROPIC_API_KEY`) for real AI; empty = offline placeholders.
   - `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` / `RAZORPAY_WEBHOOK_SECRET`: **test** keys.
4. **Apply.** The first deploy runs migrations (which also enable the `vector` extension).
5. Load demo data once: `leadpilot-api` → **Shell** →
   ```bash
   python manage.py seed_demo --flush
   ```
6. Check `https://leadpilot-api.onrender.com/api/health/` → `{"status":"ok","database":"ok"}`
   and `/api/docs/` for Swagger.

**Notes**
- `EMBEDDINGS_BACKEND=hash` keeps the API inside a small instance. For the real
  `all-MiniLM-L6-v2` model, use an instance with ≥1 GB RAM, add
  `pip install -r requirements-embeddings.txt` to the build command, set
  `EMBEDDINGS_BACKEND=sentence-transformers`, then run `python manage.py reindex_all`.
- Render workers are a paid instance type. Without the worker the app still works, but
  background jobs (nightly rescoring, task reminders) won't run; set Celery to eager mode
  only for demos.

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import the repo → **Root Directory: `frontend`**.
2. Environment variable: `VITE_API_URL = https://leadpilot-api.onrender.com`
3. Deploy. `vercel.json` rewrites every path to `index.html` (client-side routing).
4. Copy the Vercel URL into the Render variables `CORS_ALLOWED_ORIGINS`,
   `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL`, then redeploy the API.

## 3. Razorpay webhook (production)

Razorpay (Test Mode) → Settings → Webhooks → add
`https://leadpilot-api.onrender.com/api/billing/webhook/` with events `payment.captured`,
`payment.failed`, `payment_link.paid`, and the same secret as `RAZORPAY_WEBHOOK_SECRET`.

## 4. Smoke test

Log in with `admin` / `LeadPilot@123` (change these passwords for any public demo:
`python manage.py changepassword admin`), open the dashboard, drag a deal to Won, create an
invoice and pay it with test card `4111 1111 1111 1111`.

## Production settings at a glance (`config/settings/prod.py`)

`DEBUG = False`; `DJANGO_SECRET_KEY` required; HTTPS redirect, secure cookies, HSTS
(subdomains/preload opt-in via env); WhiteNoise for static files; Redis cache; CORS/CSRF from
env; login and AI endpoints rate-limited; Razorpay live keys refused.
