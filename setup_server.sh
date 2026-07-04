#!/usr/bin/env bash
#
# Automated server setup script
# Usage: fill in the CONFIG section below, then run:
#   chmod +x setup_server.sh
#   ./setup_server.sh
#
# Run as a normal sudo-capable user (not root).
# Tested on Ubuntu. Review before running on a production box.

set -euo pipefail

# ============ CONFIG — edit these ============
DOMAIN="your_domain.com"
DOMAIN_WWW="www.your_domain.com"
EMAIL="your_email@example.com"

DB_NAME="your_db_name"
DB_USER="your_user"
DB_PASSWORD="your_password"

REDIS_PASSWORD="your_redis_password"

PROJECT_NAME="your_project"
PROJECT_DIR="/var/www/${PROJECT_NAME}"
REPO_URL="git@github.com:your_username/your_repo.git"
GIT_NAME="Your Name"
GIT_EMAIL="${EMAIL}"

SECRET_KEY="change_me_$(openssl rand -hex 16)"
LINUX_USER="$(whoami)"
IS_DJANGO=true   # set false to skip migrate/collectstatic/createsuperuser
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

# 6. Git + clone
step_git_clone() {
    log "Configuring Git and cloning repo"
    sudo apt install git -y
    git config --global user.name "${GIT_NAME}"
    git config --global user.email "${GIT_EMAIL}"

    if [ ! -f ~/.ssh/id_ed25519 ]; then
        ssh-keygen -t ed25519 -C "${GIT_EMAIL}" -N "" -f ~/.ssh/id_ed25519
    fi
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_ed25519

    echo "---- Add this public key to GitHub (Settings > SSH Keys) ----"
    cat ~/.ssh/id_ed25519.pub
    pause "Add the key to GitHub now, then"

    sudo mkdir -p "${PROJECT_DIR}"
    sudo chown "${LINUX_USER}:${LINUX_USER}" "${PROJECT_DIR}"
    cd "${PROJECT_DIR}"
    if [ ! -d .git ]; then
        git clone "${REPO_URL}" .
    else
        echo "Repo already cloned, skipping."
    fi
}

# 7. Virtualenv + app setup
step_venv_setup() {
    log "Setting up virtualenv and app"
    cd "${PROJECT_DIR}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    [ -f requirements.txt ] && pip install -r requirements.txt
    pip install gunicorn psycopg2-binary

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

    if [ "${IS_DJANGO}" = true ] && [ -f manage.py ]; then
        python manage.py migrate
        python manage.py collectstatic --no-input
        echo "Run 'python manage.py createsuperuser' manually (needs interactive input)."
    fi
    deactivate
}

# 8. systemd service
step_systemd_service() {
    log "Creating systemd service"
    sudo tee "/etc/systemd/system/${PROJECT_NAME}.service" > /dev/null <<EOF
[Unit]
Description=${PROJECT_NAME} Gunicorn Service
After=network.target postgresql.service redis-server.service

[Service]
Type=notify
User=${LINUX_USER}
Group=www-data
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/.venv/bin"
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/gunicorn \\
    --workers 4 \\
    --threads 2 \\
    --worker-class=gthread \\
    --worker-tmp-dir /dev/shm \\
    --bind unix:${PROJECT_DIR}/${PROJECT_NAME}.sock \\
    ${PROJECT_NAME}.wsgi:application
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

# 9. Nginx site config
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

# 10. SSL
step_ssl() {
    log "Setting up SSL with Let's Encrypt"
    pause "Make sure ${DOMAIN} and ${DOMAIN_WWW} already point at this server's IP, then"
    sudo apt install certbot python3-certbot-nginx -y
    sudo certbot --nginx -d "${DOMAIN}" -d "${DOMAIN_WWW}" -m "${EMAIL}" --agree-tos --non-interactive
    sudo systemctl enable --now certbot.timer
}

# 11. Firewall
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

# 12. Backups
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

# 13. Permissions
step_permissions() {
    log "Setting permissions"
    sudo chown -R www-data:www-data "${PROJECT_DIR}"
    sudo chmod -R 755 "${PROJECT_DIR}"
    sudo chmod -R 775 "${PROJECT_DIR}/media" "${PROJECT_DIR}/static" 2>/dev/null || true
}

# 14. Health check
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
    step_git_clone
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
