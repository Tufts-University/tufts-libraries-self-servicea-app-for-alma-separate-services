#!/usr/bin/env bash
systemctl --no-pager --full status self-service.target self-service-gateway.service self-service-main.service self-service-film-search.service || true
curl -fsS http://127.0.0.1:5002/health/services || true
echo
