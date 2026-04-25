# service-facebook-api

Microservices-based backend for Facebook Page integration.

## Architecture

```
                  ┌──────────┐
   Client ──────► │  Nginx   │ :80
                  │ Gateway  │
                  └────┬─────┘
                       │
          ┌────────────┼────────────┐
          │                         │
    /api/* │                   /webhook* │
          ▼                         ▼
  ┌──────────────┐         ┌───────────────┐
  │  api-service │ :8000   │webhook-service│ :3001
  │  (Graph API) │         │ (Kafka ingest)│
  └──────────────┘         └───────┬───────┘
                                   │
                              ┌────▼────┐
                              │  Kafka  │ :9092
                              └─────────┘
```

| Service | Port | Description |
|---------|------|-------------|
| **Nginx** | 80 | API gateway – single entry-point |
| **api-service** | 8000 | REST APIs for Facebook Page (Graph API) |
| **webhook-service** | 3001 | Realtime webhook ingestion → Kafka |
| **Kafka** | 9092 | Event streaming broker |
| **Zookeeper** | 2181 | Kafka coordination |

## Project Structure

```
services/
├── docker-compose.yml          # Orchestrates all services
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf              # API gateway routing
├── api-service/                # Microservice 1
│   ├── Dockerfile
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env / .env.example
│   ├── scripts/start.sh
│   ├── config/                 # Django settings
│   └── apps/facebook_api/     # Business logic
└── webhook-service/            # Microservice 2
    ├── Dockerfile
    ├── manage.py
    ├── requirements.txt
    ├── .env / .env.example
    ├── scripts/start.sh
    ├── config/                 # Django settings
    └── apps/webhook/           # Business logic
```

## Phase 1 – Preparation Checklist

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

Put token and app/page config into each service's `.env` (copy from `.env.example`).

### 4) Webhook Setup on Meta App Dashboard
To stream live events to your local machine, you need to expose your local Nginx gateway (port 3000) to the internet and configure Facebook Webhook.

1. **Expose local port using Ngrok**:
   ```bash
   ngrok http 3000
   ```
   *Copy the generated `https://...ngrok-free.app` URL.*

2. **Setup Webhook Product**:
   - In Meta App Dashboard, click **Add Product** and select **Webhooks**.
   - Choose **Page** from the dropdown and click **Subscribe to this object**.
   - **Callback URL**: Enter `https://<your-ngrok-url>/webhook`
   - **Verify Token**: Enter the text you wrote in your `.env` for `FACEBOOK_WEBHOOK_VERIFY_TOKEN` (e.g. `your-webhook-verify-token`).
   - Click **Verify and Save**. (Make sure your Docker services are running!)

3. **Subscribe to Webhook Fields**:
   - Under Page webhooks, find the `feed` and `messages` fields and click **Subscribe**.
   - Alternatively, use the `POST /webhook/subscriptions/comments` API provided in this service to programmatically subscribe the Page using the API.

## Phase 2 – API Service Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/page/{pageId}` | Page detail |
| `GET`  | `/api/page/{pageId}/posts` | List posts |
| `POST` | `/api/page/{pageId}/posts` | Create post |
| `DELETE`| `/api/page/post/{postId}` | Delete post |
| `GET`  | `/api/page/post/{postId}/comments` | Post comments |
| `GET`  | `/api/page/post/{postId}/likes` | Post likes |
| `GET`  | `/api/page/{pageId}/insights` | Page insights |

## Phase 4 – Webhook Service Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/webhook` | Facebook webhook verification (`hub.challenge`) |
| `POST` | `/webhook` | Verify signature, normalize payload, publish to Kafka |
| `POST` | `/webhook/subscriptions/comments` | Register Page subscription (`feed`) |

### Normalized Event Schema

| Field | Description |
|-------|-------------|
| `event_id` | UUID for each normalized event |
| `source` | Always `"facebook"` |
| `object` | Payload object type |
| `event_type` | `"comment"`, `"message"`, or `"unknown"` |
| `occurred_at` | ISO 8601 timestamp |
| `page_id` | Facebook Page ID |
| `sender_id` | Who triggered the event |
| `target_id` | Target post/comment ID |
| `channel` | `"facebook_page"` or `"facebook_messenger"` |
| `meta` | Additional event metadata |
| `raw_event` | Original Facebook payload |

Kafka topic: `raw_events` (configurable via `KAFKA_RAW_EVENTS_TOPIC`).

## Run with Docker (Microservices)

```bash
cd services
docker compose up --build
```

Services will be available at:
- **Gateway**: `http://localhost` (port 80)
- **API docs**: `http://localhost/api/docs/swagger/`
- **Webhook**: `http://localhost/webhook`
- **Kafka broker**: `localhost:9092`

## Run locally (Single service)

```bash
cd services/api-service
pip install -r requirements.txt
cp .env.example .env   # fill values
python manage.py migrate
python manage.py runserver 8000
```

```bash
cd services/webhook-service
pip install -r requirements.txt
cp .env.example .env   # fill values
python manage.py migrate
python manage.py runserver 3001
```

## API docs

Via Nginx gateway:
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
