# Web Backend

FastAPI backend starter project for a medical clinic application.

## Requirements

- Python 3.12+

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

## Run locally

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

## Tests

```bash
pytest
```

## Make Commands

```bash
make help
make setup
make db-up
make run
make check
```

## Database

Start Postgres:

```bash
docker compose up -d database
```

Migrations and the base `admin` seed run automatically when the app starts. With `APP_ENV=development` the seed uses local defaults (`admin@clinic.com` / `Admin123!`); in any other environment `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` must be set, otherwise the seed is skipped. To run migrations manually:

```bash
python -c "from app.core.migrations import run_migrations; run_migrations()"
```

## Useful endpoints

- `GET /` returns basic API information.
- `GET /health` returns health status.
- `POST /auth/register` creates a `patient` user account and records a registration email.
- `POST /auth/login` returns a JWT access token from an `email` and `password` JSON body.
- `GET /auth/me` returns the authenticated user.
- `GET /auth/users` lists users for administrators (optional `?role=` filter).
- `PATCH /auth/users/{user_id}/role` changes a user role when the authenticated user has permission.
- `POST /role-transitions` requests a role transition to `doctor` or `attendant` and records notification emails.
- `GET /role-transitions` lists role transition requests for administrators (optional `?status=` filter).
- `POST /role-transitions/{request_id}/approve` approves a pending request, updates the user role, and records an approval email.
- `POST /role-transitions/{request_id}/reject` rejects a pending request and records a rejection email.
- `GET /notifications/emails` lists recorded email notifications (all for `admin`, own emails for other roles).

## Auth Roles

Supported roles:

- `admin`
- `patient`
- `doctor`
- `attendant`

Public registration creates `patient` users only. An initial `admin` account is seeded on startup, and users can request a transition to `doctor` or `attendant` for `admin` approval.

Direct role changes (`PATCH /auth/users/{user_id}/role`):

- `admin` can change any user to any role.
- `doctor` can change `attendant` users to `patient` or `attendant`.
- `attendant` can change `patient` users to `patient` or `attendant`.
