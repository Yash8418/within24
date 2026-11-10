from tests.conftest import register

SHIFT = {"starts_at": "2026-11-02T09:00:00-05:00", "ends_at": "2026-11-02T15:30:00-05:00"}


def create_job(client, headers, **overrides):
    body = {"name": "Cashier", "employer": "Grocery store", "job_type": "off_campus", **overrides}
    response = client.post("/jobs", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def create_shift(client, headers, job_id, **overrides):
    response = client.post("/shifts", json={**SHIFT, "job_id": job_id, **overrides}, headers=headers)
    return response


# ---------- Jobs ----------
def test_create_list_update_delete_job(client, auth_headers):
    job = create_job(client, auth_headers)
    assert client.get("/jobs", headers=auth_headers).json() == [job]

    updated = client.patch(f"/jobs/{job['id']}", json={"hourly_rate": 17.6}, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["hourly_rate"] == 17.6
    assert updated.json()["name"] == "Cashier"

    assert client.delete(f"/jobs/{job['id']}", headers=auth_headers).status_code == 204
    assert client.get("/jobs", headers=auth_headers).json() == []


def test_unknown_job_type_is_rejected(client, auth_headers):
    response = client.post("/jobs", json={"name": "X", "job_type": "volunteer"}, headers=auth_headers)
    assert response.status_code == 422


def test_users_cannot_see_or_change_each_others_jobs(client, auth_headers):
    job = create_job(client, auth_headers)
    other = register(client, email="other@example.com")
    assert client.get("/jobs", headers=other).json() == []
    assert client.patch(f"/jobs/{job['id']}", json={"name": "Hacked"}, headers=other).status_code == 404
    assert client.delete(f"/jobs/{job['id']}", headers=other).status_code == 404


# ---------- Shifts ----------
def test_create_shift_reports_counted_minutes(client, auth_headers):
    job = create_job(client, auth_headers)
    response = create_shift(client, auth_headers, job["id"])
    assert response.status_code == 201, response.text
    assert response.json()["counted_minutes"] == 390


def test_gig_shift_counts_only_earning_minutes(client, auth_headers):
    job = create_job(client, auth_headers, name="Delivery", job_type="gig")
    response = create_shift(client, auth_headers, job["id"], earning_minutes=200)
    assert response.json()["counted_minutes"] == 200


def test_shift_validation_errors(client, auth_headers):
    job_id = create_job(client, auth_headers)["id"]
    backwards = create_shift(client, auth_headers, job_id, ends_at="2026-11-02T08:00:00-05:00")
    assert backwards.status_code == 422
    too_long = create_shift(client, auth_headers, job_id, ends_at="2026-11-03T15:30:00-05:00")
    assert too_long.status_code == 422
    no_timezone = create_shift(client, auth_headers, job_id, starts_at="2026-11-02T09:00:00")
    assert no_timezone.status_code == 422
    earning_too_long = create_shift(client, auth_headers, job_id, earning_minutes=999)
    assert earning_too_long.status_code == 422


def test_list_shifts_filters_by_date_range(client, auth_headers):
    job_id = create_job(client, auth_headers)["id"]
    create_shift(client, auth_headers, job_id)
    create_shift(
        client, auth_headers, job_id, starts_at="2026-11-10T09:00:00-05:00", ends_at="2026-11-10T13:00:00-05:00"
    )
    week = client.get(
        "/shifts",
        params={"start": "2026-11-02T00:00:00-05:00", "end": "2026-11-09T00:00:00-05:00"},
        headers=auth_headers,
    )
    assert week.status_code == 200
    assert len(week.json()) == 1
    assert len(client.get("/shifts", headers=auth_headers).json()) == 2


def test_cannot_add_shift_to_someone_elses_job(client, auth_headers):
    job_id = create_job(client, auth_headers)["id"]
    other = register(client, email="other@example.com")
    assert create_shift(client, other, job_id).status_code == 404


def test_update_and_delete_shift(client, auth_headers):
    job_id = create_job(client, auth_headers)["id"]
    shift_id = create_shift(client, auth_headers, job_id).json()["id"]
    updated = client.put(
        f"/shifts/{shift_id}",
        json={"job_id": job_id, "starts_at": "2026-11-02T09:00:00-05:00", "ends_at": "2026-11-02T12:00:00-05:00"},
        headers=auth_headers,
    )
    assert updated.json()["counted_minutes"] == 180
    assert client.delete(f"/shifts/{shift_id}", headers=auth_headers).status_code == 204
    assert client.get("/shifts", headers=auth_headers).json() == []


def test_deleting_a_job_deletes_its_shifts(client, auth_headers):
    job_id = create_job(client, auth_headers)["id"]
    create_shift(client, auth_headers, job_id)
    client.delete(f"/jobs/{job_id}", headers=auth_headers)
    assert client.get("/shifts", headers=auth_headers).json() == []


def test_offsets_are_kept_when_saving_and_filtering(client, auth_headers):
    job_id = client.post("/jobs", json={"name": "Cashier", "job_type": "off_campus"}, headers=auth_headers).json()["id"]
    # 9 pm Sunday in Toronto is already Monday in UTC.
    created = create_shift(
        client, auth_headers, job_id, starts_at="2026-11-08T21:00:00-05:00", ends_at="2026-11-08T23:00:00-05:00"
    )
    assert created.json()["starts_at"] == "2026-11-09T02:00:00Z"

    sunday = {"start": "2026-11-08T00:00:00-05:00", "end": "2026-11-09T00:00:00-05:00"}
    listed = client.get("/shifts", params=sunday, headers=auth_headers).json()
    assert [s["id"] for s in listed] == [created.json()["id"]]
    assert listed[0]["starts_at"] == "2026-11-09T02:00:00Z"  # read back from the database
