#!/bin/bash
# DeepWiki 部署包生成脚本
# 输出: deepwiki-deploy-YYYYMMDD-HHMMSS.tar.gz
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="deepwiki-deploy-${TIMESTAMP}.tar.gz"
TMP="/tmp/deepwiki-pkg-$$"

cd "$PROJECT_DIR"

echo "========================================"
echo "  DeepWiki 部署包生成"
echo "========================================"

echo ""
echo "[1/3] 导出源码 (git archive)..."
mkdir -p "$TMP/app"
git archive --format=tar HEAD | tar -xC "$TMP/app"

echo "[2/3] 添加部署配置..."
cp deploy-package/docker-compose.yml "$TMP/app/"
cp .env.example "$TMP/app/.env"
cp deploy-package/deploy.sh "$TMP/app/"
cp deploy-package/DEPLOYMENT.md "$TMP/app/"

echo "[3/3] 生成压缩包..."
cd "$TMP"
tar -czf "$PROJECT_DIR/$ARCHIVE_NAME" app/
cd "$PROJECT_DIR"
rm -rf "$TMP"

echo ""
echo "========================================"
echo "  生成完成: $ARCHIVE_NAME"
echo "  $(du -sh "$ARCHIVE_NAME" 2>/dev/null || echo '')"
echo "========================================"
echo ""
echo "上传到服务器:"
echo "  scp $ARCHIVE_NAME root@dreamxu.xyz:/opt/deepwiki/"
echo ""
echo "在服务器上执行:"
echo "  cd /opt/deepwiki"
echo "  tar -xzf $ARCHIVE_NAME"
echo "  cd app"
echo "  vim .env           # 填写 API Key"
echo "  docker-compose up -d --build"
