#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# entrypoint.sh — Alertmanager startup script
# Thay thế placeholder trong alertmanager.yml bằng biến môi trường SMTP thực tế
# trước khi khởi động alertmanager.
# ─────────────────────────────────────────────────────────────────────────────

set -e

CONFIG_SRC="/etc/alertmanager/alertmanager.yml"
CONFIG_OUT="/tmp/alertmanager_rendered.yml"

echo "[entrypoint] Rendering alertmanager config..."
echo "[entrypoint]   SMTP_FROM      = ${ALERTMANAGER_SMTP_FROM}"
echo "[entrypoint]   SMTP_USERNAME  = ${ALERTMANAGER_SMTP_AUTH_USERNAME}"
echo "[entrypoint]   EMAIL_TO       = ${ALERTMANAGER_EMAIL_TO}"

# Thay thế 4 placeholder bằng giá trị từ biến môi trường
sed \
  -e "s|ALERTMANAGER_SMTP_FROM_PLACEHOLDER|${ALERTMANAGER_SMTP_FROM}|g" \
  -e "s|ALERTMANAGER_SMTP_AUTH_USERNAME_PLACEHOLDER|${ALERTMANAGER_SMTP_AUTH_USERNAME}|g" \
  -e "s|ALERTMANAGER_SMTP_AUTH_PASSWORD_PLACEHOLDER|${ALERTMANAGER_SMTP_AUTH_PASSWORD}|g" \
  -e "s|ALERTMANAGER_EMAIL_TO_PLACEHOLDER|${ALERTMANAGER_EMAIL_TO}|g" \
  "${CONFIG_SRC}" > "${CONFIG_OUT}"

echo "[entrypoint] Config rendered successfully to ${CONFIG_OUT}"

# Khởi động alertmanager với config đã được render
exec /bin/alertmanager \
  --config.file="${CONFIG_OUT}" \
  --log.level=info \
  "$@"
