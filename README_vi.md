# service-facebook-api

[English](README.md) | [Tiếng Việt](README_vi.md)

Backend microservices kiểu production cho tự động hóa Facebook Page.

Dự án nhận webhook từ Meta/Facebook, chuẩn hóa sự kiện Page, đẩy qua Kafka, xử
lý quyết định kiểm duyệt/nghiệp vụ, gọi Facebook Graph API, retry lỗi tạm thời,
và cung cấp monitoring qua Prometheus + Alertmanager.

## Công Nghệ Sử Dụng

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

## Mục Lục

- [Công Nghệ Sử Dụng](#công-nghệ-sử-dụng)
- [Dự Án Làm Gì](#dự-án-làm-gì)
- [Kiến Trúc](#kiến-trúc)
- [Danh Sách Service](#danh-sách-service)
- [Cấu Trúc Thư Mục](#cấu-trúc-thư-mục)
- [Yêu Cầu Cài Đặt](#yêu-cầu-cài-đặt)
- [Chạy Nhanh](#chạy-nhanh)
- [Cấu Hình Môi Trường](#cấu-hình-môi-trường)
- [URL Chính](#url-chính)
- [Cấu Hình Facebook Webhook](#cấu-hình-facebook-webhook)
- [API](#api)
- [Kafka Topics](#kafka-topics)
- [Trạng Thái Xử Lý](#trạng-thái-xử-lý)
- [Logging](#logging)
- [Monitoring Và Alert](#monitoring-và-alert)
- [Phát Triển Local](#phát-triển-local)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

## Dự Án Làm Gì

- Nhận webhook verification và webhook payload từ Facebook Page.
- Xác thực chữ ký webhook trước khi xử lý dữ liệu.
- Chuẩn hóa event và publish vào Kafka.
- Lưu event state, action logs, manual reviews, retry attempts trong MongoDB.
- Áp dụng rule kiểm duyệt và có thể tích hợp Dify AI để phân loại nội dung.
- Thực thi thao tác Facebook Graph API như reply, ẩn comment, tạo bài viết,
  xem insight, gửi Messenger message.
- Retry action bị lỗi bằng backoff và đưa message hết retry vào dead letter.
- Chạy local/deploy bằng Docker Compose, dùng Nginx làm gateway.
- Có Prometheus alert rules và Alertmanager gửi email.

## Kiến Trúc

```text
Meta Webhook / Client
        |
        v
Nginx gateway (:3000 local, :80/:443 production)
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

## Danh Sách Service

| Service | Port local | Vai trò |
| --- | ---: | --- |
| `nginx` | `3000`, `80`, `443` | Gateway public và reverse proxy TLS production |
| `webhook-service` | `3001` | Verify webhook, xác thực signature, chuẩn hóa event |
| `api-service` | `3002` | REST wrapper cho Facebook Graph API |
| `core-service` | `3003` | Event state, metrics, manual review, retry APIs |
| `retry-service` | `3004` | Retry health, metrics, retry attempt APIs |
| `api-worker` | - | Consume `reply_commands` và gọi Facebook action |
| `core-worker` | - | Consume `raw_events` và quyết định moderation action |
| `core-retry-worker` | - | Consume `send_retry` và chạy lại core action flow |
| `retry-worker` | - | Consume `send_failed`, publish retry hoặc DLQ |
| `mongodb` | `27018` | MongoDB, map vào container port `27017` |
| `kafka` | `9092` | Apache Kafka broker chạy KRaft mode |
| `kafka-ui` | internal | UI xem topic Kafka, proxy qua Nginx ở production |
| `kafka-exporter` | internal | Export Kafka metrics cho Prometheus |
| `prometheus` | internal | Scrape metrics và chạy alert rules |
| `alertmanager` | internal | Gửi alert qua email |

## Cấu Trúc Thư Mục

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

Mỗi Django service độc lập với `Dockerfile`, `requirements.txt`,
`.env.example`, `manage.py`, settings, app, tests và OpenAPI schema nếu có.

## Yêu Cầu Cài Đặt

- Docker Engine và Docker Compose plugin.
- Meta Developer app.
- Facebook Page access token có các quyền phù hợp với API bạn dùng.
- Public HTTPS tunnel hoặc domain để test webhook, ví dụ Ngrok.
- SMTP credentials hoặc Gmail App Password nếu muốn gửi alert qua email.

## Chạy Nhanh

1. Clone repo và vào thư mục dự án.

   ```bash
   git clone <repo-url>
   cd service-facebook-api
   ```

2. Tạo các file môi trường local.

   ```bash
   cp .env.example .env
   cp services/api-service/.env.example services/api-service/.env
   cp services/webhook-service/.env.example services/webhook-service/.env
   cp services/core-service/.env.example services/core-service/.env
   cp services/retry-service/.env.example services/retry-service/.env
   ```

3. Điền giá trị Facebook, Kafka, MongoDB, internal API và alerting vào các file
   `.env`.

4. Build và chạy toàn bộ stack.

   ```bash
   cd services
   docker compose up -d --build
   ```

5. Kiểm tra container và gateway health.

   ```bash
   docker compose ps
   curl http://localhost:3000/health
   ```

6. Dừng stack.

   ```bash
   docker compose down
   ```

## Cấu Hình Môi Trường

Docker Compose cần các file sau:

```text
.env
services/api-service/.env
services/webhook-service/.env
services/core-service/.env
services/retry-service/.env
```

Các biến quan trọng:

| Biến | Service dùng | Ý nghĩa |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | Django services | Thường là `config.settings.development` khi chạy local |
| `DJANGO_SECRET_KEY` | Django services | Secret key riêng cho từng service |
| `DEBUG` | Django services | Bật/tắt development mode, production nên để `False` |
| `ALLOWED_HOSTS` | Django services | Danh sách host Django cho phép |
| `FACEBOOK_GRAPH_API_VERSION` | api, webhook | Phiên bản Graph API, ví dụ `v25.0` |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | api, webhook | Page token dùng để gọi Graph API |
| `FACEBOOK_APP_ID` | api | Meta app id |
| `FACEBOOK_APP_SECRET` | api | Meta app secret |
| `FACEBOOK_WEBHOOK_VERIFY_TOKEN` | webhook | Token cấu hình trong Meta webhook settings |
| `FACEBOOK_WEBHOOK_SECRET` | webhook | App secret để validate `X-Hub-Signature-256` |
| `KAFKA_BOOTSTRAP_SERVERS` | all workers | Dùng `kafka:9092` trong Docker |
| `MONGO_DB_NAME`, `MONGO_HOST`, `MONGO_PORT` | core, retry | Cấu hình kết nối MongoDB |
| `CORE_INTERNAL_API_KEY` | core | Key bảo vệ core endpoint nếu được cấu hình |
| `RETRY_INTERNAL_API_KEY` | retry | Key bảo vệ retry endpoint nếu được cấu hình |
| `DIFY_API_URL`, `DIFY_API_KEY` | core | Tích hợp Dify AI tùy chọn |
| `LOG_LEVEL`, `LOG_FORMAT` | Django services | Log level và format log Python |
| `ALERTMANAGER_*` | alertmanager | Cấu hình SMTP sender, recipient và auth |

Không commit `.env` thật. Với production, lưu secret trong thư mục môi trường
trên VPS được GitHub Actions workflow sử dụng.

## URL Chính

URL gateway local:

| URL | Mô tả |
| --- | --- |
| `http://localhost:3000/health` | Health check của Nginx gateway |
| `http://localhost:3000/api/docs/swagger/` | Swagger UI của API service |
| `http://localhost:3000/api/docs/redoc/` | ReDoc của API service |
| `http://localhost:3000/webhook` | Facebook webhook callback |
| `http://localhost:3000/core/health` | Health check core service |
| `http://localhost:3000/core/docs/swagger/` | Swagger UI của core service |
| `http://localhost:3000/retry/health` | Health check retry service |
| `http://localhost:3000/retry/docs/swagger/` | Swagger UI của retry service |

Production Nginx có thêm route theo domain:

| Host | Target |
| --- | --- |
| `u-code.dev`, `fb.u-code.dev`, `api.u-code.dev` | Application gateway |
| `kafka.u-code.dev` | Kafka UI, bảo vệ bằng basic auth |
| `prometheus.u-code.dev` | Prometheus, bảo vệ bằng basic auth |
| `alerts.u-code.dev` | Alertmanager, bảo vệ bằng basic auth |

## Cấu Hình Facebook Webhook

1. Tạo Facebook Page và lưu Page ID.
2. Tạo Meta Developer app.
3. Generate Page Access Token với quyền phù hợp. Các quyền thường dùng:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `pages_read_user_content`
   - `pages_manage_engagement`
   - `read_insights`
4. Điền các biến trong `.env` của API và webhook service:
   - `FACEBOOK_GRAPH_API_VERSION`
   - `FACEBOOK_PAGE_ACCESS_TOKEN`
   - `FACEBOOK_APP_ID`
   - `FACEBOOK_APP_SECRET`
   - `FACEBOOK_WEBHOOK_VERIFY_TOKEN`
   - `FACEBOOK_WEBHOOK_SECRET`
5. Nếu test local, mở public tunnel:

   ```bash
   ngrok http 3000
   ```

6. Trong Meta Webhooks, chọn object `Page`:
   - Callback URL: `https://<ngrok-domain>/webhook`
   - Verify token: giá trị của `FACEBOOK_WEBHOOK_VERIFY_TOKEN`
7. Subscribe Page vào các field như `feed` và `messages`.

Webhook service có helper endpoint để subscribe comment/feed:

```http
POST /webhook/subscriptions/comments
```

## API

Các path dưới đây đi qua gateway local `http://localhost:3000`.

### API Service

| Method | Path | Mô tả |
| --- | --- | --- |
| `GET` | `/api/page/{page_id}` | Chi tiết Page |
| `GET` | `/api/page/{page_id}/posts` | Danh sách bài viết của Page |
| `POST` | `/api/page/{page_id}/posts` | Tạo bài viết Page |
| `DELETE` | `/api/page/post/{post_id}` | Xóa bài viết |
| `GET` | `/api/page/post/{post_id}/comments` | Danh sách comment của post |
| `GET` | `/api/page/post/{post_id}/likes` | Danh sách like của post |
| `GET` | `/api/page/{page_id}/insights` | Page insights |
| `POST` | `/api/page/comment/{comment_id}/hide` | Ẩn hoặc bỏ ẩn comment |
| `POST` | `/api/page/comment/{comment_id}/replies` | Reply comment |
| `POST` | `/api/page/{page_id}/messages` | Gửi Messenger message |

### Webhook Service

| Method | Path | Mô tả |
| --- | --- | --- |
| `GET` | `/webhook` | Meta webhook verification |
| `POST` | `/webhook` | Validate signature, normalize event, publish Kafka |
| `POST` | `/webhook/subscriptions/comments` | Subscribe Page vào comment/feed events |

### Core Service

Khi `CORE_INTERNAL_API_KEY` được set, request vào endpoint bảo vệ cần header
`X-Internal-Api-Key`.

| Method | Path | Mô tả |
| --- | --- | --- |
| `GET` | `/core/health` | Health check |
| `GET` | `/core/metrics` | Metrics event đã xử lý |
| `GET` | `/core/events` | Danh sách event đã xử lý |
| `GET` | `/core/events/{event_id}` | Chi tiết event kèm action logs và reviews |
| `POST` | `/core/events/{event_id}/retry` | Retry thủ công một event lỗi |
| `GET` | `/core/reviews` | Manual review queue |

### Retry Service

Khi `RETRY_INTERNAL_API_KEY` được set, request vào endpoint bảo vệ cần header
`X-Retry-Internal-Api-Key`.

| Method | Path | Mô tả |
| --- | --- | --- |
| `GET` | `/retry/health` | Health check |
| `GET` | `/retry/metrics` | Metrics retry attempts |
| `GET` | `/retry/attempts` | Danh sách retry attempts |
| `GET` | `/retry/attempts/{command_id}` | Chi tiết retry attempt |

## Kafka Topics

| Topic | Producer | Consumer | Mục đích |
| --- | --- | --- | --- |
| `raw_events` | webhook-service | core-worker | Event Facebook đã chuẩn hóa |
| `reply_commands` | core-worker | api-worker | Action Facebook cần thực thi |
| `send_failed` | api-worker, core-worker | retry-worker | Action lỗi có thể retry |
| `send_retry` | retry-worker | core-retry-worker | Retry command đã được lên lịch |
| `dead_letter` | retry-worker | operators/monitoring | Lỗi hết retry hoặc không thể retry |

## Trạng Thái Xử Lý

Core event states:

| State | Ý nghĩa |
| --- | --- |
| `received` | Event đã được nhận và lưu |
| `retrying` | Event đang được xử lý lại |
| `action_queued` | Facebook action command đã được queue |
| `ignored` | Event được bỏ qua có chủ đích |
| `review_pending` | Event cần review thủ công |
| `failed` | Core processing lỗi |
| `send_failed` | Dispatch action lỗi và đã gửi sang retry |
| `dlq_published` | Message đã được đưa vào dead letter flow |

Retry outcomes:

| Outcome | Ý nghĩa |
| --- | --- |
| `scheduled` | Retry đã được lên lịch |
| `dead_lettered` | Đã hết số lần retry |
| `skipped` | Retry message bị bỏ qua theo policy hoặc idempotency |

Xem thêm `CORE_RETRY_RUNBOOK.md` để biết topology retry và demo steps.

## Logging

Tất cả Django service và worker log ra stdout/stderr, đúng pattern khi chạy
Docker. Gunicorn access log và error log cũng đã bật.

Các lệnh hữu ích:

```bash
cd services
docker compose logs -f webhook-service
docker compose logs -f api-service api-worker
docker compose logs -f core-service core-worker core-retry-worker
docker compose logs -f retry-service retry-worker
docker compose logs -f prometheus alertmanager
```

Muốn tăng độ chi tiết log, set `LOG_LEVEL=DEBUG` trong `.env` của service rồi
recreate container:

```bash
cd services
docker compose up -d --build api-service api-worker
```

## Monitoring Và Alert

Prometheus:

- `prometheus/prometheus.yml`
- `prometheus/alert.rules.yml`

Alertmanager:

- `alertmanager/alertmanager.yml`
- các biến root `.env` có prefix `ALERTMANAGER_`

Các alert chính:

| Alert | Severity | Ý nghĩa |
| --- | --- | --- |
| `DeadLetterQueueReceived` | critical | Có message vào topic `dead_letter` |
| `KafkaConsumerLagHigh` | warning | Consumer lag Kafka cao |
| `WebhookReceiverSilent` | warning | Webhook ingestion có dấu hiệu im lặng |

Xem `alertmanager/README.md` để cấu hình SMTP và test alert thủ công.

## Phát Triển Local

Chạy một Django service không qua Docker:

```bash
cd services/api-service
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 3002
```

Thư mục và port tương ứng:

| Service | Thư mục | Port |
| --- | --- | ---: |
| API | `services/api-service` | `3002` |
| Webhook | `services/webhook-service` | `3001` |
| Core | `services/core-service` | `3003` |
| Retry | `services/retry-service` | `3004` |

## Testing

Chạy check và test trong từng service:

```bash
python manage.py check
python manage.py test
```

Chạy test thủ công cho toàn bộ service:

```bash
cd services/api-service && python manage.py test
cd ../webhook-service && python manage.py test
cd ../core-service && python manage.py test
cd ../retry-service && python manage.py test
```

Validate Docker Compose trước khi deploy:

```bash
cd services
docker compose config
```

## Deployment

GitHub Actions workflow:

```text
.github/workflows/python-app.yml
```

Workflow deploy khi push vào `main` hoặc chạy thủ công bằng
`workflow_dispatch`, sử dụng self-hosted Linux runner. Luồng deploy:

1. Dọn artifacts trong runner workspace.
2. Checkout repository.
3. Copy private environment files từ thư mục env trên VPS.
4. Kiểm tra Docker và Docker Compose.
5. Build Django services, Alertmanager và Nginx.
6. Start MongoDB và Kafka.
7. Chạy Django migrations.
8. Start toàn bộ Compose stack.
9. Health check gateway, core và retry.
10. Prune Docker images không dùng.

Các file môi trường production cần có:

```text
/opt/service-facebook-api/env/root.env
/opt/service-facebook-api/env/api-service.env
/opt/service-facebook-api/env/webhook-service.env
/opt/service-facebook-api/env/core-service.env
/opt/service-facebook-api/env/retry-service.env
```

Workflow hỗ trợ override bằng các biến như `SERVICE_FACEBOOK_ENV_DIR`,
`ROOT_ENV_FILE_PATH`, `API_SERVICE_ENV_FILE_PATH`,
`WEBHOOK_SERVICE_ENV_FILE_PATH`, `CORE_SERVICE_ENV_FILE_PATH`,
`RETRY_SERVICE_ENV_FILE_PATH`.

## Troubleshooting

| Vấn đề | Cần kiểm tra |
| --- | --- |
| Gateway unhealthy | `docker compose ps`, sau đó `docker compose logs -f nginx` |
| Không thấy application logs | Rebuild/recreate container và kiểm tra `LOG_LEVEL` |
| Facebook webhook verification lỗi | Callback URL, verify token, HTTPS domain và route `/webhook` |
| Webhook POST trả `401` | `FACEBOOK_WEBHOOK_SECRET` và Meta app secret |
| Kafka worker không xử lý message | Kafka health, topic name, consumer group id, worker logs |
| API action lỗi | Quyền của `FACEBOOK_PAGE_ACCESS_TOKEN` và log `api-worker` |
| Retry flow không chạy | `send_failed`, `retry-worker`, `send_retry`, `core-retry-worker` logs |
| Message vào DLQ | Kiểm tra `dead_letter`, source error logs và retry attempt records |
| Alert email không gửi | Root `.env` `ALERTMANAGER_*` và log `alertmanager` |

Runbook hữu ích:

- `CORE_RETRY_RUNBOOK.md`
- `alertmanager/README.md`
