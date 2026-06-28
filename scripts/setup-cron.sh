#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════
#  安装每小时自动备份的 cron 任务
# ═══════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
BACKUP_DIR="${HOME}/QA-backups"
LOG_FILE="${BACKUP_DIR}/backup.log"

chmod +x "${BACKUP_SCRIPT}"
chmod +x "${SCRIPT_DIR}/restore.sh"

# 创建备份目录
mkdir -p "${BACKUP_DIR}/db" "${BACKUP_DIR}/code"

# 构建 cron 行
CRON_LINE="0 * * * * QA_PROJECT_DIR=${PROJECT_DIR} QA_BACKUP_DIR=${BACKUP_DIR} bash ${BACKUP_SCRIPT} >> ${LOG_FILE} 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -qF "backup.sh"; then
  echo "⚠️  Cron job already exists. Current crontab:"
  crontab -l | grep "backup"
  echo ""
  read -p "Replace it? [y/N] " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
  fi
  # 删除旧的
  crontab -l 2>/dev/null | grep -vF "backup.sh" | crontab -
fi

# 添加新的
(crontab -l 2>/dev/null; echo "${CRON_LINE}") | crontab -

echo "✅ Cron job installed:"
echo "   Schedule: every hour at :00"
echo "   Script:   ${BACKUP_SCRIPT}"
echo "   Backups:  ${BACKUP_DIR}/"
echo "   Log:      ${LOG_FILE}"
echo "   Retention: 72 backups (3 days)"
echo ""
echo "Verify: crontab -l"
echo "Test now: ${BACKUP_SCRIPT}"
echo "Restore:  ${SCRIPT_DIR}/restore.sh list"
