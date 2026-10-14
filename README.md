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
- `GET /auth/users?role=patient|doctor|attendant|admin` lists users for `admin`, `doctor` and `attendant`.
- `PATCH /auth/users/{user_id}/role` changes a user role when the authenticated user has permission.
- `POST /appointments`, `GET /appointments`, `PATCH /appointments/{id}` and `POST /appointments/{id}/cancel` let an attendant schedule, list, reschedule and cancel appointments.
- `GET /appointments/agenda?view=day|week|month&date=YYYY-MM-DD` returns the authenticated doctor agenda.
- `POST /appointments/{id}/attendance` lets the appointment doctor register the attendance and request exams.
- `GET /appointments/{id}` returns the appointment with its attendance record to its doctor.
- `GET /exams` and `GET /exams/{id}` return the exams visible to the authenticated user.
- `admin` users can call every appointment and exam endpoint; on the agenda they must pass `doctor_id`.
- `POST /exams/{id}/schedule`, `POST /exams/{id}/perform` and `POST /exams/{id}/result` let an attendant move an exam through its statuses.

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
