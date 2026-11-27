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

## Docker

`docker-compose.yml` runs two services on a Docker network named `clinic`:

| Service | Container | Host port | Notes |
|---|---|---|---|
| `database` | `clinic_database` | `127.0.0.1:${DB_PORT:-5432}` | Postgres 17, data in the `postgres_data` volume |
| `api` | `clinic_api` | `127.0.0.1:${API_PORT:-8000}` | Built from the `Dockerfile`, runs as a non-root user, applies migrations on startup |

```bash
make up        # docker compose up -d --build
make logs      # API logs
make down
```

- `SECRET_KEY` is required and read from `.env` (compose fails fast without it).
- Inside the network the API reaches the database as `database:5432`; the
  `DATABASE_URL` in `.env` (for `localhost`) is only used when running outside Docker.
- Ports are bound to `127.0.0.1` only. Change them with `DB_PORT` / `API_PORT` if
  they are in use, e.g. `API_PORT=8001 make up`.
- The frontend container joins the same `clinic` network and proxies `/api` to
  `http://clinic_api:8000` (see the frontend README), so the browser needs no CORS.

## Database

To run only Postgres (and the API with `make run`):

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
- `POST /auth/refresh` returns a new access token for a still valid one. Expired tokens and inactive users are rejected, so an expired session cannot be extended.
- `GET /users?role=patient|doctor|attendant|admin` lists users for `admin`, `doctor` and `attendant`, without their documents.
- `POST /users/me/documents` accepts a nonempty array of documents for the authenticated user (one per type) and returns the created documents. The same value can be used by different users.
- `GET /document-types` lists available document types without authentication.
  Migration `009_seed_document_types` loads the basic types, `CPF` and `RG`.
- `POST /document-types` creates a document type for administrators.
- `PATCH /auth/{user_id}/role` changes a user role when the authenticated user has permission.
- `POST /role-transitions` requests a role transition to `doctor` or `attendant` and records notification emails.
- `GET /role-transitions` lists role transition requests for administrators (optional `?status=` filter).
- `POST /role-transitions/{request_id}/approve` approves a pending request, updates the user role, and records an approval email.
- `POST /role-transitions/{request_id}/reject` rejects a pending request and records a rejection email.
- `GET /notifications/emails` lists recorded email notifications (all for `admin`, own emails for other roles).
- `POST /appointments`, `GET /appointments`, `POST /appointments/{id}/reschedule` and `POST /appointments/{id}/cancel` let an attendant schedule, list, reschedule and cancel appointments. Patient and doctor must be active users with those roles, and the database rejects two active appointments for the same doctor at the same time. Appointments start on a 30-minute grid (`:00` or `:30`) and must be in the future.
- `GET /appointments/me` lists the authenticated patient's own appointments, without the attendance record.
- `GET /appointments/patients` lists the patients the authenticated doctor has attended (completed appointments), each once with the last attendance date, most recent first.
- `GET /appointments/calendar?view=day|week|month&date=YYYY-MM-DD` returns the authenticated doctor calendar.
- `POST /appointments/{id}/no-show` marks a scheduled appointment whose time has passed as a no-show. Attendants and admins can mark any appointment; doctors only their own.
- `POST /appointments/{id}/attendance` lets the appointment doctor register the attendance and request exams, once the appointment time has been reached.
- `GET /appointments/{id}` returns the appointment with its attendance record to its doctor.
- `GET /exams` and `GET /exams/{id}` return the exams visible to the authenticated user, without the result text: patients see their own exams, doctors see the exams they requested, attendants and admins see all of them.
- `GET /exams/results` returns available exam results to patients and doctors. It is the only route that returns the result text.
- `admin` users can call every appointment and exam endpoint, except the ones tied to the session user (`/appointments/me`, `/appointments/patients` and `/exams/{id}/result`); on the calendar they must pass `doctor_id`.
- `POST /exams/{id}/schedule` and `POST /exams/{id}/perform` let an attendant (or admin) schedule an exam and mark it as performed.
- `POST /exams/{id}/result` lets only the doctor who requested the exam register its result, which makes it available to the patient.

## Statuses

Appointments: `scheduled` → `completed` (attendance registered), `no_show` (patient did not come) or `cancelled`.
Only `scheduled` appointments change status, and the check runs inside the `UPDATE`, so two concurrent requests cannot both succeed.
Cancelled appointments free their slot; the others keep it.

Exams: `requested` (by the doctor at the attendance) → `scheduled` → `performed` (attendant or admin) → `result_available` (requesting doctor).

User responses include `documents`; each document contains `document_type` with its `id` and `type`.
Register the account, log in, then add documents through `/users/me/documents`.

## Auth Roles

Supported roles:

- `admin`
- `patient`
- `doctor`
- `attendant`

Public registration creates `patient` users only. An initial `admin` account is seeded on startup, and users can request a transition to `doctor` or `attendant` for `admin` approval.

Direct role changes (`PATCH /auth/{user_id}/role`):

- `admin` can change any user to any role.
- `doctor` can change `attendant` users to `patient` or `attendant`.
- `attendant` can change `patient` users to `patient` or `attendant`.

## Sessions

Access tokens are JWTs signed with `SECRET_KEY` and valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (30 by default).
Set a long random `SECRET_KEY` in `.env`, for example with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
The web frontend renews the token through `POST /auth/refresh` only while the user is active, so idle sessions still expire.

## Not implemented (possible next steps)

- **Password reset by e-mail.** Suggested flow: `POST /auth/password-reset` receives an e-mail and always answers `202`, whether the account exists or not, to avoid revealing who is registered. When it exists, it stores the **hash** of a random single-use token that expires in about 30 minutes and e-mails a link with the token. `POST /auth/password-reset/confirm` checks the token, sets the new password and invalidates the token.
  Free ways to send the e-mail: [Mailpit](https://mailpit.axllent.org/) as a Docker Compose service captures the messages locally (no account, good for demos and tests); Resend and Brevo have free tiers; Gmail SMTP works with an app password. SMTP credentials go in `.env`.
- An admin screen to manage users and roles.
- Business hours: the web frontend only offers 07:00–18:00, but the API accepts any 30-minute slot.
