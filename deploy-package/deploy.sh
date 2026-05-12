#!/bin/bash
# DeepWiki 服务端部署脚本
# 用法: cd app && bash deploy.sh
set -e

echo "========================================"
echo "  DeepWiki 服务端部署"
echo "========================================"

# 检查 .env
if [ ! -f .env ] || ! grep -q "MINIMAX_API_KEY=" .env; then
  echo ""
  echo "请先编辑 .env 文件，填写 API Key:"
  echo "  vim .env"
  echo ""
  exit 1
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
  echo "Docker 未安装，请先安装 Docker"
  exit 1
fi

# 检查端口
BACKEND_PORT=$(grep -E "^BACKEND_PORT=" .env 2>/dev/null | cut -d= -f2 || echo "8001")
if ss -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT}"; then
  echo "警告: 端口 ${BACKEND_PORT} 已被占用，请在 .env 中修改 BACKEND_PORT"
fi

echo ""
echo "[1/2] 构建并启动容器..."
docker-compose down --remove-orphans 2>/dev/null || true
docker-compose up -d --build

echo ""
echo "[2/2] 等待服务就绪..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:${BACKEND_PORT}/health > /dev/null 2>&1; then
    echo "服务已启动!"
    FRONTEND_PORT=$(grep -E "^FRONTEND_PORT=" .env 2>/dev/null | cut -d= -f2 || echo "3000")
    echo ""
    echo "前端: http://localhost:${FRONTEND_PORT}"
    echo "后端: http://localhost:${BACKEND_PORT}"
    echo "健康检查: http://localhost:${BACKEND_PORT}/health"
    exit 0
  fi
  sleep 3
done

echo "启动超时，请检查 docker-compose logs"
exit 1
