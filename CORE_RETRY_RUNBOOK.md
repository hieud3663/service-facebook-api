# Core and Retry Service Runbook

## Runtime topology

The implemented runtime keeps the existing stable services intact:

```text
webhook-service -> raw_events -> core-worker -> reply_commands -> api-worker -> Facebook Graph API
                                      ^                         |
                                      |                         v
retry-worker -> send_retry -> core-retry-worker          send_failed
      |
      v
dead_letter
```

`core-service` never calls Facebook Graph API directly and no longer calls `api-service` over internal HTTP for moderation actions. It publishes action commands to `reply_commands`. `api-worker` consumes those commands, calls Facebook Graph API, and publishes failures to `send_failed`. `retry-service` never calls Facebook or AI providers; it only consumes `send_failed` and publishes either `send_retry` or `dead_letter`.

## Services

- `core-service`: web endpoints at `/core/*`, port `3003`.
- `core-worker`: consumes `raw_events`.
- `core-retry-worker`: consumes `send_retry`.
- `api-worker`: consumes `reply_commands` and executes Facebook actions.
- `retry-service`: web endpoints at `/retry/*`, port `3004`.
- `retry-worker`: consumes `send_failed`.
- `kafka-ui`: Kafka UI at `http://localhost:8080`.
- `prometheus`: metrics at `http://localhost:9090`.
- `alertmanager`: alerts at `http://localhost:9093`.

## Kafka topics

- `raw_events`: webhook-service publishes normalized events.
- `reply_commands`: core publishes Facebook action commands for api-worker.
- `send_failed`: api-worker publishes Facebook action failures; core can also publish command queue failures.
- `send_retry`: retry-service publishes retry commands.
- `dead_letter`: retry-service publishes exhausted or non-retryable failures.

## Quick checks

```bash
cd services
docker compose config
docker compose up --build
```

Health endpoints through the gateway:

```text
GET http://localhost:3000/core/health
GET http://localhost:3000/retry/health
```

Direct service health endpoints:

```text
GET http://localhost:3003/core/health
GET http://localhost:3004/retry/health
```

## Demo retry flow

1. Open Kafka UI at `http://localhost:8080`.
2. Publish a message to `send_failed`:

```json
{
  "command_id": "demo-event:reply_comment:demo-comment",
  "event_id": "demo-event",
  "action_type": "reply_comment",
  "target_id": "demo-comment",
  "page_id": "demo-page",
  "retry_count": 0,
  "max_retries": 3,
  "retryable": true,
  "failure_type": "api_timeout",
  "reason": "demo timeout",
  "payload": {
    "comment_id": "demo-comment",
    "message": "hello"
  },
  "raw_event": {
    "event_id": "demo-event",
    "event_type": "comment",
    "page_id": "demo-page",
    "sender_id": "demo-user",
    "comment_id": "demo-comment",
    "message_text": "demo"
  },
  "source_service": "demo"
}
```

3. `retry-worker` waits according to backoff and publishes to `send_retry`.
4. `core-retry-worker` consumes `send_retry` and calls `EventProcessor(..., force_retry=True)`.
5. Core republishes the action to `reply_commands`.
6. If Facebook execution fails again, `api-worker` publishes back to `send_failed`.
7. When retry exceeds `max_retries`, `retry-worker` publishes to `dead_letter`.

## Dead letter alert

Prometheus loads `prometheus/alert.rules.yml`. The `DeadLetterQueueReceived` alert fires when the Kafka exporter reports an offset increase on topic `dead_letter`.
