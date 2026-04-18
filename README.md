# service-facebook-api

Django REST backend for Facebook Page integration.

## Project Structure

- `config/`: project config (`urls.py`, `asgi.py`, `wsgi.py`, split settings)
- `config/settings/base.py`: base settings
- `config/settings/development.py`: local dev settings
- `config/settings/production.py`: production settings
- `config/settings/test.py`: test settings
- `apps/facebook_api/`: API app for Facebook Page Graph operations

## Phase 1 - Preparation Checklist

### 1) Create Facebook Page
- Create a Page in Facebook.
- Save evidence screenshot including:
  - Page name
  - Page ID

### 2) Create Facebook App (Meta Developer)
- Go to Meta for Developers and create an app.
- Add required product(s): usually `Facebook Login` and permissions for Page access.
- Save evidence screenshot including:
  - App Dashboard (App ID visible)

### 3) Get Page Access Token
- Generate a Page Access Token for the target page.
- Ensure permissions are granted (depending on endpoint use):
  - `pages_show_list`
  - `pages_read_engagement`
  - `pages_manage_posts`
  - `pages_read_user_content`
  - `pages_manage_engagement`
  - `read_insights`
- Save evidence screenshot including:
  - token value (or partially masked)
  - permissions list

Put token and app/page config into `.env` (copy from `.env.example`).

## Phase 2 - Backend APIs

Implemented endpoints:

- `GET /api/page/{pageId}`
- `GET /api/page/{pageId}/posts`
- `POST /api/page/{pageId}/posts`
- `DELETE /api/page/post/{postId}`
- `GET /api/page/post/{postId}/comments`
- `GET /api/page/post/{postId}/likes`
- `GET /api/page/{pageId}/insights`

## Run locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Create `.env` from `.env.example` and fill values.
3. Run server:
   - `python manage.py migrate`
   - `python manage.py runserver`

## Run with Docker

1. Create `.env` from `.env.example` and fill required values.
2. Build and run:
  - `docker compose up --build`
3. API will be available at `http://localhost:8000`.

The container startup will automatically run:
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`
- `gunicorn config.wsgi:application --bind 0.0.0.0:8000`

## API docs

- Schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/swagger/`
- ReDoc: `GET /api/docs/redoc/`

## GitHub Actions CI/CD

Workflow file: `.github/workflows/ci-cd.yml`

Pipeline behavior:
- CI on pull request and push to `main`/`master`:
  - install dependencies
  - `python manage.py check`
  - `python manage.py migrate --noinput`
  - `python manage.py test`
  - `python manage.py spectacular --file schema.yaml --validate`
- CD on push to `main`:
  - build Docker image
  - push to GitHub Container Registry: `ghcr.io/<owner>/<repo>`

No extra secret is required for GHCR publish in the same repository because workflow uses `GITHUB_TOKEN` with `packages: write` permission.
