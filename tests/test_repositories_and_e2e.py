import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from yoyo import read_migrations

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.migrations import MIGRATIONS_PATH
from app.core.seed import bootstrap_base_admin, ensure_base_admin
from app.main import app
from app.modules.auth.enums import UserRole
from app.modules.auth.repository import UserRepository
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.repository import EmailNotificationRepository
from app.modules.role_transitions.enums import TransitionStatus, TransitionTargetRole
from app.modules.role_transitions.repository import RoleTransitionRepository


def _create_sqlite_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_migrations_files_integrity_and_rollback_pairs() -> None:
    migrations = read_migrations(str(MIGRATIONS_PATH))
    migration_ids = [m.id for m in migrations]
    assert migration_ids == [
        "001_create_users",
        "002_add_user_roles",
        "003_create_email_notifications",
        "004_create_role_transition_requests",
    ]
    for migration_id in migration_ids:
        forward = Path(MIGRATIONS_PATH) / f"{migration_id}.sql"
        rollback = Path(MIGRATIONS_PATH) / f"{migration_id}.rollback.sql"
        assert forward.is_file() and forward.read_text(encoding="utf-8").strip()
        assert rollback.is_file() and rollback.read_text(encoding="utf-8").strip()


def test_sqlalchemy_repositories_persistence_filters_and_foreign_keys() -> None:
    session_factory = _create_sqlite_session_factory()

    with patch("app.core.seed.SessionLocal", session_factory):
        bootstrap_base_admin()
        bootstrap_base_admin()

    with session_factory() as db:
        user_repo = UserRepository(db)
        email_repo = EmailNotificationRepository(db)
        tr_repo = RoleTransitionRepository(db)

        admins = user_repo.list_all(role=UserRole.ADMIN)
        assert len(admins) == 1
        admin = admins[0]
        assert len(admin.id) == 26
        assert admin.email == settings.seed_admin_email

        patient = user_repo.create(
            email="patient@clinic.com",
            full_name="Paciente Real",
            hashed_password="hash",
            role=UserRole.PATIENT,
        )
        assert len(patient.id) == 26
        assert user_repo.get_by_id(patient.id) is not None
        assert user_repo.get_by_email("patient@clinic.com") is not None
        assert len(user_repo.list_all(role=UserRole.PATIENT)) == 1

        email_1 = email_repo.create(
            recipient_email=patient.email,
            subject="Assunto 1",
            body="Corpo 1",
            event_type=EmailEventType.USER_REGISTERED,
        )
        email_2 = email_repo.create(
            recipient_email=admin.email,
            subject="Assunto Admin",
            body="Corpo Admin",
            event_type=EmailEventType.ROLE_TRANSITION_ADMIN_ALERT,
        )
        assert len(email_1.id) == 26
        assert len(email_repo.list_all()) == 2
        assert [e.id for e in email_repo.list_all(recipient_email=admin.email)] == [
            email_2.id
        ]

        tr_req = tr_repo.create(
            user_id=patient.id,
            requested_role=TransitionTargetRole.DOCTOR,
        )
        tr_req_id = tr_req.id
        assert len(tr_req_id) == 26
        assert tr_repo.get_pending_by_user_id(patient.id) is not None
        assert len(tr_repo.list_all(status=TransitionStatus.PENDING)) == 1

        tr_req.status = TransitionStatus.APPROVED.value
        tr_req.reviewed_by_id = admin.id
        tr_repo.save(tr_req)
        assert tr_repo.get_pending_by_user_id(patient.id) is None
        assert len(tr_repo.list_all(status=TransitionStatus.APPROVED)) == 1

        # Deleting reviewer sets reviewed_by_id to NULL (ON DELETE SET NULL).
        db.delete(admin)
        db.commit()
        db.expire_all()
        reloaded = tr_repo.get_by_id(tr_req_id)
        assert reloaded is not None
        assert reloaded.reviewed_by_id is None

        # Deleting requester cascades to role_transition_requests (ON DELETE CASCADE).
        db.delete(patient)
        db.commit()
        db.expire_all()
        assert tr_repo.get_by_id(tr_req_id) is None


