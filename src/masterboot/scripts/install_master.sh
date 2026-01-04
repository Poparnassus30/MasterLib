#!/usr/bin/env sh
# masterboot/scripts/install_master.sh
# Installe la commande "master" globalement via pipx (option 1).
# Usage:
#   sh install_master.sh
#   MASTERLIB_REPO=/chemin/vers/MasterLib sh install_master.sh
#
# Notes:
# - En prod, on visera plus tard un paquet .deb (option 3).
set -eu

MASTERLIB_REPO="${MASTERLIB_REPO:-$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)}"
LOG_DIR="${LOG_DIR:-$MASTERLIB_REPO/data/logs}"
LOG_FILE="$LOG_DIR/install_master.log"

mkdir -p "$LOG_DIR"

log() { printf "%s\n" "$*" | tee -a "$LOG_FILE" >/dev/null; }

log "[INSTALL] MasterLib repo = $MASTERLIB_REPO"
log "[INSTALL] log          = $LOG_FILE"

# 1) pipx present ?
if ! command -v pipx >/dev/null 2>&1; then
  log "[INSTALL] pipx not found -> installing via apt"
  if command -v apt >/dev/null 2>&1; then
    sudo apt update | tee -a "$LOG_FILE" >/dev/null
    sudo apt install -y pipx | tee -a "$LOG_FILE" >/dev/null
  else
    log "[ERROR] apt not found. Install pipx manually."
    exit 1
  fi
else
  log "[INSTALL] pipx already installed"
fi

# 2) ensure path (doesn't modify current shell)
pipx ensurepath | tee -a "$LOG_FILE" >/dev/null || true
log "[INSTALL] pipx ensurepath done (restart shell if 'master' not found)"

# 3) install masterlib in pipx (editable)
# If already installed, reinstall to match local repo.
if pipx list | grep -qi "masterlib"; then
  log "[INSTALL] masterlib already in pipx -> reinstall (editable)"
  pipx reinstall masterlib --editable "$MASTERLIB_REPO" | tee -a "$LOG_FILE" >/dev/null
else
  log "[INSTALL] installing masterlib via pipx (editable)"
  pipx install --editable "$MASTERLIB_REPO" | tee -a "$LOG_FILE" >/dev/null
fi

# 4) sanity check
if command -v master >/dev/null 2>&1; then
  log "[OK] 'master' is available: $(command -v master)"
  master --help >/dev/null 2>&1 || true
else
  log "[WARN] 'master' not found in PATH. Restart your shell or run:"
  log "       export PATH=\"\$HOME/.local/bin:\$PATH\""
  exit 2
fi

log "[NOTE] Later: package .deb (option 3) when stable releases are tagged."
