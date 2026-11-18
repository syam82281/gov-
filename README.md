# Bharat One — Government Jobs & Services Portal

A starter full-stack directory for discovering Indian government recruitment portals and citizen services.

## Stack
- Frontend: React 19 + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Deployment: Docker Compose + Nginx

## Run with Docker
1. Install Docker Desktop (Windows/macOS) or Docker Engine + Compose (Linux).
2. Extract this project.
3. Open a terminal in the project directory.
4. Start all services:

   ```bash
   docker compose up --build -d
   ```

5. Open:
   - Website: http://localhost:8080
   - API: http://localhost:8000
   - API documentation: http://localhost:8000/docs

Stop services:
```bash
docker compose down
```

Keep database data:
```bash
docker compose down
```

Delete database volume (this permanently deletes local database data):
```bash
docker compose down -v
```

## Run locally without Docker

Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend in a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. For local backend development, set `VITE_API_URL=http://localhost:8000` if needed.

## API endpoints
- `GET /api/health` — health check
- `GET /api/categories` — available categories
- `GET /api/job-links` — list posted job links and application dates
- `POST /api/job-links` — publish a job link (admin key required)
- `GET /api/opportunities` — list and filter opportunities
- `GET /api/opportunities/{id}` — one opportunity
- `POST /api/opportunities` — create (admin key required)
- `PATCH /api/opportunities/{id}` — update (admin key required)
- `DELETE /api/opportunities/{id}` — deactivate (admin key required)

Filters:
- `search`: title, organization or description
- `category`: exact category
- `state`: state name; includes All India entries
- `featured`: true or false

## Add a listing (admin)
Change `ADMIN_API_KEY` in `docker-compose.yml` before deployment. Then use the key in the `X-Admin-Key` header.

The **Job Links** section also has a publishing form for an admin to add a job title, application URL, starting date and ending date. Enter the configured admin key in the form; it is sent only with the publish request. Links are publicly listed with their application window, and the Apply button is available only while that window is open.

## Automatic job-link monitoring

The backend checks these official recruitment pages every 15 minutes by default:
- UPSC recruitment advertisements
- SSC
- RRB Chandigarh (this does not cover every regional Railway Recruitment Board)
- IBPS
- SBI Careers

The monitor looks for explicit application-link text and labeled application dates. It automatically publishes only matches with a clear title, both dates in the right order, a current application window, and a destination on a recognized government or monitored recruitment domain. Links with missing dates, unclear titles, expired dates, or other destination domains are skipped; they are not queued for review.

This is a conservative scheduled page monitor, not an AI model or a search of the entire internet. It does not interpret PDFs or JavaScript-only pages and may miss links that a source page does not expose as ordinary HTML. Only the listed pages are checked; add and verify more official sources before claiming broader coverage. Monitoring can be disabled with `JOB_MONITOR_ENABLED: "false"` or rescheduled by changing `JOB_MONITOR_INTERVAL_SECONDS` in `docker-compose.yml`.

Job links can also be published through the API:

```bash
curl -X POST http://localhost:8000/api/job-links \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: change-this-admin-key" \
  -d '{
    "title":"Example Recruitment",
    "apply_url":"https://example.gov.in/apply",
    "start_date":"2026-11-12",
    "end_date":"2026-12-12"
  }'
```

Example:
```bash
curl -X POST http://localhost:8000/api/opportunities \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: change-this-admin-key" \
  -d '{
    "title":"Example Recruitment",
    "organization":"Example Board",
    "category":"Central Government",
    "state":"All India",
    "qualification":"As stated in official notification",
    "age_limit":"See official notification",
    "application_fee":"See official notification",
    "last_date":"Check official notification",
    "apply_url":"https://example.gov.in/",
    "notification_url":"https://example.gov.in/",
    "description":"Replace with verified official details",
    "featured":true,
    "verified":false,
    "active":true
  }'
```

## Important before production
- This is an information directory, not a government-owned portal. Display a clear disclaimer and do not use government emblems in a way that implies official status.
- Seed entries are portal links, not confirmation that recruitment is currently open. Check each official notification for current dates, eligibility, fees and vacancies.
- Verify every URL and notification before publishing; maintain a review date and source reference.
- Do not collect Aadhaar, passwords, OTPs, payment details or application documents. Send users to the official portal for applications.
- Replace development database credentials and admin key; use HTTPS, secrets management, backups, rate limiting, logging and proper admin authentication before public launch.
- The frontend API URL is currently configured for local Docker use (`http://localhost:8000`). Change it to your deployed API URL for production.
