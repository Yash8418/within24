from tests.conftest import register


def add_job(client, headers, job_type="off_campus", name="Cashier"):
    return client.post("/jobs", json={"name": name, "job_type": job_type}, headers=headers).json()["id"]


def add_shift(client, headers, job_id, day, start="09:00", end="17:00"):
    body = {"job_id": job_id, "starts_at": f"2026-11-{day}T{start}:00-05:00", "ends_at": f"2026-11-{day}T{end}:00-05:00"}
    assert client.post("/shifts", json=body, headers=headers).status_code == 201


def check(client, headers, job_id, day, start="09:00", end="17:00", **extra):
    body = {
        "job_id": job_id,
        "starts_at": f"2026-11-{day}T{start}:00-05:00",
        "ends_at": f"2026-11-{day}T{end}:00-05:00",
        **extra,
    }
    response = client.post("/check-shift", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_shift_that_fits(client, auth_headers):
    job = add_job(client, auth_headers)
    add_shift(client, auth_headers, job, "02")
    result = check(client, auth_headers, job, "04")
    assert result["allowed"] is True
    assert result["weeks"][0]["minutes_before"] == 480
    assert result["weeks"][0]["minutes_after"] == 960
    assert "You can take this shift" in result["message"]
    assert "16 of 24 hours" in result["message"]


def test_shift_that_would_go_over(client, auth_headers):
    job = add_job(client, auth_headers)
    for day in ("02", "03", "04"):
        add_shift(client, auth_headers, job, day)  # 24 h already
    result = check(client, auth_headers, job, "06", "09:00", "11:00")
    assert result["allowed"] is False
    assert result["weeks"][0]["status_after"] == "over"
    assert "26 hours" in result["message"]


def test_rolling_window_blocks_a_shift_that_fits_its_calendar_week(client, auth_headers):
    job = add_job(client, auth_headers)
    for day in ("05", "06", "09"):  # Thu, Fri, Mon: 24 h in 5 days
        add_shift(client, auth_headers, job, day)
    result = check(client, auth_headers, job, "10")  # Tue: 16 h in its calendar week
    assert result["weeks"][0]["status_after"] == "ok"
    assert result["rolling_peak_status_after"] == "over"
    assert result["allowed"] is False


def test_checking_does_not_save_anything(client, auth_headers):
    job = add_job(client, auth_headers)
    check(client, auth_headers, job, "04")
    assert client.get("/shifts", headers=auth_headers).json() == []


def test_on_campus_shift_is_always_allowed(client, auth_headers):
    store = add_job(client, auth_headers)
    library = add_job(client, auth_headers, "on_campus", "Library")
    for day in ("02", "03", "04"):
        add_shift(client, auth_headers, store, day)
    result = check(client, auth_headers, library, "05")
    assert result["allowed"] is True
    assert result["counts_toward_limit"] is False
    assert "On-campus" in result["message"]


def test_gig_shift_counts_only_earning_time(client, auth_headers):
    job = add_job(client, auth_headers, "gig", "Delivery")
    result = check(client, auth_headers, job, "04", "17:00", "22:00", earning_minutes=150)
    assert result["counted_minutes"] == 150


def test_overnight_shift_reports_both_weeks(client, auth_headers):
    job = add_job(client, auth_headers)
    body = {"job_id": job, "starts_at": "2026-11-08T20:00:00-05:00", "ends_at": "2026-11-09T04:00:00-05:00"}
    result = client.post("/check-shift", json=body, headers=auth_headers).json()
    assert [w["week_start"] for w in result["weeks"]] == ["2026-11-02", "2026-11-09"]
    assert [w["minutes_after"] for w in result["weeks"]] == [240, 240]


def test_editing_a_shift_excludes_the_old_version(client, auth_headers):
    job = add_job(client, auth_headers)
    add_shift(client, auth_headers, job, "02")
    shift_id = client.get("/shifts", headers=auth_headers).json()[0]["id"]
    result = check(client, auth_headers, job, "02", "09:00", "19:00", replaces_shift_id=shift_id)
    assert result["weeks"][0]["minutes_after"] == 600


def test_cannot_check_against_someone_elses_job(client, auth_headers):
    job = add_job(client, auth_headers)
    other = register(client, email="other@example.com")
    body = {"job_id": job, "starts_at": "2026-11-04T09:00:00-05:00", "ends_at": "2026-11-04T17:00:00-05:00"}
    assert client.post("/check-shift", json=body, headers=other).status_code == 404


def test_shift_during_a_break_is_allowed_and_not_counted(client, auth_headers):
    job = client.post("/jobs", json={"name": "Cashier", "job_type": "off_campus"}, headers=auth_headers).json()["id"]
    client.post("/breaks", json={"name": "Summer", "start_date": "2027-05-01", "end_date": "2027-08-31"},
                headers=auth_headers)
    shift = {"job_id": job, "starts_at": "2027-06-01T08:00:00-04:00", "ends_at": "2027-06-01T20:00:00-04:00"}
    for _ in range(3):  # 36 h already that week
        client.post("/shifts", json=shift, headers=auth_headers)
    body = client.post("/check-shift", json=shift, headers=auth_headers).json()
    assert body["allowed"] is True
    assert body["counted_minutes"] == 0
    assert "scheduled break" in body["message"]
