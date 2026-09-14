# merbag IPAM application

merbag IPAM application is a self-hosted IPv4 address-management application for tracking prefixes, child subnets, individual addresses, customers, routers, and devices. The default seed uses the documentation-only TEST-NET-3 block `203.0.113.0/24`; replace it with a network you control for real deployments.

The first release is intentionally local-first: authentication and authorization live in the application, PostgreSQL is not published on the host, and MikroTik integration is represented by non-destructive interfaces rather than live router changes.

## Architecture

| Component | Responsibility | Host exposure |
| --- | --- | --- |
| `nginx` | Single entry point, `/api/` reverse proxy, security headers, login rate limit | `${APP_PORT:-80}` |
| `frontend` | React/TypeScript single-page application served by an internal nginx | None |
| `backend` | FastAPI REST API, JWT authentication, RBAC, IPAM and audit services | None |
| `postgres` | Durable relational data | None |

Requests flow from the browser to the outer nginx service. `/api/*` is forwarded unchanged to FastAPI; every other path is forwarded to the frontend, whose fallback supports client-side routes. The backend and database share a separate Docker network, and the frontend has no network path to PostgreSQL. Database files are stored in the named `postgres_data` volume.

The backend uses SQLAlchemy and Alembic. On each backend container start it waits for PostgreSQL health, upgrades the schema, runs an idempotent seed, and then starts Uvicorn. Compose intentionally runs one backend process; if the deployment is later scaled horizontally, run migrations as a separate one-shot release step.

## Features in this release

- Dashboard totals, utilization, inventory counts, and recent allocations.
- Multiple IPv4 prefixes with derived network, broadcast, usable range, and address counts.
- Child subnet creation/splitting and parent-child relationships.
- Address states: free, assigned, reserved, gateway, network, broadcast, and blackholed.
- Allocation, release, reservation, editing, next-free lookup, global search, and retained allocation history.
- Device, customer, and router inventories with address associations.
- Audit records for logins and important IPAM mutations.
- Local users with Argon2 password hashes and JWT bearer sessions.
- Admin, Operator, and Read Only roles.
- A responsive React dashboard and scan-friendly address/subnet views.

## Production installation (Ubuntu 24.04)

The target host needs Docker Engine and the Docker Compose plugin. For a clean server, follow Docker's current [Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/); install `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and `docker-compose-plugin` from Docker's signed apt repository. Verify the installation:

```bash
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

Using Docker through the `docker` group is effectively root-level access. Either keep the commands under `sudo`, or add only a trusted deployment account to that group and start a new login session.

Copy or clone this repository to the server, then work from its root directory. Create the runtime configuration with restrictive permissions:

```bash
umask 077
cp .env.example .env

merbag_db_secret=$(openssl rand -hex 32)
merbag_jwt_secret=$(openssl rand -hex 64)
merbag_admin_secret=$(openssl rand -hex 24)

sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${merbag_db_secret}/" .env
sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${merbag_jwt_secret}/" .env
sed -i "s/^INITIAL_ADMIN_PASSWORD=.*/INITIAL_ADMIN_PASSWORD=${merbag_admin_secret}/" .env

# Pause here and transfer merbag_admin_secret directly into an approved
# password manager. Do not paste it into command history, tickets, or logs.
unset merbag_db_secret merbag_jwt_secret merbag_admin_secret
chmod 600 .env
```

Do not run the `unset` line until the generated initial administrator password has been recorded in the approved password manager. Edit `.env` and replace `ipam.example.com` in `TRUSTED_HOSTS` with the server's actual IP address and/or DNS name. If nginx should listen on a different host port, change `APP_PORT`.

Validate without printing resolved secrets, then start the application:

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

The first build downloads base images and may take several minutes. The backend will apply migrations and seed the initial prefix and administrator before nginx becomes healthy. Follow startup when needed:

```bash
docker compose logs -f --tail=100 postgres backend frontend nginx
```

Do not commit `.env`, paste it into tickets, or share the output of `docker compose config` without redaction. The Compose file does not publish PostgreSQL or FastAPI ports. At the host firewall, allow the application port only from the intended management networks and restrict SSH to administrator networks. The included nginx listener is HTTP; terminate TLS in a trusted upstream proxy or add a managed certificate before using the application across an untrusted network.

## Default URLs

Replace `HOST` and the port if `APP_PORT` is not `80`.

| Purpose | URL |
| --- | --- |
| Web application | `http://HOST/` |
| API health | `http://HOST/api/health` |
| Interactive API docs | `http://HOST/api/docs` |
| ReDoc | `http://HOST/api/redoc` |
| OpenAPI document | `http://HOST/api/openapi.json` |

There is no hardcoded password. The first administrator is created from `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD`. The seed does not overwrite an existing account on later restarts, so changing the environment value alone does not rotate an existing password.

## Roles and access control

All operational data endpoints require authentication. Health, login/token, and API documentation metadata remain public so monitoring and interactive sign-in can function.

| Role | Effective access |
| --- | --- |
| Admin | Full operational access, user administration, and destructive prefix/subnet operations |
| Operator | Create and update IPAM/inventory records and perform address allocations; cannot administer users or perform admin-only deletes |
| Read Only | Authenticated dashboard, list, detail, history, and search access; no mutations |

Authorization is enforced by the backend, not only by hidden UI controls. Keep at least two individually named administrator accounts for recovery and attribution; do not share the seeded account between operators.

## Data semantics

