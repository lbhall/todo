#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="/var/www/todos.emcfunleague.com/source"
VENV="/var/www/todos.emcfunleague.com/venv/bin"

echo "==> Pulling latest code..."
git -C "$SOURCE_DIR" pull

echo "==> Installing dependencies..."
"$VENV/pip" install -r "$SOURCE_DIR/requirements.txt" --quiet

echo "==> Running migrations..."
"$VENV/python" "$SOURCE_DIR/manage.py" migrate --noinput

echo "==> Collecting static files..."
"$VENV/python" "$SOURCE_DIR/manage.py" collectstatic --noinput

echo "==> Installing recurring-todos cron job..."
# Materialize each RecurringTodo template into a Todo for the coming week.
# Runs weekly on Sunday at 06:00. Re-written every deploy so it stays in sync.
# Runs as the user that owns the source tree (same user gunicorn runs as).
APP_USER="$(stat -c '%U' "$SOURCE_DIR")"
sudo tee /etc/cron.d/recurring-todos >/dev/null <<EOF
# Managed by deploy.sh — do not edit by hand; changes are overwritten on deploy.
SHELL=/bin/bash
0 6 * * 0 $APP_USER cd $SOURCE_DIR && $VENV/python manage.py create_recurring_todos >> $SOURCE_DIR/logs/recurring.log 2>&1
EOF
sudo chmod 0644 /etc/cron.d/recurring-todos

echo "==> Restarting gunicorn..."
sudo systemctl restart gunicorn.todos.service

echo "==> Done."
