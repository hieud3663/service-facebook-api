# service-facebook-api

[English](README.md) | [Tiếng Việt](README_vi.md)

Production-style microservices backend for Facebook Page automation.

This repository receives Meta/Facebook webhooks, normalizes Page events, pushes
them through Kafka, applies moderation/business decisions, executes Facebook
Graph API actions, retries transient failures, and exposes operational
monitoring through Prometheus and Alertmanager.

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/DRF-A30000?style=for-the-badge&logo=django&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![Alertmanager](https://img.shields.io/badge/Alertmanager-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Meta](https://img.shields.io/badge/Meta%20Graph%20API-0467DF?style=for-the-badge&logo=meta&logoColor=white)

## Table of Contents

- [Tech Stack](#tech-stack)
- [What This Project Does](#what-this-project-does)
- [Architecture](#architecture)
- [Services](#services)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Main URLs](#main-urls)
- [Facebook Webhook Setup](#facebook-webhook-setup)
- [API Surface](#api-surface)
- [Kafka Topics](#kafka-topics)
- [Processing States](#processing-states)
- [Logging](#logging)
- [Monitoring and Alerts](#monitoring-and-alerts)
- [Local Development](#local-development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## What This Project Does

- Accepts Facebook Page webhook verification and event payloads.
- Validates webhook signatures before processing event data.
- Publishes normalized events to Kafka for asynchronous processing.
- Stores event state, action logs, manual reviews, and retry attempts in MongoDB.
- Uses configurable moderation rules and optional Dify AI classification.
- Executes Facebook Graph API actions such as replies, hiding comments, page
  posts, insights, and Messenger messages.
- Retries failed actions with backoff and sends exhausted messages to a dead
  letter topic.
- Provides Docker-first local and VPS deployment with Nginx as the gateway.
- Ships Prometheus alert rules and Alertmanager email routing.

## Architecture

```text
Meta Webhook / Client
        |
        v
Nginx gateway :3000
        |
        +-- /api/*      -> api-service :3002
        +-- /webhook    -> webhook-service :3001
        +-- /core/*     -> core-service :3003
        +-- /retry/*    -> retry-service :3004

webhook-service
        |
        v
Kafka: raw_events
        |
        v
core-worker -> MongoDB -> Kafka: reply_commands
        |                     |
        |                     v
        |               api-worker -> Facebook Graph API
        |                     |
        |                     v
        +-------------- Kafka: send_failed
                              |
                              v
retry-worker -> Kafka: send_retry / dead_letter
        |
        v
core-retry-worker

Kafka exporter -> Prometheus -> Alertmanager -> Email
```

## Services

| Service | Local port | Role |
| --- | ---: | --- |
| `nginx` | `3000` | Single public gateway |
| `webhook-service` | `3001` | Facebook webhook verification, signature validation, event normalization |
| `api-service` | `3002` | REST wrapper for Facebook Graph API operations |
| `core-service` | `3003` | Event state, metrics, manual review, retry APIs |
| `retry-service` | `3004` | Retry health, metrics, and retry attempt APIs |
| `api-worker` | - | Consumes `reply_commands` and executes Facebook actions |
| `core-worker` | - | Consumes `raw_events` and decides moderation actions |
| `core-retry-worker` | - | Consumes `send_retry` and reruns the core action flow |
| `retry-worker` | - | Consumes `send_failed` and publishes retry or DLQ messages |
| `mongodb` | `27018` | MongoDB mapped to container port `27017` |
| `kafka` | `9092` | Apache Kafka broker in KRaft mode |
| `kafka-ui` | internal | Kafka topic browser, proxied in production |
| `kafka-exporter` | internal | Kafka metrics exporter for Prometheus |
| `prometheus` | internal | Metrics scraping and alert rules |
| `alertmanager` | internal | Email alert delivery |

## Repository Layout

```text
.
|-- services/
|   |-- docker-compose.yml
|   |-- nginx/
|   |   |-- Dockerfile
|   |   |-- nginx.conf
|   |   `-- app_locations.conf
|   |-- api-service/
|   |-- webhook-service/
|   |-- core-service/
|   `-- retry-service/
|-- prometheus/
|   |-- prometheus.yml
|   `-- alert.rules.yml
|-- alertmanager/
|   |-- Dockerfile
|   |-- alertmanager.yml
|   |-- entrypoint.sh
|   `-- README.md
|-- docs/
|-- images/
|-- CORE_RETRY_RUNBOOK.md
`-- .github/workflows/python-app.yml
```

Each Django service is self-contained with its own `Dockerfile`,
`requirements.txt`, `.env.example`, `manage.py`, settings package, app package,
tests, and optional OpenAPI schema.

## Prerequisites

- Docker Engine and Docker Compose plugin.
- Meta Developer app.
- Facebook Page access token with the permissions required by the operations
  you enable.
- Public HTTPS tunnel or domain for webhook testing, for example Ngrok.
- Optional Gmail App Password or SMTP credentials for Alertmanager.

## Quick Start

1. Clone and enter the repository.

   ```bash
   git clone <repo-url>
   cd service-facebook-api
   ```

2. Create local environment files.

   ```bash
   cp .env.example .env
   cp services/api-service/.env.example services/api-service/.env
   cp services/webhook-service/.env.example services/webhook-service/.env
   cp services/core-service/.env.example services/core-service/.env
   cp services/retry-service/.env.example services/retry-service/.env
   ```

3. Fill in the Facebook, Kafka, MongoDB, internal API, and alerting values in
   the generated `.env` files.

4. Build and start the full stack.

   ```bash
   cd services
   docker compose up -d --build
   ```

5. Check container status and gateway health.

   ```bash
   docker compose ps
   curl http://localhost:3000/health
   ```

6. Stop the stack when done.

   ```bash
   docker compose down
   ```

## Environment Configuration

Docker Compose expects these files to exist:

```text
.env
services/api-service/.env
services/webhook-service/.env
services/core-service/.env
services/retry-service/.env
```

Key variables:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Django services | Usually `config.settings.development` locally |
| `DJANGO_SECRET_KEY` | Django services | Per-service Django secret key |
| `DEBUG` | Django services | Development toggle; keep `False` in production |
| `ALLOWED_HOSTS` | Django services | Host allow-list for Django |
| `FACEBOOK_GRAPH_API_VERSION` | api, webhook | Graph API version, for example `v25.0` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | api, webhook | Page token used for Graph API calls |
| `FACEBOOK_APP_ID` | api | Meta app id |
| `FACEBOOK_APP_SECRET` | api | Meta app secret |
| `FACEBOOK_WEBHOOK_VERIFY_TOKEN` | webhook | Token configured in Meta webhook settings |
| `FACEBOOK_WEBHOOK_SECRET` | webhook | App secret used for `X-Hub-Signature-256` validation |
| `KAFKA_BOOTSTRAP_SERVERS` | all workers | Use `kafka:9092` inside Docker |
| `MONGO_DB_NAME`, `MONGO_HOST`, `MONGO_PORT` | core, retry | MongoDB connection settings |
| `CORE_INTERNAL_API_KEY` | core | Optional key for protected core endpoints |
| `RETRY_INTERNAL_API_KEY` | retry | Optional key for protected retry endpoints |
| `DIFY_API_URL`, `DIFY_API_KEY` | core | Optional Dify AI integration |
| `LOG_LEVEL`, `LOG_FORMAT` | Django services | Console logging level and Python log format |
| `ALERTMANAGER_*` | alertmanager | SMTP sender, recipient, and auth configuration |

Never commit real `.env` files. Keep production values in the VPS environment
directory used by the GitHub Actions workflow.

## Main URLs

Local gateway URLs:

| URL | Description |
| --- | --- |
| `http://localhost:3000/health` | Nginx gateway health |
| `http://localhost:3000/api/docs/swagger/` | API service Swagger UI |
| `http://localhost:3000/api/docs/redoc/` | API service ReDoc |
| `http://localhost:3000/webhook` | Facebook webhook callback |
| `http://localhost:3000/core/health` | Core service health |
| `http://localhost:3000/core/docs/swagger/` | Core service Swagger UI |
| `http://localhost:3000/retry/health` | Retry service health |
| `http://localhost:3000/retry/docs/swagger/` | Retry service Swagger UI |

Production Nginx also defines these host-based routes:

| Host | Target |
| --- | --- |
| `u-code.dev`, `fb.u-code.dev`, `api.u-code.dev` | Application gateway |
| `kafka.u-code.dev` | Kafka UI, protected by basic auth |
| `prometheus.u-code.dev` | Prometheus, protected by basic auth |
| `alerts.u-code.dev` | Alertmanager, protected by basic auth |

## Facebook Webhook Setup

1. Create a Facebook Page and save the Page ID.
2. Create a Meta Developer app.
3. Generate a Page Access Token with the permissions required by your use case.
   Common permissions for this project include:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `pages_read_user_content`
   - `pages_manage_engagement`
   - `read_insights`
4. Fill in the API and webhook service `.env` files:
   - `FACEBOOK_GRAPH_API_VERSION`
   - `FACEBOOK_PAGE_ACCESS_TOKEN`
   - `FACEBOOK_APP_ID`
   - `FACEBOOK_APP_SECRET`
   - `FACEBOOK_WEBHOOK_VERIFY_TOKEN`
   - `FACEBOOK_WEBHOOK_SECRET`
5. Expose the local gateway if testing locally:

   ```bash
   ngrok http 3000
   ```

6. In Meta Webhooks, choose object `Page`:
   - Callback URL: `https://<ngrok-domain>/webhook`
   - Verify token: value of `FACEBOOK_WEBHOOK_VERIFY_TOKEN`
7. Subscribe the Page to webhook fields such as `feed` and `messages`.

The webhook service also exposes this helper endpoint for comment/feed
subscription:

```http
POST /webhook/subscriptions/comments
```

## API Surface

All paths below are shown through the local gateway
`http://localhost:3000`.

### API Service

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/page/{page_id}` | Page detail |
| `GET` | `/api/page/{page_id}/posts` | List page posts |
| `POST` | `/api/page/{page_id}/posts` | Create page post |
| `DELETE` | `/api/page/post/{post_id}` | Delete post |
| `GET` | `/api/page/post/{post_id}/comments` | List post comments |
| `GET` | `/api/page/post/{post_id}/likes` | List post likes |
| `GET` | `/api/page/{page_id}/insights` | Page insights |
| `POST` | `/api/page/comment/{comment_id}/hide` | Hide or unhide comment |
| `POST` | `/api/page/comment/{comment_id}/replies` | Reply to comment |
| `POST` | `/api/page/{page_id}/messages` | Send Messenger message |

### Webhook Service

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/webhook` | Meta webhook verification |
| `POST` | `/webhook` | Signature validation, normalization, Kafka publish |
| `POST` | `/webhook/subscriptions/comments` | Subscribe a Page to comment/feed events |

### Core Service

When `CORE_INTERNAL_API_KEY` is set, protected requests must include
`X-Internal-Api-Key`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/core/health` | Health check |
| `GET` | `/core/metrics` | Processed event metrics |
| `GET` | `/core/events` | List processed events |
| `GET` | `/core/events/{event_id}` | Event detail with action logs and reviews |
| `POST` | `/core/events/{event_id}/retry` | Manually retry a failed event |
| `GET` | `/core/reviews` | Manual review queue |

### Retry Service

When `RETRY_INTERNAL_API_KEY` is set, protected requests must include
`X-Retry-Internal-Api-Key`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/retry/health` | Health check |
| `GET` | `/retry/metrics` | Retry attempt metrics |
| `GET` | `/retry/attempts` | List retry attempts |
| `GET` | `/retry/attempts/{command_id}` | Retry attempt detail |

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
| --- | --- | --- | --- |
| `raw_events` | webhook-service | core-worker | Normalized Facebook events |
| `reply_commands` | core-worker | api-worker | Facebook actions to execute |
| `send_failed` | api-worker, core-worker | retry-worker | Retryable action failures |
| `send_retry` | retry-worker | core-retry-worker | Scheduled retry commands |
| `dead_letter` | retry-worker | operators/monitoring | Exhausted or non-retryable failures |

## Processing States

Core event states:

| State | Meaning |
| --- | --- |
| `received` | Event was accepted and stored |
| `retrying` | Event is being processed again |
| `action_queued` | A Facebook action command was queued |
| `ignored` | Event was intentionally skipped |
| `review_pending` | Event requires manual review |
| `failed` | Core processing failed |
| `send_failed` | Action dispatch failed and was sent to retry |
| `dlq_published` | Message was published to the dead letter flow |

Retry outcomes:

| Outcome | Meaning |
| --- | --- |
| `scheduled` | Retry was scheduled |
| `dead_lettered` | Retry attempts were exhausted |
| `skipped` | Retry message was ignored by policy or idempotency |

See `CORE_RETRY_RUNBOOK.md` for the implemented retry topology and demo steps.

## Logging

All Django services and workers log to stdout/stderr, which is the expected
Docker logging pattern. Gunicorn access and error logs are also enabled.

Useful commands:

```bash
cd services
docker compose logs -f webhook-service
docker compose logs -f api-service api-worker
docker compose logs -f core-service core-worker core-retry-worker
docker compose logs -f retry-service retry-worker
docker compose logs -f prometheus alertmanager
```

Increase verbosity by setting `LOG_LEVEL=DEBUG` in the relevant service `.env`,
then recreate the target container:

```bash
cd services
docker compose up -d --build api-service api-worker
```

## Monitoring and Alerts

Prometheus configuration:

- `prometheus/prometheus.yml`
- `prometheus/alert.rules.yml`

Alertmanager configuration:

- `alertmanager/alertmanager.yml`
- root `.env` variables prefixed with `ALERTMANAGER_`

Current alert focus:

| Alert | Severity | Meaning |
| --- | --- | --- |
| `DeadLetterQueueReceived` | critical | Messages reached the `dead_letter` topic |
| `KafkaConsumerLagHigh` | warning | Kafka consumer lag is high |
| `WebhookReceiverSilent` | warning | Webhook ingestion appears silent |

See `alertmanager/README.md` for SMTP setup and manual alert tests.

## Local Development

Run one Django service without Docker:

```bash
cd services/api-service
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 3002
```

Use the corresponding service directory and port for other services:

| Service | Directory | Port |
| --- | --- | ---: |
| API | `services/api-service` | `3002` |
| Webhook | `services/webhook-service` | `3001` |
| Core | `services/core-service` | `3003` |
| Retry | `services/retry-service` | `3004` |

## Testing

Run Django checks and tests from a service directory:

```bash
python manage.py check
python manage.py test
```

Run tests for all service directories manually:

```bash
cd services/api-service && python manage.py test
cd ../webhook-service && python manage.py test
cd ../core-service && python manage.py test
cd ../retry-service && python manage.py test
```

Validate Docker Compose before deploying:

```bash
cd services
docker compose config
```

## Deployment

The GitHub Actions workflow lives at:

```text
.github/workflows/python-app.yml
```

It deploys on push to `main` or manual `workflow_dispatch` using a self-hosted
Linux runner. The deployment flow:

1. Cleans runner workspace artifacts.
2. Checks out the repository.
3. Copies private environment files from the VPS environment directory.
4. Validates Docker and Docker Compose availability.
5. Builds all Django services, Alertmanager, and Nginx.
6. Starts MongoDB and Kafka.
7. Runs Django migrations.
8. Starts the full Compose stack.
9. Runs gateway, core, and retry health checks.
10. Prunes unused Docker images.

Expected production environment files:

```text
/opt/service-facebook-api/env/root.env
/opt/service-facebook-api/env/api-service.env
/opt/service-facebook-api/env/webhook-service.env
/opt/service-facebook-api/env/core-service.env
/opt/service-facebook-api/env/retry-service.env
```

The workflow also accepts override variables such as
`SERVICE_FACEBOOK_ENV_DIR`, `ROOT_ENV_FILE_PATH`,
`API_SERVICE_ENV_FILE_PATH`, `WEBHOOK_SERVICE_ENV_FILE_PATH`,
`CORE_SERVICE_ENV_FILE_PATH`, and `RETRY_SERVICE_ENV_FILE_PATH`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Gateway returns unhealthy | `docker compose ps`, then `docker compose logs -f nginx` |
| No application logs appear | Rebuild/recreate containers and check `LOG_LEVEL` |
| Facebook webhook verification fails | Callback URL, verify token, domain HTTPS, and `/webhook` route |
| Webhook POST returns `401` | `FACEBOOK_WEBHOOK_SECRET` and Meta app secret |
| Kafka workers do not process messages | Kafka health, topic names, consumer group ids, worker logs |
| API actions fail | `FACEBOOK_PAGE_ACCESS_TOKEN` permissions and `api-worker` logs |
| Retry flow does not run | `send_failed`, `retry-worker`, `send_retry`, and `core-retry-worker` logs |
| Messages reach DLQ | Inspect `dead_letter`, source error logs, and retry attempt records |
| Alert emails do not send | Root `.env` `ALERTMANAGER_*` values and `alertmanager` logs |

Useful runbooks:

- `CORE_RETRY_RUNBOOK.md`
- `alertmanager/README.md`
