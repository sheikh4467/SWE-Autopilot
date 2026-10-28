# SWE Autopilot

SWE Autopilot is an AI-driven software engineering platform prototype for coordinating specialized agents across the Software Development Life Cycle. The project focuses on traceable requirements, architecture decisions, code generation, testing, security checks, change-impact analysis, recovery, and evidence-based release gates.

## Repository structure

```text
SWE-Autopilot/
├── swe-autopilot-web/   # Next.js frontend and authentication UI
└── swe-autopilot-api/   # FastAPI authentication service and OAuth callbacks
```

## Local development

### Backend

```powershell
cd swe-autopilot-api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Configure Google/GitHub credentials and SMTP email-delivery settings only in
`swe-autopilot-api/.env`. Copy the safe template from `.env.example` if you
need to recreate it. Never commit that file.

Email verification is required by default. The app sends a short-lived OTP to
the verified Google/GitHub email address or to the email entered during local
signup. Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and
`SMTP_FROM_EMAIL` before testing signup or OAuth verification. For Gmail, use
an app password rather than the normal account password. The OTP is never
stored in the database or returned by the API.

Local signup also calls ZeroBounce before creating the user or sending an OTP.
Add `ZEROBOUNCE_API_KEY` to `swe-autopilot-api/.env`; keep it server-side and
never put it in the frontend. The default US endpoint is
`https://api-us.zerobounce.net/v2/validate`. The signup flow accepts only a
ZeroBounce `valid` result. It rejects invalid, spamtrap, abuse, do-not-mail,
catch-all, and unknown results because those results cannot confirm a usable
mailbox. ZeroBounce documents `mailbox_not_found` as an invalid result and
catch-all/unknown as cases where deliverability cannot be confirmed. The OTP
is still required after a valid result because validation is not proof that the
user controls the mailbox.

Signup also enforces a 24-character full-name limit, validates the email
syntax, and checks that the email domain can resolve before attempting delivery.
Domain resolution cannot prove that a specific Gmail mailbox exists: Gmail may
accept the outgoing message and later bounce it. The OTP is the authoritative
mailbox check. No authenticated session or workspace access is granted until
the user enters the OTP successfully.

For Gmail local testing, add these values to `swe-autopilot-api/.env` without
sharing the app password in chat or committing the file:

```dotenv
EMAIL_VERIFICATION_REQUIRED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM_EMAIL=your-address@gmail.com
SMTP_USE_TLS=true
```

### Frontend

```powershell
cd swe-autopilot-web
npm install
Copy-Item .env.example .env.local
npm run dev
```

The frontend expects the API at `http://localhost:8000` and runs at `http://localhost:3000` by default.

### Frontend routes

The product pages are split into separate routes:

```text
/platform   Platform overview with 3D system visual
/workflow   Agent workflow and evidence flow
/security   Identity, permissions, sandbox, and evidence controls
/about      FYP mission and project context
/workspace  Authenticated live workspace dashboard
```

After a successful email OTP, Google, or GitHub authentication, the browser
opens `/workspace` and greets the authenticated user by name. The dashboard
polls `/workspace/stats` every 10 seconds. It currently reports the default
workspace and live account/workspace activity; requirements, artifacts, agent
runs, and verification counters populate as those project actions are added to
the backend.

After signing out, Google and GitHub OAuth requests ask the provider to show an
account chooser. The application does not store provider credentials or client
side account history. The provider may still keep its own browser session, so
the provider's own sign-out may be required when its session has only one
account available.

## Checks

Frontend:

```powershell
npm run lint
npm run typecheck
npm run build
```

Backend:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pip check
```

## Security

OAuth client secrets, session secrets, local databases, virtual environments, dependency folders, build output, and app workspace metadata are excluded through `.gitignore`.
