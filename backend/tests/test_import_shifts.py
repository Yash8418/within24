from tests.conftest import register

CSV = "date,start,end,active_hours\n2026-11-03,18:00,21:30,2.5\n2026-11-04,22:00,01:00,\n"


def make_job(client, headers, job_type="gig"):
    return client.post("/jobs", json={"name": "Deliveries", "job_type": job_type}, headers=headers).json()["id"]


def test_preview_then_import(client, auth_headers):
    job = make_job(client, auth_headers)
    preview = client.post("/shifts/import", json={"job_id": job, "csv": CSV}, headers=auth_headers).json()
    assert preview["dry_run"] is True and preview["imported"] == 0
    assert [r["earning_minutes"] for r in preview["rows"]] == [150, None]
    assert preview["rows"][0]["starts_at"] == "2026-11-03T23:00:00Z"
    assert client.get("/shifts", headers=auth_headers).json() == []

    done = client.post("/shifts/import", json={"job_id": job, "csv": CSV, "dry_run": False}, headers=auth_headers)
    assert done.json()["imported"] == 2
    shifts = client.get("/shifts", headers=auth_headers).json()
    assert {s["source"] for s in shifts} == {"csv_import"}

    # Importing the same file again skips both rows as duplicates.
    again = client.post("/shifts/import", json={"job_id": job, "csv": CSV, "dry_run": False}, headers=auth_headers)
    assert again.json()["imported"] == 0
    assert all(r["duplicate"] for r in again.json()["rows"])


def test_nothing_is_saved_when_any_row_is_invalid(client, auth_headers):
    job = make_job(client, auth_headers)
    bad = CSV + "2026-11-05,25:00,26:00,\n"
    body = client.post("/shifts/import", json={"job_id": job, "csv": bad, "dry_run": False}, headers=auth_headers)
    assert body.json()["imported"] == 0
    assert body.json()["errors"][0]["line"] == 4
    assert client.get("/shifts", headers=auth_headers).json() == []


def test_imported_gig_hours_count_by_earning_time(client, auth_headers):
    job = make_job(client, auth_headers)
    client.post("/shifts/import", json={"job_id": job, "csv": CSV, "dry_run": False}, headers=auth_headers)
    week = client.get("/summary", params={"date": "2026-11-03"}, headers=auth_headers).json()["week"]
    assert week["minutes"] == 150 + 180


def test_cannot_import_into_someone_elses_job(client, auth_headers):
    job = make_job(client, auth_headers)
    other = register(client, "other@example.com")
    response = client.post("/shifts/import", json={"job_id": job, "csv": CSV}, headers=other)
    assert response.status_code == 404
