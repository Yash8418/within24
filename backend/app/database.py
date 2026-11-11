import os
import socket
from collections.abc import Iterator

from sqlalchemy.engine import make_url

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# PostgreSQL in Docker/production; SQLite file for quick local runs.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./within24.db")

# Some hosts hand out "postgres://" URLs; SQLAlchemy needs the psycopg driver name.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)



def ipv4_address(host: str | None) -> str | None:
    """An IPv4 address for `host`, or None if it has none (or can't be resolved right now).

    Some hosts (e.g. Render) have no outbound IPv6, but managed databases such as Neon publish
    IPv6 addresses first. Passing libpq's `hostaddr` makes it connect over IPv4 while still
    using `host` for TLS verification and SNI.
    """
    if not host or host.startswith("/"):
        return None
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError:
        return None
    return infos[0][4][0] if infos else None


def connect_args_for(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    if os.getenv("DATABASE_PREFER_IPV4", "true").lower() in ("1", "true", "yes"):
        address = ipv4_address(make_url(url).host)
        if address:
            return {"hostaddr": address}
    return {}


connect_args = connect_args_for(DATABASE_URL)
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
