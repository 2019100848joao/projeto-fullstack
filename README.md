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
- `POST /auth/refresh` returns a new access token for a still valid one. Expired tokens and inactive users are rejected, so an expired session cannot be extended.
- `GET /users?role=patient|doctor|attendant|admin` lists users for `admin`, `doctor` and `attendant`, without their documents.
- `POST /users/me/documents` accepts a nonempty array of documents for the authenticated user (one per type) and returns the created documents. The same value can be used by different users.
- `GET /document-types` lists available document types without authentication.
- `POST /document-types` creates a document type for administrators.
- `PATCH /auth/{user_id}/role` changes a user role when the authenticated user has permission.
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

Public registration can create `patient`, `doctor`, or `attendant` users. It cannot create `admin` users.

> **Known security issue (to be fixed by the role management work):** because `/auth/register` is public, anyone can create an active `doctor` or `attendant` account and read patient data. Public registration should only create `patient` users, and staff accounts should be created or promoted by an admin. The web frontend already sends no role, so it only creates patients.

### Creating the first admin (development)

No endpoint creates the first admin. Register a user, then promote it in the database:

```bash
docker compose exec database psql -U clinic_user -d clinic_db \
  -c "UPDATE users SET role = 'admin' WHERE email = 'admin@example.com'"
```

Role changes:

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
- Bootstrap of the first admin and an admin screen to manage users and roles.
- Business hours: the web frontend only offers 07:00–18:00, but the API accepts any 30-minute slot.
