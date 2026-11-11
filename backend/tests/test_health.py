from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_postgres_connections_prefer_ipv4(monkeypatch):
    from app import database

    calls = []

    def fake_getaddrinfo(host, port, family, type):
        calls.append((host, family))
        return [(family, type, 6, "", ("203.0.113.7", 0))]

    monkeypatch.setattr(database.socket, "getaddrinfo", fake_getaddrinfo)
    url = "postgresql+psycopg://u:p@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert database.connect_args_for(url) == {"hostaddr": "203.0.113.7"}
    assert calls == [("ep-example.us-east-2.aws.neon.tech", database.socket.AF_INET)]

    monkeypatch.setenv("DATABASE_PREFER_IPV4", "false")
    assert database.connect_args_for(url) == {}
    assert database.connect_args_for("sqlite:///x.db") == {"check_same_thread": False}


def test_unresolvable_host_falls_back_to_default(monkeypatch):
    from app import database

    def fail(*args, **kwargs):
        raise OSError("no address")

    monkeypatch.setattr(database.socket, "getaddrinfo", fail)
    assert database.connect_args_for("postgresql+psycopg://u:p@db.invalid/x") == {}
