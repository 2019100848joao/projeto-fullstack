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

Migrations run automatically when the app starts. To run them manually:

```bash
python -c "from app.core.migrations import run_migrations; run_migrations()"
```

## Useful endpoints

- `GET /` returns basic API information.
- `GET /health` returns health status.
- `POST /auth/register` creates a user account.
- `POST /auth/login` returns a JWT access token from an `email` and `password` JSON body.
- `GET /auth/me` returns the authenticated user.
- `POST /users/me/documents` accepts a nonempty array of documents for the authenticated user (one per type) and returns an array.
- `GET /document-types` lists available document types without authentication.
- `POST /document-types` creates a document type for administrators.
- `PATCH /auth/users/{user_id}/role` changes a user role when the authenticated user has permission.

User responses include `documents`; each document contains `document_type` with its `id` and `type`.
Register the account, log in, then add documents through `/users/me/documents`.

## Auth Roles

Supported roles:

- `admin`
- `patient`
- `doctor`
- `attendant`

Public registration can create `patient`, `doctor`, or `attendant` users. It cannot create `admin` users.

Role changes:

- `admin` can change any user to any role.
- `doctor` can change `attendant` users to `patient` or `attendant`.
- `attendant` can change `patient` users to `patient` or `attendant`.
