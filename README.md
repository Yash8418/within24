# ⏱️ Within24

**Work-hours tracker for international students in Canada.** Log shifts from every job — retail, restaurant, on-campus, delivery apps — and see at a glance whether you're within the 24-hour weekly off-campus limit on your study permit.

## The problem

International students in Canada can work up to **24 hours per week off campus** during academic terms. Going over is a breach of study permit conditions. But staying within the limit is harder than it sounds:

- Hours from **several employers** all count toward the same 24 — and no single employer sees the total.
- **Gig work** (delivery, rideshare) counts time spent earning wages or commission, not just time logged into the app.
- **On-campus** work has no weekly limit, and **scheduled academic breaks** allow full-time work — but only breaks that qualify.
- Students are expected to be able to **show their hours** if asked, but few keep records.

## Features

- **One weekly total** across all jobs, separating on-campus, off-campus and gig hours
- **"Can I take this shift?"** — checks a proposed shift before you accept it
- **Scheduled breaks** — off-campus hours during your school's official breaks aren't counted
- **Conservative week checks** — the Monday–Sunday week *and* the busiest rolling 7-day window
- **Versioned rules engine** — every rule links to its official IRCC source and the date it was checked
- **CSV import** for gig-app exports, with a preview, duplicate detection and all-or-nothing saves
- **PDF hours record** with weekly totals, breaks and every shift — for your records or an advisor

## Tech stack

FastAPI · SQLAlchemy · PostgreSQL · React · JWT auth · pytest · Docker · GitHub Actions

## Run it locally

```bash
# API (SQLite by default)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload          # http://localhost:8000/docs

# Frontend
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

Or run the API with PostgreSQL: `docker compose up --build`.

## Deploy

| Part | Where | Setup |
|---|---|---|
| Database | [Neon](https://neon.tech) (free PostgreSQL) | Create a project and copy its connection string |
| API | [Render](https://render.com) (free web service) | *New → Blueprint* → this repo ([`render.yaml`](render.yaml)); paste the connection string as `DATABASE_URL` |
| Frontend | GitHub Pages | *Settings → Pages → Source: GitHub Actions*; add the repository variable `API_URL` = the Render URL; run **Publish frontend** |

The free Render service sleeps after 15 minutes without traffic, so the first request after a pause takes about a minute.

## Disclaimer

Within24 helps you keep track of your own hours. It is **not legal or immigration advice**. Always check the official rules from Immigration, Refugees and Citizenship Canada (IRCC) and speak to your school's international student office or a licensed immigration professional if you're unsure.
