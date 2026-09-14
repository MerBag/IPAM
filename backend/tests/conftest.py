import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "01234567890123456789012345678901"
os.environ["ENVIRONMENT"] = "test"
os.environ["TRUSTED_HOSTS"] = "localhost,127.0.0.1,testserver"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.enums import UserRole
from app.main import app
from app.models import User  # imports all mapped tables
from app.security import hash_password


test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(test_engine)
    yield
    # SQLite cannot otherwise drop the self-referential subnet table in dependency order.
    with test_engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(connection)
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


@pytest.fixture
def db() -> Session:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        username="admin",
        password_hash=hash_password("correct-horse-battery-staple"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, admin):
    response = client.post(
        "/api/auth/login",
        json={"username": admin.username, "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
