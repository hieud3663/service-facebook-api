FROM prom/alertmanager:latest

# Copy config template và entrypoint script
COPY alertmanager.yml /etc/alertmanager/alertmanager.yml
COPY entrypoint.sh /entrypoint.sh

# Đổi về root để set permission, sau đó chạy lại với nobody
USER root
RUN chmod +x /entrypoint.sh && \
    chmod 644 /etc/alertmanager/alertmanager.yml

# Alertmanager image mặc định chạy user "nobody"
USER nobody

ENTRYPOINT ["/entrypoint.sh"]
