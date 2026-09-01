#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="${SELF_SERVICE_USER:-libraryapps}"
GROUP_NAME="${SELF_SERVICE_GROUP:-libraryapps}"
PYTHON="${PYTHON:-python3}"

if [[ ! -d "$ROOT/services/main" ]]; then
  echo "Business source has not been imported yet." >&2
  echo "Run: $ROOT/scripts/import_original_source.py /path/to/original/repo --force" >&2
  exit 2
fi

# "$PYTHON" -m venv "$ROOT/.venv"
# "$ROOT/.venv/bin/pip" install --upgrade pip
# "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
#"$ROOT/scripts/validate_structure.py"
"$ROOT/scripts/render_systemd.py" --root "$ROOT" --user "$USER_NAME" --group "$GROUP_NAME"

sudo mkdir -p /etc/self-service-app
if [[ ! -f /etc/self-service-app/self-service.env ]]; then
  sudo cp "$ROOT/systemd/self-service.env.example" /etc/self-service-app/self-service.env
  echo "Created /etc/self-service-app/self-service.env; edit SECRET_KEY and application variables before starting."
fi
sudo cp "$ROOT"/systemd/generated/*.service "$ROOT"/systemd/generated/*.target /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable self-service.target

echo "Installed systemd units. After editing /etc/self-service-app/self-service.env:"
echo "  sudo systemctl start self-service.target"
