#!/usr/bin/env sh
# masterboot/scripts/prepare_workspace.sh
# Variables requises (injectées par Python) :
# - PROJECT_ROOT
# - WORKSPACE (souvent: <project_root>/data)
# - LOG_FILE (souvent: <project_root>/data/logs/masterboot.log)

set -eu

log() { printf "%s\n" "$*" >> "$LOG_FILE"; }

phase_1_fix_paths() {
  log "[PHASE 1] fix paths"
  # place holder (normalisation future)
}

phase_2_create_dirs() {
  log "[PHASE 2] create dirs"
  mkdir -p "$WORKSPACE/logs" "$WORKSPACE/runtime" "$WORKSPACE/scan"
}

phase_3_snapshot_tree() {
  log "[PHASE 3] snapshot tree"
  if command -v tree >/dev/null 2>&1; then
    tree -a -L 6 "$PROJECT_ROOT" > "$WORKSPACE/scan/tree_project.txt" 2>/dev/null || true
  else
    log "[PHASE 3] tree command not found (skip)"
  fi
}

main() {
  : "${PROJECT_ROOT:?Missing PROJECT_ROOT}"
  : "${WORKSPACE:?Missing WORKSPACE}"
  : "${LOG_FILE:?Missing LOG_FILE}"

  phase_1_fix_paths
  phase_2_create_dirs
  phase_3_snapshot_tree
  log "[OK] prepare done"
}

main "$@"
