# Hướng dẫn cấu hình Email Alert — Alertmanager

## Tổng quan

Hệ thống gửi email cảnh báo tự động khi:

| Alert | Điều kiện | Mức độ |
|-------|-----------|--------|
| **DeadLetterQueueReceived** | Có message mới vào `dead_letter` topic | 🔴 CRITICAL — Gửi ngay |
| **KafkaConsumerLagHigh** | Consumer lag > 500 message trong 2 phút | 🟡 WARNING |
| **WebhookReceiverSilent** | Không có event từ Facebook trong 10 phút | 🟡 WARNING |

---

## Bước 1: Chuẩn bị Gmail App Password

1. Vào **Google Account** → **Security**
2. Bật **2-Step Verification** (nếu chưa bật)
3. Vào **App passwords** → Chọn "Mail" và "Other"
4. Đặt tên "Alertmanager" → Click **Generate**
5. Copy password **16 ký tự** (dạng `xxxx xxxx xxxx xxxx`)

> ⚠️ Dùng App Password, KHÔNG dùng password Google thông thường

---

## Bước 2: Điền thông tin vào `.env` (root project)

Mở file `.env` ở thư mục gốc, tìm section `Alertmanager`:

```env
ALERTMANAGER_SMTP_FROM=your-email@gmail.com          # Email gửi
ALERTMANAGER_SMTP_AUTH_USERNAME=your-email@gmail.com # Cùng email gửi
ALERTMANAGER_SMTP_AUTH_PASSWORD=xxxx xxxx xxxx xxxx  # App Password 16 ký tự
ALERTMANAGER_EMAIL_TO=recipient@example.com          # Email nhận cảnh báo
```

---

## Bước 3: Rebuild và restart

```bash
cd services

# Rebuild alertmanager image (vì đã đổi từ image sang build)
docker compose build alertmanager

# Khởi động lại alertmanager
docker compose up -d alertmanager

# Kiểm tra log
docker compose logs -f alertmanager
```

---

## Bước 4: Kiểm tra hoạt động

### 4.1 Xem Alertmanager UI
Truy cập: http://localhost:9093

- Tab **Alerts**: Xem các alert đang active
- Tab **Silences**: Tắt tạm alert (dùng khi maintenance)
- Tab **Status**: Xem config đã load đúng chưa

### 4.2 Xem Prometheus UI
Truy cập: http://localhost:9090/alerts

- Xem trạng thái 3 alert rules: INACTIVE / PENDING / FIRING

### 4.3 Test bắn alert thủ công

```bash
# Bắn thử alert để kiểm tra email
curl -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {"alertname":"TestEmail","severity":"critical"},
    "annotations": {
      "summary": "Test email alert",
      "description": "Day la email test tu Alertmanager. Neu ban nhan duoc email nay, cau hinh da chinh xac!"
    }
  }]'
```

Sau 5-10 giây, kiểm tra inbox email nhận được thông báo.

### 4.4 Giả lập DLQ alert (realistic test)

```bash
# Publish 1 message vào dead_letter topic để giả lập DLQ alert
# Container name: services-kafka-1 (theo docker-compose trong thư mục services/)
# Image: apache/kafka:latest (KRaft mode) → script ở /opt/kafka/bin/

docker exec -it services-kafka-1 \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic dead_letter

# Gõ nội dung bất kỳ rồi Enter, sau đó Ctrl+C để thoát:
# {"test": "fake dlq message", "reason": "test alert"}
```

Trong vòng 1 phút, Prometheus phát hiện offset tăng → Alertmanager nhận alert → Email được gửi.

---

## Troubleshooting

| Lỗi | Nguyên nhân | Giải pháp |
|-----|------------|-----------|
| Email không gửi được | App Password sai | Tạo lại App Password mới |
| `Authentication failed` | 2FA chưa bật | Bật 2-Step Verification trên Google |
| `connection refused :587` | Firewall block | Kiểm tra outbound port 587 |
| Config không load | YAML syntax error | Chạy `docker compose logs alertmanager` |
| Placeholder không được thay thế | `.env` chưa có giá trị | Điền đầy đủ 4 biến `ALERTMANAGER_*` |

---

## Luồng hoạt động

```
Message fail hết retry
        ↓
Retry Service publish → dead_letter topic
        ↓
kafka-exporter expose metric: kafka_topic_partition_current_offset{topic="dead_letter"}
        ↓
Prometheus scrape mỗi 15s → phát hiện offset tăng
        ↓
Alert rule "DeadLetterQueueReceived" FIRING (for: 0m = ngay lập tức)
        ↓
Prometheus gửi alert → Alertmanager (http://alertmanager:9093)
        ↓
Alertmanager route theo severity=critical → group_wait=0s → Gửi ngay
        ↓
Gmail SMTP:587 → Email đến inbox của team
```
