# SWE Autopilot Web

Landing and authentication-entry experience for the SWE Autopilot FYP proposal.

## Stack

- Next.js 15 App Router
- React + TypeScript
- Tailwind CSS with custom shadcn-style UI primitives
- CSS 3D transforms and keyframe motion for the orbital agent-runtime visual

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Checks

```bash
npm run lint
npm run typecheck
npm run build
```

## Connect authentication

The sign-in and create-account forms call the FastAPI service in
`../swe-autopilot-api`. Copy `.env.example` to `.env.local` if the API is not
running at its default origin:

```bash
Copy-Item .env.example .env.local
```

Google and GitHub buttons redirect to the API OAuth routes. Provider secrets
must stay in `swe-autopilot-api/.env`; never put them in a `NEXT_PUBLIC_`
variable.
