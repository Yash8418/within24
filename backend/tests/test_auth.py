from app.security import create_access_token, decode_access_token, hash_password, verify_password
from tests.conftest import register


def test_password_is_hashed_and_verifiable():
    hashed = hash_password("correct-horse")
    assert hashed != "correct-horse"
    assert verify_password("correct-horse", hashed)
    assert not verify_password("wrong", hashed)


def test_token_round_trip_and_tampering():
    token = create_access_token(42)
    assert decode_access_token(token) == 42
    assert decode_access_token(token + "x") is None
    assert decode_access_token("not-a-token") is None


def test_register_then_fetch_profile(client):
    headers = register(client, email="Yash@Example.com")
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "yash@example.com"
    assert response.json()["timezone"] == "America/Toronto"


def test_duplicate_email_is_rejected_case_insensitively(client):
    register(client, email="student@example.com")
    response = client.post("/auth/register", json={"email": "STUDENT@example.com", "password": "another-pass"})
    assert response.status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert response.status_code == 422


def test_login_with_correct_and_incorrect_password(client):
    register(client, password="correct-horse")
    ok = client.post("/auth/login", json={"email": "student@example.com", "password": "correct-horse"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/auth/login", json={"email": "student@example.com", "password": "wrong-horse"})
    assert bad.status_code == 401
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "correct-horse"})
    assert unknown.status_code == 401


def test_protected_route_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
