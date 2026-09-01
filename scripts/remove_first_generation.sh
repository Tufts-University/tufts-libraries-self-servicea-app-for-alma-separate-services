#!/usr/bin/env bash
set -euo pipefail
# Removes ONLY the first-generation units produced by the earlier package.
OLD_UNITS=(
  tufts-self-service.target
  tufts-self-service-gateway.service
  tufts-self-service-main.service
  tufts-self-service-barnes-and-noble.service
  tufts-self-service-bib-541.service
  tufts-self-service-p-and-e.service
  tufts-self-service-gift-fund.service
  tufts-self-service-sql.service
  tufts-self-service-concurrent-checkouts.service
  tufts-self-service-film-search.service
)
for unit in "${OLD_UNITS[@]}"; do
  sudo systemctl disable --now "$unit" 2>/dev/null || true
  sudo rm -f "/etc/systemd/system/$unit"
done
sudo systemctl daemon-reload
sudo systemctl reset-failed
cat <<'MSG'
First-generation generated units removed.
The script intentionally does NOT delete your original application checkout.
You may now remove the earlier generated directory manually after confirming its path.
MSG
