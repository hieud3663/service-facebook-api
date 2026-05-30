# service-facebook-api

Microservices backend for Facebook Page integration. The system receives Facebook
webhooks, normalizes events, processes moderation decisions, executes Facebook
Graph API actions, retries transient failures, and exposes monitoring/alerting
for the Kafka pipeline.

## Architecture

```text
Client / Meta Webhook
        |
        v
Nginx gateway :3000
        |
        +-- /api/*      -> api-service :3002
        +-- /webhook*   -> webhook-service :3001
        +-- /core/*     -> core-service :3003
        +-- /retry/*    -> retry-service :3004

webhook-service -> Kafka topic raw_events
core-worker     -> consumes raw_events -> MongoDB -> Kafka topic reply_commands
api-worker      -> consumes reply_commands -> Facebook Graph API
api-worker      -> publishes failures to send_failed
retry-worker    -> consumes send_failed -> send_retry or dead_letter
core-retry-worker -> consumes send_retry -> reruns core action flow

Kafka exporter -> Prometheus -> Alertmanager -> Email
```

## Services

| Service | Host port | Purpose |
| --- | ---: | --- |
| `nginx` | `3000` | Single gateway for API, webhook, core, retry routes |
| `api-service` | `3002` | Facebook Graph API REST wrapper |
| `api-worker` | - | Executes async Facebook action commands from `reply_commands` |
| `webhook-service` | `3001` | Facebook webhook verification and Kafka ingestion |
| `core-service` | `3003` | Core event state, health, metrics, manual review APIs |
| `core-worker` | - | Consumes `raw_events` and decides moderation actions |
| `core-retry-worker` | - | Consumes `send_retry` and reruns core processing |
| `retry-service` | `3004` | Retry health, metrics, and retry attempt APIs |
| `retry-worker` | - | Consumes `send_failed`, publishes `send_retry` or `dead_letter` |
| `mongodb` | `27018` | MongoDB data store, mapped to container port `27017` |
| `kafka` | `9092` | Apache Kafka broker in KRaft mode |
| `kafka-ui` | `8080` | Kafka topic/browser UI |
| `kafka-exporter` | `9308` | Kafka metrics exporter |
| `prometheus` | `9090` | Metrics and alert rules |
| `alertmanager` | `9093` | Email alert routing |

## Repository Layout

```text
.
|-- services/
|   |-- docker-compose.yml
|   |-- nginx/
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
`-- .github/workflows/python-app.yml
```

## Prerequisites

- Docker and Docker Compose plugin
- Meta/Facebook app and Page access token
- Ngrok or another public tunnel for local webhook testing
- Optional: Gmail App Password for Alertmanager email alerts

## Environment Files

Docker Compose expects these files:

```text
.env
services/api-service/.env
services/webhook-service/.env
services/core-service/.env
services/retry-service/.env
```

Use the existing examples as a starting point:

```bash
cp .env.example .env
cp services/api-service/.env.example services/api-service/.env
cp services/webhook-service/.env.example services/webhook-service/.env
cp services/core-service/.env.example services/core-service/.env
cp services/retry-service/.env.example services/retry-service/.env
```

Important variables:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `FACEBOOK_GRAPH_API_VERSION` | api, webhook | Graph API version, for example `v22.0` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | api, webhook | Page access token |
| `FACEBOOK_WEBHOOK_VERIFY_TOKEN` | webhook | Verify token configured in Meta dashboard |
| `FACEBOOK_WEBHOOK_SECRET` | webhook | App secret for `X-Hub-Signature-256` validation |
| `DIFY_API_URL`, `DIFY_API_KEY` | core | Optional AI classification integration |
| `CORE_INTERNAL_API_KEY` | core | Protects core internal endpoints when configured |
| `RETRY_INTERNAL_API_KEY` | retry | Protects retry internal endpoints when configured |
| `KAFKA_BOOTSTRAP_SERVERS` | all workers | Use `kafka:9092` in Docker |
| `LOG_LEVEL` | all Django services | Console log level, default `INFO` |
| `LOG_FORMAT` | all Django services | Optional Python logging format |
| `ALERTMANAGER_*` | alertmanager | SMTP sender and recipient settings |

## Run with Docker

```bash
cd services
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

Main URLs:

| URL | Description |
| --- | --- |
| `http://localhost:3000/health` | Gateway health |
| `http://localhost:3000/api/docs/swagger/` | API service Swagger UI |
| `http://localhost:3000/api/docs/redoc/` | API service ReDoc |
| `http://localhost:3000/webhook` | Facebook webhook endpoint |
| `http://localhost:3000/core/health` | Core health |
| `http://localhost:3000/retry/health` | Retry health |
| `http://localhost:8080` | Kafka UI |
| `http://localhost:9090` | Prometheus |
| `http://localhost:9093` | Alertmanager |

Stop the stack:

```bash
cd services
docker compose down
```

## Docker Logs

All Django services and workers log to stdout/stderr for Docker. Gunicorn access
logs are also enabled.

Useful commands:

```bash
cd services
docker compose logs -f webhook-service
docker compose logs -f api-service api-worker
docker compose logs -f core-service core-worker core-retry-worker
docker compose logs -f retry-service retry-worker
docker compose logs -f prometheus alertmanager
```

Increase verbosity by setting `LOG_LEVEL=DEBUG` in the relevant service `.env`
file, then rebuild/recreate the container:

