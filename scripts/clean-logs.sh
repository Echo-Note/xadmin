#!/bin/bash
# 清理 server/data/logs/ 目录下的所有日志文件
# 临时使用，保留目录结构

set -e

LOG_DIR="$(cd "$(dirname "$0")/../server/data/logs" && pwd)"

if [ ! -d "$LOG_DIR" ]; then
    echo "日志目录不存在: $LOG_DIR"
    exit 1
fi

echo "清理日志目录: $LOG_DIR"

# 删除所有 .log 文件
find "$LOG_DIR" -type f -name '*.log' -delete

# 删除 daily 子目录（形如 YYYY-MM-DD/）
find "$LOG_DIR" -maxdepth 1 -type d | while IFS= read -r d; do
    basename=$(basename "$d")
    if echo "$basename" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
        rm -rf "$d"
    fi
done

# 删除 task/ 子目录内容
if [ -d "$LOG_DIR/task" ]; then
    rm -rf "$LOG_DIR/task"
fi

# 删除其他杂项文件
rm -f "$LOG_DIR/flower.db.db"

echo "清理完成"
