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

Configure Google and GitHub credentials only in `swe-autopilot-api/.env`. Never commit that file.

### Frontend

```powershell
cd swe-autopilot-web
npm install
Copy-Item .env.example .env.local
npm run dev
```

The frontend expects the API at `http://localhost:8000` and runs at `http://localhost:3000` by default.

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
