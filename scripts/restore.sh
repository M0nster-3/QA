#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
#  QA 回档脚本
#  用法:
#    ./restore.sh list              列出可用备份
#    ./restore.sh db [timestamp]    恢复数据库（默认最新）
#    ./restore.sh code [timestamp]  恢复代码（默认最新）
#    ./restore.sh full [timestamp]  恢复数据库 + 代码
# ═══════════════════════════════════════════════════════

PROJECT_DIR="${QA_PROJECT_DIR:-$HOME/QA}"
BACKUP_DIR="${QA_BACKUP_DIR:-$HOME/QA-backups}"
DB_PATH="${PROJECT_DIR}/server/data/arxiv_qa.db"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[restore]${NC} $1"; }
warn() { echo -e "${YELLOW}[restore]${NC} $1"; }
err() { echo -e "${RED}[restore]${NC} $1" >&2; }

cmd_list() {
  echo ""
  echo "=== Database Backups ==="
  ls -lht "${BACKUP_DIR}/db/" 2>/dev/null | head -20 || echo "  (none)"
  echo ""
  echo "=== Code Snapshots ==="
  ls -lht "${BACKUP_DIR}/code/" 2>/dev/null | head -20 || echo "  (none)"
  echo ""
  echo "Usage: ./restore.sh db|code|full [timestamp]"
  echo "  timestamp format: 20260622_143000"
  echo "  omit timestamp to use the latest backup"
}

find_backup() {
  local dir="$1" pattern="$2"
  if [ -n "${pattern}" ]; then
    local found
    found=$(ls -1 "${dir}" 2>/dev/null | grep "${pattern}" | head -1)
    if [ -z "${found}" ]; then
      err "No backup matching '${pattern}' in ${dir}"
      exit 1
    fi
    echo "${dir}/${found}"
  else
    local latest
    latest=$(ls -1t "${dir}" 2>/dev/null | head -1)
    if [ -z "${latest}" ]; then
      err "No backups found in ${dir}"
      exit 1
    fi
    echo "${dir}/${latest}"
  fi
}

cmd_db() {
  local ts="${1:-}"
  local backup
  backup=$(find_backup "${BACKUP_DIR}/db" "${ts}")
  log "Restoring DB from: $(basename "${backup}")"

  # 停止 uvicorn
  warn "Stopping QA service..."
  sudo systemctl stop qa 2>/dev/null || pkill -f "uvicorn.*backend.app" 2>/dev/null || true
  sleep 1

  # 备份当前 DB
  if [ -f "${DB_PATH}" ]; then
    cp "${DB_PATH}" "${DB_PATH}.pre-restore.$(date +%s)"
    log "Current DB backed up"
  fi

  # 恢复
  if [[ "${backup}" == *.gz ]]; then
    gunzip -c "${backup}" > "${DB_PATH}"
  else
    cp "${backup}" "${DB_PATH}"
  fi
  log "DB restored"

  # 重启
  warn "Starting QA service..."
  sudo systemctl start qa 2>/dev/null || log "Please restart uvicorn manually"
  log "Done!"
}

cmd_code() {
  local ts="${1:-}"
  local backup
  backup=$(find_backup "${BACKUP_DIR}/code" "${ts}")
  log "Restoring code from: $(basename "${backup}")"

  warn "Stopping QA service..."
  sudo systemctl stop qa 2>/dev/null || pkill -f "uvicorn.*backend.app" 2>/dev/null || true
  sleep 1

  # 备份当前代码
  local pre_restore="${PROJECT_DIR}.pre-restore.$(date +%s)"
  cp -r "${PROJECT_DIR}" "${pre_restore}"
  log "Current code backed up to ${pre_restore}"

  # 恢复（保留 .env 和 data/）
  local tmp_dir=$(mktemp -d)
  tar xzf "${backup}" -C "${tmp_dir}"
  local extracted=$(ls "${tmp_dir}")
  
  # 保存要保留的文件
  cp "${PROJECT_DIR}/.env" "${tmp_dir}/.env.keep" 2>/dev/null || true
  
  # 替换代码
  rsync -a --delete \
    --exclude=".env" \
    --exclude="server/data/" \
    --exclude="node_modules/" \
    --exclude="dist/" \
    "${tmp_dir}/${extracted}/" "${PROJECT_DIR}/"
  
  # 恢复 .env
  cp "${tmp_dir}/.env.keep" "${PROJECT_DIR}/.env" 2>/dev/null || true
  
  rm -rf "${tmp_dir}"
  log "Code restored"

  warn "Starting QA service..."
  sudo systemctl start qa 2>/dev/null || log "Please restart uvicorn manually"
  log "Done! You may need to rebuild frontend: cd ${PROJECT_DIR}/frontend-web && npm run build"
}

cmd_full() {
  local ts="${1:-}"
  cmd_db "${ts}"
  cmd_code "${ts}"
}

case "${1:-list}" in
  list) cmd_list ;;
  db)   cmd_db "${2:-}" ;;
  code) cmd_code "${2:-}" ;;
  full) cmd_full "${2:-}" ;;
  *)    echo "Usage: $0 {list|db|code|full} [timestamp]" ;;
esac
