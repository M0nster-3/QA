#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
#  QA 自动备份脚本
#  由 cron 每小时执行一次，保留最近 72 份（3 天）
# ═══════════════════════════════════════════════════════

# ── 配置 ──
PROJECT_DIR="${QA_PROJECT_DIR:-$HOME/QA}"
BACKUP_DIR="${QA_BACKUP_DIR:-$HOME/QA-backups}"
DB_PATH="${PROJECT_DIR}/server/data/arxiv_qa.db"
KEEP_COUNT=72  # 3 days * 24 hours
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ── 颜色（cron 下不需要，终端手动跑时有用）──
if [ -t 1 ]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; NC=''
fi

log() { echo -e "${GREEN}[backup]${NC} $1"; }
warn() { echo -e "${YELLOW}[backup]${NC} $1"; }
err() { echo -e "${RED}[backup]${NC} $1" >&2; }

# ── 创建备份目录 ──
mkdir -p "${BACKUP_DIR}/db"
mkdir -p "${BACKUP_DIR}/code"

# ── 1. 数据库备份（使用 python3 sqlite3 模块，安全不锁表）──
if [ -f "${DB_PATH}" ]; then
  BACKUP_FILE="${BACKUP_DIR}/db/qa_${TIMESTAMP}.db"
  python3 -c "
import sqlite3
src = sqlite3.connect('${DB_PATH}')
dst = sqlite3.connect('${BACKUP_FILE}')
src.backup(dst)
dst.close()
src.close()
"
  
  # 压缩
  gzip "${BACKUP_FILE}"
  log "DB backup: qa_${TIMESTAMP}.db.gz ($(du -h "${BACKUP_FILE}.gz" | cut -f1))"
else
  warn "DB not found at ${DB_PATH}, skipping database backup"
fi

# ── 2. 代码快照（轻量 tar，排除 node_modules/dist/data）──
CODE_BACKUP="${BACKUP_DIR}/code/code_${TIMESTAMP}.tar.gz"
tar czf "${CODE_BACKUP}" \
  -C "$(dirname "${PROJECT_DIR}")" \
  --exclude="node_modules" \
  --exclude="dist" \
  --exclude="__pycache__" \
  --exclude="*.db" \
  --exclude="*.db-wal" \
  --exclude="*.db-shm" \
  --exclude=".env" \
  "$(basename "${PROJECT_DIR}")" \
  2>/dev/null || true
log "Code snapshot: code_${TIMESTAMP}.tar.gz ($(du -h "${CODE_BACKUP}" | cut -f1))"

# ── 3. 清理旧备份（保留最近 KEEP_COUNT 份）──
cleanup() {
  local dir="$1"
  local count
  count=$(ls -1 "${dir}" 2>/dev/null | wc -l)
  if [ "${count}" -gt "${KEEP_COUNT}" ]; then
    local to_delete=$((count - KEEP_COUNT))
    ls -1t "${dir}" | tail -n "${to_delete}" | while read -r f; do
      rm -f "${dir}/${f}"
    done
    log "Cleaned ${to_delete} old backups from ${dir}"
  fi
}

cleanup "${BACKUP_DIR}/db"
cleanup "${BACKUP_DIR}/code"

# ── 4. 统计 ──
DB_COUNT=$(ls -1 "${BACKUP_DIR}/db" 2>/dev/null | wc -l)
CODE_COUNT=$(ls -1 "${BACKUP_DIR}/code" 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)
log "Done. DB: ${DB_COUNT} backups, Code: ${CODE_COUNT} snapshots, Total: ${TOTAL_SIZE}"
