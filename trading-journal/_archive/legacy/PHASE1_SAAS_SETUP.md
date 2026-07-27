#Phase 1 SaaS Foundations

This phase makes the current project deployable as a personal SaaS with minimal cost and no localhost lock-in.

##What was implemented

- Backend runtime now supports environment configuration (`BK_*` and `DATABASE_URL`).
- Backend database connection now supports cloud Postgres and local sqlite fallback.
- Backend CORS is now environment-driven.
- Backend socket bridge can be disabled in cloud (`BK_ENABLE_SOCKET_SERVER=false`).
- `MetaTrader5` dependency is now optional in code, so cloud Linux deploys can run without MT5 package.
- Frontend API requests now use `NEXT_PUBLIC_API_BASE_URL`.
- Initial SaaS schema tables were added:
  - `Organization`
  - `ApiKey`
  - `IngestionEvent`
  - `AccountSnapshot`
  - `Mt5Node`
- Backend dependencies were split:
  - `backend/requirements.txt` for cloud/base
  - `backend/requirements.mt5.txt` for local MT5 runtime

##Suggested zero-cost stack

- Frontend: Vercel Hobby
- Backend API: Oracle Cloud Always Free VM
- Database: Neon Free Postgres
- Access control: Cloudflare Zero Trust Free

##Environment setup

###Backend

Use `backend/.env.example` as reference.

Minimum for cloud:

- `BK_DATABASE_URL=postgresql+psycopg://...`
- `BK_CORS_ORIGINS=https://your-frontend-domain.com`
- `BK_ENABLE_SOCKET_SERVER=false`

Optional:

- `BK_API_HOST=0.0.0.0`
- `BK_API_PORT=8080`

###Frontend

Use `frontend/.env.example` as reference.

- `NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain.com/api/v1`

##Deployment order

1. Create Postgres database in Neon (or Supabase).
2. Deploy backend to VM/container with `backend/requirements.txt`.
3. Set backend env vars and start backend.
4. Verify backend health: `GET /health`.
5. Deploy frontend to Vercel.
6. Set `NEXT_PUBLIC_API_BASE_URL` in Vercel project envs.
7. Validate frontend metrics and charts against cloud API.

##Local MT5 mode

For local Windows mode with MT5 live features:

- Install `backend/requirements.mt5.txt`.
- Keep `BK_ENABLE_SOCKET_SERVER=true`.
- Keep API base as `http://localhost:8080/api/v1`.

##Definition of done for Phase 1

- Frontend reachable from public URL.
- Backend reachable from public URL and `/health` returns `status=online`.
- Frontend reads API from `NEXT_PUBLIC_API_BASE_URL` (no hardcoded localhost).
- Database runs on managed Postgres with successful table creation.