```bash
cd services
docker compose up -d --build api-service api-worker
```

## Facebook Setup

1. Create a Facebook Page and save the Page ID.
2. Create a Meta Developer app.
3. Generate a Page Access Token with the permissions required by the endpoints
   you use, commonly:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `pages_read_user_content`
   - `pages_manage_engagement`
   - `read_insights`
4. Fill the `.env` files with token/app/webhook values.
5. Expose the local gateway:

```bash
ngrok http 3000
```

6. In Meta Webhooks, choose object `Page`:
   - Callback URL: `https://<ngrok-domain>/webhook`
   - Verify token: value of `FACEBOOK_WEBHOOK_VERIFY_TOKEN`
7. Subscribe the Page to webhook fields such as `feed` and `messages`.

The webhook service also provides:

```http
POST /webhook/subscriptions/comments
```

to subscribe the page to `feed` programmatically.

## API Endpoints

All paths below are through the gateway at `http://localhost:3000`.

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
| `GET` | `/webhook` | Facebook webhook verification |
| `POST` | `/webhook` | Verify signature, normalize payload, publish `raw_events` |
| `POST` | `/webhook/subscriptions/comments` | Subscribe Page comment/feed events |

### Core Service

Internal endpoints use `X-Internal-Api-Key` when `CORE_INTERNAL_API_KEY` is set.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/core/health` | Core health check |
| `GET` | `/core/metrics` | Processed event metrics |
| `GET` | `/core/events` | List processed events |
| `GET` | `/core/events/{event_id}` | Event detail with actions/reviews |
| `POST` | `/core/events/{event_id}/retry` | Manual retry for a failed event |
| `GET` | `/core/reviews` | Manual review queue |

### Retry Service

Internal endpoints use `X-Retry-Internal-Api-Key` when
`RETRY_INTERNAL_API_KEY` is set.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/retry/health` | Retry health check |
| `GET` | `/retry/metrics` | Retry attempt metrics |
| `GET` | `/retry/attempts` | List retry attempts |
| `GET` | `/retry/attempts/{command_id}` | Retry attempt detail |

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
| --- | --- | --- | --- |
| `raw_events` | webhook-service | core-worker | Normalized Facebook events |
| `reply_commands` | core-worker | api-worker | Facebook actions to execute |
| `send_failed` | api-worker, core-worker | retry-worker | Retryable/failed action messages |
| `send_retry` | retry-worker | core-retry-worker | Scheduled retry commands |
| `dead_letter` | retry-worker | monitoring/manual review | Exhausted or non-retryable failures |

## Processing Statuses

Core event statuses:

- `received`
- `retrying`
- `action_queued`
- `ignored`
- `review_pending`
- `failed`
- `send_failed`
- `dlq_published`

Retry outcomes:

- `scheduled`
- `dead_lettered`
- `skipped`

See `CORE_RETRY_RUNBOOK.md` for the implemented retry topology and demo steps.

## Monitoring and Alerts

Prometheus loads:

- `prometheus/prometheus.yml`
- `prometheus/alert.rules.yml`

Alertmanager loads:

- `alertmanager/alertmanager.yml`
- root `.env` values named `ALERTMANAGER_*`

Current alerting focus:

- `DeadLetterQueueReceived`: critical alert when the `dead_letter` topic receives messages
- `KafkaConsumerLagHigh`: warning for high consumer lag
- `WebhookReceiverSilent`: warning when webhook ingestion is silent

See `alertmanager/README.md` for Gmail App Password setup and manual alert tests.

## Local Development

Run a single service without Docker:

```bash
cd services/api-service
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 3002
```

Run service checks:

```bash
cd services/api-service
python manage.py check
python manage.py test
```

Repeat from the desired service directory:

- `services/webhook-service`
- `services/api-service`
- `services/core-service`
- `services/retry-service`

## CI/CD

Workflow file:

```text
.github/workflows/python-app.yml
```

The workflow deploys on push to `main` using a self-hosted Linux runner. It:

1. Cleans runner workspace artifacts.
2. Checks out the repository.
3. Copies private environment files from `/opt/service-facebook-api/env`.
4. Validates Docker and Docker Compose.
5. Builds and deploys the Docker Compose stack.
6. Runs gateway, core, and retry health checks.
7. Prunes unused Docker images.

Expected environment files on the VPS:

```text
/opt/service-facebook-api/env/root.env
/opt/service-facebook-api/env/api-service.env
/opt/service-facebook-api/env/webhook-service.env
/opt/service-facebook-api/env/core-service.env
/opt/service-facebook-api/env/retry-service.env
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No application logs in Docker | Ensure containers were rebuilt after code changes and check `LOG_LEVEL` |
| Facebook webhook verification fails | Verify callback URL, token, and gateway route `/webhook` |
| Webhook POST returns 401 | Check `FACEBOOK_WEBHOOK_SECRET` and Meta app secret |
| Kafka workers do not process messages | Check Kafka health, topic names, and worker logs |
| API actions fail | Check `FACEBOOK_PAGE_ACCESS_TOKEN` permissions and api-worker logs |
| Retry never happens | Check `send_failed`, `retry-worker`, and `core-retry-worker` logs |
| Email alerts do not send | Check root `.env` `ALERTMANAGER_*` values and `alertmanager` logs |
