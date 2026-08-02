# Deploying to Liara — single origin at debrief.liara.run

Account: **sajjadtazeroo@gmail.com** · region **iran**.

**Topology (one public subdomain, no custom domain):**
- `debrief` app → **debrief.liara.run** (Nuxt web, public)
- `debrief-api` app → API (private; no public traffic needed)
- managed **Postgres (pgvector)** + **Redis**
- all four on one private network

The web app proxies `/api/**` to `debrief-api` internally (Nitro `routeRules`), so the
browser only ever talks to `debrief.liara.run`. Auth cookies are therefore **first-party**
— no custom domain, no cross-subdomain cookie problem.

Fill in `<PLAN>` and `<...>` secrets.

## 0. Authenticate (interactive — you run this)
```
liara login                 # sign in as sajjadtazeroo@gmail.com
liara account:use <name>    # select it
```

## 1. Private network
```
liara network create --name debrief-net
```

## 2. Managed databases
```
liara db create --name debrief-db    --type postgres --version 16 --network debrief-net --plan <PLAN>
liara db create --name debrief-redis --type redis    --version 7  --network debrief-net --plan <PLAN>
```
Enable extensions on Postgres (panel query console or `liara shell`):
```
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```
Note the **internal** hostnames/creds from the panel.

## 3. Create the apps
```
liara create --app debrief-api --platform docker --network debrief-net --plan <PLAN>
liara create --app debrief     --platform docker --network debrief-net --plan <PLAN>
```

## 4. API environment
Same-origin ⇒ host-only cookies (`COOKIE_DOMAIN` empty) and refresh path `/`
(so it survives the `/api` proxy prefix).
```
liara env set --app debrief-api \
  DATABASE_URL='postgresql+psycopg://<user>:<pw>@debrief-db:5432/<db>' \
  REDIS_URL='redis://:<pw>@debrief-redis:6379/0' \
  JWT_SECRET='<openssl rand -hex 32>' \
  COOKIE_SECURE=1 COOKIE_SAMESITE=lax COOKIE_REFRESH_PATH=/ \
  CORS_ORIGINS='https://debrief.liara.run' \
  ADMIN_USERNAME='<admin>' ADMIN_PASSWORD='<strong-password>' \
  SEED_ON_START=0 \
  OPENROUTER_API_KEY='<optional — only if using /chat>'
```

## 5. Deploy the API (from repo root — Dockerfile.api + .liaraignore)
```
liara deploy --app debrief-api --platform docker --dockerfile Dockerfile.api --port 8000
```

## 6. Deploy the web (from web/ — bake proxy target + relative API base)
```
cd web
liara deploy --app debrief --platform docker --port 3000 \
  --build-arg NUXT_PUBLIC_API_BASE=/api \
  --build-arg NUXT_API_INTERNAL=http://debrief-api:8000
```
(`NUXT_API_INTERNAL` = the API app's internal address on `debrief-net`; adjust if
Liara exposes a different private hostname.)

## 7. Verify
```
curl -s https://debrief.liara.run/api/health                        # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}' https://debrief.liara.run/api/kpis   # 401
```
Open `https://debrief.liara.run` → /login → sign in (admin creds from step 4) →
dashboard; hard-refresh stays logged in; Logout works.

## Notes
- `debrief.liara.run` requires the web app be named exactly `debrief` (must be available).
- `SEED_ON_START=0` keeps demo data out of prod; load real data via the Import page.
- pgvector must exist before the API's first boot (init_schema runs `CREATE EXTENSION vector`).
- Rotate `ADMIN_PASSWORD` after first login; set a real random `JWT_SECRET`.
