#!/usr/bin/env bash
#
# Automated server setup script (FastAPI edition)
# Usage: fill in the CONFIG section below, then run:
#   chmod +x setup_server.sh
#   ./setup_server.sh
#
# Assumes:
#   - You already created a sudo user (see create_user.sh) and are running as them.
#   - You've already cloned your repo into PROJECT_DIR yourself.
#   - Your entrypoint is PROJECT_DIR/app/main.py with a FastAPI instance named `app`.
#
set -euo pipefail

# ============ CONFIG — edit these ============
DOMAIN="encheiron.com"
DOMAIN_WWW="www.encheiron.com"
EMAIL="encheiron@gmail.com"

DB_NAME="harness_db"
DB_USER="tegabytes"
DB_PASSWORD="2uqxjWF2ZDr8KM"

REDIS_PASSWORD="c8n6&d@@%fe5"

PROJECT_NAME="harness"
PROJECT_DIR="/var/www/${PROJECT_NAME}"

SECRET_KEY="change_me_$(openssl rand -hex 16)"
LINUX_USER="$(whoami)"

UVICORN_WORKERS=4
# ===============================================

log() { echo -e "\n\033[1;32m==> $1\033[0m"; }
pause() { read -rp "$1 Press Enter to continue..."; }

# 1. Update
step_update() {
    log "Updating system"
    sudo apt update && sudo apt upgrade -y
}

# 2. PostgreSQL
step_postgres() {
    log "Installing PostgreSQL"
    sudo apt install postgresql postgresql-contrib -y
    sudo systemctl enable --now postgresql

    sudo -u postgres psql <<EOF
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec

ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';
ALTER ROLE ${DB_USER} SET default_transaction_isolation TO 'read committed';
ALTER ROLE ${DB_USER} SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOF
}

# 3. Redis
step_redis() {
    log "Installing Redis"
    sudo apt install redis -y
    sudo sed -i "s/^# requirepass foobared/requirepass ${REDIS_PASSWORD}/" /etc/redis/redis.conf
    sudo systemctl enable --now redis-server
    sudo systemctl restart redis-server
    redis-cli -a "${REDIS_PASSWORD}" ping || echo "WARNING: redis ping failed"
}

# 4. Python
step_python() {
    log "Installing Python & build tools"
    sudo apt install python3 python3-pip python3-venv python3-dev build-essential libpq-dev -y
}

# 5. Nginx
step_nginx_install() {
    log "Installing Nginx"
    sudo apt install nginx -y
    sudo systemctl enable --now nginx
}

# 6. Virtualenv + app setup
step_venv_setup() {
    log "Setting up virtualenv and app"
    if [ ! -d "${PROJECT_DIR}" ]; then
        echo "ERROR: ${PROJECT_DIR} does not exist. Clone your repo there first." >&2
        exit 1
    fi
    if [ ! -f "${PROJECT_DIR}/app/main.py" ]; then
        echo "WARNING: ${PROJECT_DIR}/app/main.py not found — double check your project layout."
    fi

    cd "${PROJECT_DIR}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    [ -f requirements.txt ] && pip install -r requirements.txt
    pip install gunicorn uvicorn[standard] psycopg2-binary

    cat > .env <<EOF
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
SECRET_KEY=${SECRET_KEY}
DEBUG=False
EOF

    mkdir -p static media logs
    deactivate
}

# 7. systemd service (FastAPI via gunicorn + uvicorn worker)
step_systemd_service() {
    log "Creating systemd service"
    sudo tee "/etc/systemd/system/${PROJECT_NAME}.service" > /dev/null <<EOF
[Unit]
Description=${PROJECT_NAME} FastAPI Service
After=network.target postgresql.service redis-server.service

[Service]
User=${LINUX_USER}
Group=www-data
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/.venv/bin"
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/gunicorn \\
    --workers ${UVICORN_WORKERS} \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind unix:${PROJECT_DIR}/${PROJECT_NAME}.sock \\
    app.main:app
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now "${PROJECT_NAME}.service"
}

# 8. Nginx site config
step_nginx_config() {
    log "Configuring Nginx site"
    sudo tee "/etc/nginx/sites-available/${PROJECT_NAME}" > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} ${DOMAIN_WWW};
    root ${PROJECT_DIR};

    location /static/ {
        alias ${PROJECT_DIR}/static/;
        expires 30d;
    }

    location /media/ {
        alias ${PROJECT_DIR}/media/;
        expires 30d;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:${PROJECT_DIR}/${PROJECT_NAME}.sock;
        proxy_redirect off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
}
EOF

    sudo ln -sf "/etc/nginx/sites-available/${PROJECT_NAME}" /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
}

# 9. SSL
step_ssl() {
    log "Setting up SSL with Let's Encrypt"
    pause "Make sure ${DOMAIN} and ${DOMAIN_WWW} already point at this server's IP, then"
    sudo apt install certbot python3-certbot-nginx -y
    sudo certbot --nginx -d "${DOMAIN}" -d "${DOMAIN_WWW}" -m "${EMAIL}" --agree-tos --non-interactive
    sudo systemctl enable --now certbot.timer
}

# 10. Firewall
step_firewall() {
    log "Configuring firewall"
    sudo apt install ufw -y
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow http
    sudo ufw allow https
    sudo ufw --force enable
    sudo ufw status
}

# 11. Backups
step_backups() {
    log "Setting up daily DB backup cron job"
    cat > "/home/${LINUX_USER}/backup_db.sh" <<EOF
#!/bin/bash
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/postgresql"
mkdir -p \$BACKUP_DIR
PGPASSWORD='${DB_PASSWORD}' pg_dump -U ${DB_USER} -h localhost ${DB_NAME} > \$BACKUP_DIR/db_backup_\$DATE.sql
find \$BACKUP_DIR -name "db_backup_*.sql" -mtime +7 -delete
EOF
    chmod +x "/home/${LINUX_USER}/backup_db.sh"
    (crontab -l 2>/dev/null | grep -v backup_db.sh; echo "0 2 * * * /home/${LINUX_USER}/backup_db.sh") | crontab -
}

# 12. Permissions
step_permissions() {
    log "Setting permissions"
    sudo chown -R www-data:www-data "${PROJECT_DIR}"
    sudo chmod -R 755 "${PROJECT_DIR}"
    sudo chmod -R 775 "${PROJECT_DIR}/media" "${PROJECT_DIR}/static" 2>/dev/null || true
}

# 13. Health check
step_healthcheck() {
    log "Health check"
    for service in nginx postgresql redis-server "${PROJECT_NAME}"; do
        echo -n "$service: "
        systemctl is-active "$service" || true
    done
    curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" "http://localhost" || true
    sudo nginx -t
}

# ============ MAIN ============
main() {
    step_update
    step_postgres
    step_redis
    step_python
    step_nginx_install
    step_venv_setup
    step_systemd_service
    step_nginx_config
    step_ssl
    step_firewall
    step_backups
    step_permissions
    step_healthcheck
    log "Setup complete!"
}

main "$@"
