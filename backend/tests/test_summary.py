from tests.conftest import register


def add_job(client, headers, job_type="off_campus", name="Cashier"):
    return client.post("/jobs", json={"name": name, "job_type": job_type}, headers=headers).json()["id"]


def add_shift(client, headers, job_id, start, end, **extra):
    response = client.post("/shifts", json={"job_id": job_id, "starts_at": start, "ends_at": end, **extra}, headers=headers)
    assert response.status_code == 201, response.text


def test_rules_endpoint_lists_sources(client):
    body = client.get("/rules").json()
    assert body["off_campus_weekly_limit_hours"] == 24
    assert all(rule["sources"] for rule in body["rules"])


def test_summary_totals_this_week_across_jobs(client, auth_headers):
    store = add_job(client, auth_headers)
    delivery = add_job(client, auth_headers, "gig", "Delivery")
    library = add_job(client, auth_headers, "on_campus", "Library")
    add_shift(client, auth_headers, store, "2026-11-02T09:00:00-05:00", "2026-11-02T17:00:00-05:00")  # 8 h
    add_shift(client, auth_headers, delivery, "2026-11-04T17:00:00-05:00", "2026-11-04T22:00:00-05:00",
              earning_minutes=180)  # 3 h counted
    add_shift(client, auth_headers, library, "2026-11-05T09:00:00-05:00", "2026-11-05T19:00:00-05:00")  # not counted

    body = client.get("/summary", params={"date": "2026-11-06"}, headers=auth_headers).json()
    assert body["week"]["start"] == "2026-11-02"
    assert body["week"]["minutes"] == 660
    assert body["week"]["remaining_minutes"] == 780
    assert body["week"]["status"] == "ok"

    by_job = {j["name"]: j for j in body["by_job"]}
    assert by_job["Cashier"]["minutes"] == 480
    assert by_job["Delivery"]["minutes"] == 180
    assert by_job["Library"]["minutes"] == 600
    assert by_job["Library"]["counts_toward_limit"] is False


def test_summary_flags_rolling_window_over_the_limit(client, auth_headers):
    job = add_job(client, auth_headers)
    for day in ("05", "06", "09", "10"):  # Thu, Fri, then Mon, Tue: 32 h within 6 days
        add_shift(client, auth_headers, job, f"2026-11-{day}T09:00:00-05:00", f"2026-11-{day}T17:00:00-05:00")

    body = client.get("/summary", params={"date": "2026-11-09"}, headers=auth_headers).json()
    assert body["week"]["minutes"] == 960 and body["week"]["status"] == "ok"
    assert body["rolling_peak"]["minutes"] == 1920
    assert body["rolling_peak"]["status"] == "over"


def test_recent_weeks_history(client, auth_headers):
    job = add_job(client, auth_headers)
    add_shift(client, auth_headers, job, "2026-10-20T09:00:00-04:00", "2026-10-20T13:00:00-04:00")
    body = client.get("/summary", params={"date": "2026-11-06", "weeks_back": 4}, headers=auth_headers).json()
    assert [w["week_start"] for w in body["recent_weeks"]] == ["2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"]
    assert [w["minutes"] for w in body["recent_weeks"]] == [0, 240, 0, 0]


def test_summary_is_private_and_requires_login(client, auth_headers):
    job = add_job(client, auth_headers)
    add_shift(client, auth_headers, job, "2026-11-02T09:00:00-05:00", "2026-11-02T17:00:00-05:00")
    other = register(client, email="other@example.com")
    assert client.get("/summary", params={"date": "2026-11-06"}, headers=other).json()["week"]["minutes"] == 0
    assert client.get("/summary").status_code == 401


def test_summary_rejects_dates_before_supported_rules(client, auth_headers):
    assert client.get("/summary", params={"date": "2024-01-15"}, headers=auth_headers).status_code == 422
