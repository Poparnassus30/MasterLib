#!/usr/bin/env sh
set -eu

log() { printf "%s\n" "$*" >> "$LOG_FILE"; }

phase_1_fix_paths() {
  log "[PHASE 1] fix paths"
  # ex: normaliser chemins
}

phase_2_create_dirs() {
  log "[PHASE 2] create dirs"
  mkdir -p "$WORKSPACE/logs" "$WORKSPACE/kernel" "$WORKSPACE/runtime" "$WORKSPACE/registre"
}

phase_3_snapshot_tree() {
  log "[PHASE 3] tree snapshot"
  command -v tree >/dev/null 2>&1 && tree -a -L 4 "$PROJECT_ROOT" > "$WORKSPACE/logs/tree.log" || true
}

main() {
  # Variables injectées par Python via env
  # PROJECT_ROOT, WORKSPACE, LOG_FILE

  phase_1_fix_paths
  phase_2_create_dirs
  phase_3_snapshot_tree
  log "[OK] prepare done"
}

main "$@"
