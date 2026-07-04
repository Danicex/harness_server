#!/usr/bin/env bash
#
# create_user.sh — run ONCE as root on a fresh server.
# Creates a sudo-capable user, copies your SSH key so you can log in
# directly as that user, and optionally disables root SSH login.
#
# Usage (as root):
#   ./create_user.sh
#
set -euo pipefail

# ============ CONFIG — edit these ============
NEW_USER="tegabytes"
DISABLE_ROOT_LOGIN=true   # set false if you want to keep root SSH access too
# ===============================================

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this as root (or with sudo)." >&2
    exit 1
fi

log() { echo -e "\n\033[1;32m==> $1\033[0m"; }

# 1. Create the user
log "Creating user '${NEW_USER}'"
if id "${NEW_USER}" &>/dev/null; then
    echo "User ${NEW_USER} already exists, skipping creation."
else
    adduser --gecos "" "${NEW_USER}"
fi

# 2. Grant sudo
log "Adding ${NEW_USER} to sudo group"
usermod -aG sudo "${NEW_USER}"

# 3. Set up SSH access for the new user
log "Setting up SSH access"
NEW_HOME="/home/${NEW_USER}"
mkdir -p "${NEW_HOME}/.ssh"

if [ -f /root/.ssh/authorized_keys ]; then
    # Copy whatever keys let you into root right now
    cp /root/.ssh/authorized_keys "${NEW_HOME}/.ssh/authorized_keys"
    echo "Copied root's authorized_keys to ${NEW_USER}."
else
    echo "No /root/.ssh/authorized_keys found."
    echo "Paste the public key you want to use for ${NEW_USER} (or leave blank and add it manually later):"
    read -r PUBKEY
    if [ -n "${PUBKEY}" ]; then
        echo "${PUBKEY}" > "${NEW_HOME}/.ssh/authorized_keys"
    fi
fi

chmod 700 "${NEW_HOME}/.ssh"
chmod 600 "${NEW_HOME}/.ssh/authorized_keys" 2>/dev/null || true
chown -R "${NEW_USER}:${NEW_USER}" "${NEW_HOME}/.ssh"

# 4. Test before locking root out
log "IMPORTANT: before continuing, open a NEW terminal and confirm you can log in as:"
echo "    ssh ${NEW_USER}@<server-ip>"
echo "Do NOT close this session until you've confirmed that works."
read -rp "Press Enter once you've confirmed SSH access as ${NEW_USER}..."

# 5. Optionally disable root login
if [ "${DISABLE_ROOT_LOGIN}" = true ]; then
    log "Disabling root SSH login"
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
    systemctl restart ssh || systemctl restart sshd
    echo "Root SSH login disabled. Log in as ${NEW_USER} and use sudo from now on."
else
    echo "Root SSH login left enabled (DISABLE_ROOT_LOGIN=false)."
fi

log "Done. Log in as: ssh ${NEW_USER}@<server-ip>, then run setup_server.sh from there."
