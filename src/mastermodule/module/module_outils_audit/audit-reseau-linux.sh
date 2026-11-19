#!/usr/bin/env bash
# REINEROUGE - Audit réseau Linux
# Lecture seule côté système ; le rapport est écrit dans Documents.

set -u

DATE="$(date '+%Y-%m-%d_%H-%M-%S')"
HOST="$(hostname 2>/dev/null || printf 'linux')"
DOSSIER="${HOME:-/tmp}/Documents/REINEROUGE/Audits"

if ! mkdir -p "$DOSSIER"; then
    printf 'Impossible de créer le dossier de rapport : %s\n' "$DOSSIER" >&2
    exit 1
fi

FICHIER="$DOSSIER/audit_reseau_${HOST}_${DATE}.txt"

section() {
    printf '\n========== %s ==========\n\n' "$1" >> "$FICHIER"
}

collecter() {
    local titre="$1"
    shift
    section "$titre"

    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Commande absente : %s\n' "$1" >> "$FICHIER"
        return
    fi

    "$@" >> "$FICHIER" 2>&1 || {
        local code=$?
        printf '\nCode retour : %s\n' "$code" >> "$FICHIER"
    }
}

collecter_shell() {
    local titre="$1"
    local commande="$2"
    section "$titre"
    bash -c "$commande" >> "$FICHIER" 2>&1 || {
        local code=$?
        printf '\nCode retour : %s\n' "$code" >> "$FICHIER"
    }
}

printf 'REINEROUGE - AUDIT RESEAU LINUX\n' > "$FICHIER"
printf 'Date : %s\nMachine : %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$HOST" >> "$FICHIER"

collecter "SYSTEME" uname -a
collecter "DISTRIBUTION" cat /etc/os-release
collecter "INTERFACES RESEAU" ip -brief link
collecter_shell "ADRESSES IP ET DNS" 'ip -brief address; printf "\n--- resolv.conf ---\n"; cat /etc/resolv.conf'
collecter "ROUTES IPV4" ip -4 route
collecter "ROUTES IPV6" ip -6 route
collecter "ROUTAGE TEST IPV4" ip route get 1.1.1.1
collecter "ROUTAGE TEST IPV6" ip -6 route get 2606:4700:4700::1111
collecter "PROCESSUS VPN ET TUNNELS" pgrep -a -f 'warp|cloudflared|tailscale'
collecter "CONNEXIONS TCP ETABLI" ss -tnp state established
collecter "PORTS UDP" ss -ulpn

if command -v systemctl >/dev/null 2>&1; then
    collecter_shell "SERVICES VPN ET TUNNELS" "systemctl list-units --type=service --all --no-legend | grep -Ei 'warp|cloudflare|tailscale' || true"
fi

if command -v warp-cli >/dev/null 2>&1; then
    collecter "WARP STATUS" warp-cli status
    collecter "WARP SETTINGS" warp-cli settings
fi

if command -v tailscale >/dev/null 2>&1; then
    collecter "TAILSCALE STATUS" tailscale status
fi

printf '\nAudit terminé.\nRapport : %s\n' "$FICHIER"
