# ⏱️ Within24

**Work-hours tracker for international students in Canada.** Log shifts from every job — retail, restaurant, on-campus, delivery apps — and see at a glance whether you're within the 24-hour weekly off-campus limit on your study permit.

> 🚧 Work in progress.

## The problem

International students in Canada can work up to **24 hours per week off campus** during academic terms. Going over is a breach of study permit conditions. But staying within the limit is harder than it sounds:

- Hours from **several employers** all count toward the same 24 — and no single employer sees the total.
- **Gig work** (delivery, rideshare) counts time spent earning wages or commission, not just time logged into the app.
- **On-campus** work has no weekly limit, and **scheduled academic breaks** allow full-time work — but only breaks that qualify.
- Students are expected to be able to **show their hours** if asked, but few keep records.

## Planned features

- One weekly total across all jobs, separating on-campus, off-campus and gig hours
- "Can I take this shift?" check before accepting extra hours
- Scheduled-break calendar so full-time weeks during breaks are handled correctly
- Versioned rules engine where every rule links to its official source
- Conservative week checks (calendar week **and** any rolling 7-day window)
- CSV import for gig earnings
- Downloadable PDF hours record

## Tech stack

FastAPI · SQLAlchemy · PostgreSQL · React · JWT auth · pytest · Docker · GitHub Actions

## Disclaimer

Within24 helps you keep track of your own hours. It is **not legal or immigration advice**. Always check the official rules from Immigration, Refugees and Citizenship Canada (IRCC) and speak to your school's international student office or a licensed immigration professional if you're unsure.