def test_end_to_end_poc_journey_with_real_db_and_jwt() -> None:
    session_factory = _create_sqlite_session_factory()

    def override_get_db() -> Generator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with session_factory() as db:
            seeded_admin = ensure_base_admin(db)
            assert seeded_admin.role == "admin"

        client = TestClient(app)

        # 1. Self-registration as doctor/attendant/admin is blocked.
        for blocked_role in ("doctor", "attendant", "admin"):
            blocked = client.post(
                "/auth/register",
                json={
                    "email": f"{blocked_role}@clinic.com",
                    "full_name": "Blocked User",
                    "password": "Password123!",
                    "role": blocked_role,
                },
            )
            assert blocked.status_code == 422

        # 2. Maria registers as patient and logs in.
        reg_maria = client.post(
            "/auth/register",
            json={
                "email": "maria@clinic.com",
                "full_name": "Dra. Maria",
                "password": "Password123!",
            },
        )
        assert reg_maria.status_code == 201
        assert reg_maria.json()["role"] == "patient"

        # Duplicate registration fails with 409.
        dup_maria = client.post(
            "/auth/register",
            json={
                "email": "maria@clinic.com",
                "full_name": "Dra. Maria",
                "password": "Password123!",
            },
        )
        assert dup_maria.status_code == 409

        maria_token = client.post(
            "/auth/login",
            json={"email": "maria@clinic.com", "password": "Password123!"},
        ).json()["access_token"]

        # Maria sees her welcome email.
        maria_emails = client.get(
            "/notifications/emails",
            headers=_bearer(maria_token),
        ).json()
        assert [e["event_type"] for e in maria_emails] == ["user_registered"]

        # 3. Maria requests transition to doctor; duplicate pending fails with 409.
        tr_create = client.post(
            "/role-transitions",
            headers=_bearer(maria_token),
            json={"requested_role": "doctor"},
        )
        assert tr_create.status_code == 201
        tr_id = tr_create.json()["id"]

        tr_dup = client.post(
            "/role-transitions",
            headers=_bearer(maria_token),
            json={"requested_role": "attendant"},
        )
        assert tr_dup.status_code == 409

        # Maria cannot list users, list all transitions, or approve her own request.
        assert (
            client.get("/auth/users", headers=_bearer(maria_token)).status_code == 403
        )
        assert (
            client.get("/role-transitions", headers=_bearer(maria_token)).status_code
            == 403
        )
        assert (
            client.post(
                f"/role-transitions/{tr_id}/approve",
                headers=_bearer(maria_token),
            ).status_code
            == 403
        )

        # 4. Base admin logs in, inspects users, pending transitions, and emails.
        admin_token = client.post(
            "/auth/login",
            json={
                "email": settings.seed_admin_email,
                "password": settings.seed_admin_password,
            },
        ).json()["access_token"]

        patients = client.get(
            "/auth/users",
            params={"role": "patient"},
            headers=_bearer(admin_token),
        ).json()
        assert [p["email"] for p in patients] == ["maria@clinic.com"]

        pending = client.get(
            "/role-transitions",
            params={"status": "pending"},
            headers=_bearer(admin_token),
        ).json()
        assert [r["id"] for r in pending] == [tr_id]

        # Maria does NOT see the admin alert email, while Admin sees all 3 emails.
        maria_visible = client.get(
            "/notifications/emails",
            headers=_bearer(maria_token),
        ).json()
        admin_visible = client.get(
            "/notifications/emails",
            headers=_bearer(admin_token),
        ).json()
        assert len(maria_visible) == 2
        assert len(admin_visible) == 3

        # 5. Admin approves Maria -> Maria becomes doctor + receives approval email.
        approve_resp = client.post(
            f"/role-transitions/{tr_id}/approve",
            headers=_bearer(admin_token),
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"

        # Reviewing again fails with 409.
        assert (
            client.post(
                f"/role-transitions/{tr_id}/reject",
                headers=_bearer(admin_token),
            ).status_code
            == 409
        )

        maria_me = client.get("/auth/me", headers=_bearer(maria_token)).json()
        assert maria_me["role"] == "doctor"

        # Now that Maria is already a doctor, requesting doctor again returns 400.
        same_role_resp = client.post(
            "/role-transitions",
            headers=_bearer(maria_token),
            json={"requested_role": "doctor"},
        )
        assert same_role_resp.status_code == 400

        # 6. Carlos registers, requests attendant, gets rejected, then admin promotes.
        reg_carlos = client.post(
            "/auth/register",
            json={
                "email": "carlos@clinic.com",
                "full_name": "Carlos",
                "password": "Password123!",
            },
        )
        carlos_id = reg_carlos.json()["id"]
        carlos_token = client.post(
            "/auth/login",
            json={"email": "carlos@clinic.com", "password": "Password123!"},
        ).json()["access_token"]

        carlos_tr = client.post(
            "/role-transitions",
            headers=_bearer(carlos_token),
            json={"requested_role": "attendant"},
        ).json()

        reject_resp = client.post(
            f"/role-transitions/{carlos_tr['id']}/reject",
            headers=_bearer(admin_token),
        )
        assert reject_resp.status_code == 200
        assert (
            client.get("/auth/me", headers=_bearer(carlos_token)).json()["role"]
            == "patient"
        )

        direct_patch = client.patch(
            f"/auth/users/{carlos_id}/role",
            headers=_bearer(admin_token),
            json={"role": "attendant"},
        )
        assert direct_patch.status_code == 200
        assert direct_patch.json()["role"] == "attendant"

        carlos_emails = client.get(
            "/notifications/emails",
            headers=_bearer(carlos_token),
        ).json()
        assert {e["event_type"] for e in carlos_emails} == {
            "user_registered",
            "role_transition_requested",
            "role_transition_rejected",
        }
    finally:
        app.dependency_overrides.clear()
