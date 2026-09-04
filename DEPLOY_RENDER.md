# V2 Render deployment

Create a **new** Render Web Service for the V2 application. Do not replace the legacy root project service.

- **Branch:** `feat/fgo-agent`
- **Root Directory:** `v2`
- **Build Command:** `./build.sh`
- **Start Command:** `gunicorn config.wsgi:application`

Supply these environment variables manually in Render. Never copy local secrets or the local development Tool token:

- `DJANGO_SECRET_KEY` — fresh production secret
- `DJANGO_DEBUG=false`
- `AGENT_TOOL_API_TOKEN` — fresh Render-only server-to-server token
- `DIFY_API_BASE_URL`
- `DIFY_API_KEY`
- `DIFY_TIMEOUT_SECONDS` (optional)
- `PYTHON_VERSION=3.14.3` (if explicitly pinned)
- `DJANGO_ALLOWED_HOSTS` (optional; `RENDER_EXTERNAL_HOSTNAME` is admitted automatically)

`config.wsgi:application` is the WSGI entry point. The service keeps SQLite as a temporary fallback for this deployment stage; Render filesystem persistence is not treated as the final production data strategy. PostgreSQL and data migration are separate future work. The read-only `/api/tools/servant/` endpoint is stateless and does not depend on persistent servant database storage.

Do not add a persistent disk or import legacy data as part of this deployment preparation.
