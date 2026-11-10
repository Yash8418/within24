from tests.conftest import register

WINTER = {"name": "Winter break", "start_date": "2026-12-19", "end_date": "2027-01-04"}


def test_create_list_update_delete_break(client, auth_headers):
    created = client.post("/breaks", json=WINTER, headers=auth_headers)
    assert created.status_code == 201
    break_id = created.json()["id"]

    reading = {"name": "Reading week", "start_date": "2026-10-10", "end_date": "2026-10-18"}
    client.post("/breaks", json=reading, headers=auth_headers)
    names = [b["name"] for b in client.get("/breaks", headers=auth_headers).json()]
    assert names == ["Reading week", "Winter break"]  # sorted by start date

    updated = client.put(f"/breaks/{break_id}", json={**WINTER, "end_date": "2027-01-06"}, headers=auth_headers)
    assert updated.json()["end_date"] == "2027-01-06"

    assert client.delete(f"/breaks/{break_id}", headers=auth_headers).status_code == 204
    assert len(client.get("/breaks", headers=auth_headers).json()) == 1


def test_break_dates_are_validated(client, auth_headers):
    backwards = {**WINTER, "start_date": "2027-01-04", "end_date": "2026-12-19"}
    assert client.post("/breaks", json=backwards, headers=auth_headers).status_code == 422
    too_long = {**WINTER, "end_date": "2027-08-01"}
    assert client.post("/breaks", json=too_long, headers=auth_headers).status_code == 422
    one_day = {**WINTER, "end_date": WINTER["start_date"]}
    assert client.post("/breaks", json=one_day, headers=auth_headers).status_code == 201


def test_breaks_are_private(client, auth_headers):
    break_id = client.post("/breaks", json=WINTER, headers=auth_headers).json()["id"]
    other = register(client, "other@example.com")
    assert client.get("/breaks", headers=other).json() == []
    assert client.delete(f"/breaks/{break_id}", headers=other).status_code == 404
    assert client.put(f"/breaks/{break_id}", json=WINTER, headers=other).status_code == 404
    assert client.get("/breaks").status_code == 401