- A **prefix** is an owned or routed IPv4 range. Network and broadcast values, usable bounds, and total address count are calculated from CIDR input rather than accepted from the browser.
- A **subnet** belongs to a prefix and may reference a parent subnet. Parent-child bounds are validated so unrelated or out-of-prefix blocks cannot be attached.
- An **IP address** is materialized under its prefix and may be associated with a subnet, device, customer, and router. Network and broadcast rows use their corresponding protected statuses.
- **Free** means available for allocation. **Assigned**, **Reserved**, **Gateway**, and **Blackholed** all count as unavailable/used for operational capacity. Network and broadcast addresses are also unavailable.
- An **allocation** is an append-only event with the prior/new state and a snapshot of assignment data. Releasing an address clears its current assignment fields but retains allocation history.
- The **audit log** records the actor and important actions independently of the current object state. Treat it as an operational history, not as a substitute for off-host log retention.
- Dates are stored as timezone-aware timestamps; API clients should render them in the operator's local timezone.

## Development

### Backend

Use Python 3.12 and a PostgreSQL database. From `backend/`:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://merbag:replace-with-local-password@127.0.0.1:5432/merbag_ipam'
export JWT_SECRET_KEY='development-only-secret-at-least-16-characters'
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use a dedicated non-production database and credentials for local development. The frontend dev server expects the API at `/api`; its Vite proxy forwards that path to the backend.

### Frontend

Use Node.js 20 or newer with Corepack enabled. From `frontend/`:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

Open `http://localhost:5173`. For a production-equivalent local run, use `docker compose up -d --build` from the repository root.

### Tests and build checks

```bash
docker compose run --rm backend python -m pytest -q -p no:cacheprovider
docker compose build frontend
```

The backend tests cover network calculations and allocation rules. The frontend image build runs the TypeScript compiler before producing its static bundle.

## Database migrations

Migrations run automatically before the API starts. Useful operator/developer commands are:

```bash
# Show current database revision
docker compose exec backend alembic current

# Apply pending migrations explicitly
docker compose run --rm backend alembic upgrade head

# Create a migration during development after changing models
cd backend
alembic revision --autogenerate -m "describe change"
```

Review generated migrations before committing them. Take a verified database backup before an upgrade. Avoid schema downgrades in production unless the migration was explicitly designed and tested for rollback.

## Backup and restore

Create a PostgreSQL custom-format backup from the repository root:

```bash
sh scripts/backup-db.sh
```

The script writes a permission-restricted, timestamped file under `backups/` by default. Pass another destination directory as its only argument. Copy backups to encrypted off-host storage and periodically test restoration; the Docker volume is persistence, not a backup.

Restore replaces the current database. Stop writes, verify the selected file, and run the guarded helper:

```bash
RESTORE_CONFIRM=REPLACE_MERBAG_DATABASE \
  sh scripts/restore-db.sh backups/merbag-YYYYMMDDTHHMMSSZ.dump
```

The restore helper stops nginx and the backend, rebuilds the public schema from the dump, applies any newer migrations, and restarts application traffic. If a restore fails, leave the application stopped, inspect the PostgreSQL output, and restore a known-good backup before starting the backend.

## Routine operations

```bash
# Service status and health
docker compose ps

# Recent backend logs
docker compose logs --tail=200 backend

# Restart one service
docker compose restart backend

# Back up, rebuild with refreshed base images, and deploy
sh scripts/backup-db.sh
docker compose build --pull
docker compose pull postgres nginx
docker compose up -d
```

`docker compose down` removes containers and networks but preserves the named database volume. **Do not run `docker compose down -v`** unless permanent deletion of the database is explicitly intended and a restore has been tested.

## MikroTik integration status

The application does not make RouterOS changes in this release. The intended integration boundary covers discovery, import, comparison/reconciliation, duplicate or unknown address detection, and blackhole route planning. Before enabling live integration, implement and test:

1. RouterOS API/API-SSL transport with timeouts, certificate validation, scoped credentials, and secret storage outside the database.
2. Background synchronization with per-router locking, pagination, retry/backoff, and observable job status.
3. Normalization and reconciliation rules that distinguish authoritative IPAM state from discovered router state.
4. Dry-run import and conflict review with complete audit records.
5. Explicit approval, least-privilege RouterOS accounts, idempotency, and rollback for any future blackhole-route mutation.

Destructive router actions should remain disabled until these controls and integration tests exist.

## Troubleshooting

**Compose reports a required variable is missing.** Copy `.env.example` to `.env` and fill `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `INITIAL_ADMIN_PASSWORD`, and `TRUSTED_HOSTS`. Generate URL-safe database passwords; hexadecimal avoids connection-string escaping problems.

**The browser shows 400 or “Invalid host header.”** Add the exact hostname or IP used in the browser to the comma-separated `TRUSTED_HOSTS` value, then recreate the backend with `docker compose up -d --force-recreate backend`.

**nginx returns 502/503 during startup.** Check `docker compose ps` and `docker compose logs --tail=200 backend postgres`. Common causes are a failed migration, invalid database credentials, or a backend health check that has not passed yet.

**Login returns 429.** The outer nginx limits repeated login attempts per client address. Wait before retrying and investigate automated or failed attempts in the logs.

**Port 80 is already in use.** Set another `APP_PORT` in `.env`, for example `APP_PORT=8080`, then run `docker compose up -d` and browse to that port.

**A changed `.env` value is not applied.** `restart` does not recreate containers. Run `docker compose up -d --force-recreate backend nginx` (or the affected service).

**Database storage is growing.** Inspect the `postgres_data` volume and audit/allocation retention requirements. Do not manually delete volume files; archive according to policy and use supported SQL maintenance operations.
