#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env não encontrado em $ENV_FILE. ABORTING."
  exit 1
fi

set -a

source "$ENV_FILE"
set +a

NETWORK="${DOCKER_HOST_NETWORK:-jk-network}"
IMAGE_NAME="jk-db-setup"
CONTAINER_NAME="jk-db-setup"

echo "Rede Docker: $NETWORK"
echo "Construindo/usando imagem $IMAGE_NAME para rodar os scripts de banco."

docker build -t "$IMAGE_NAME:latest" "$SCRIPT_DIR"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "Removendo container antigo ${CONTAINER_NAME}..."
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

ADMIN_ENV_ARGS=()
if [ -n "$MYSQL_ADMIN_HOST" ] && [ -n "$MYSQL_ADMIN_PORT" ] && \
   [ -n "$MYSQL_ADMIN_USER" ] && [ -n "$MYSQL_ADMIN_PASSWORD" ]; then
  echo "Usando MYSQL_ADMIN_* do .env para conectar em $MYSQL_ADMIN_HOST:$MYSQL_ADMIN_PORT"
  ADMIN_ENV_ARGS=(
    -e "MYSQL_ADMIN_HOST=$MYSQL_ADMIN_HOST"
    -e "MYSQL_ADMIN_PORT=$MYSQL_ADMIN_PORT"
    -e "MYSQL_ADMIN_USER=$MYSQL_ADMIN_USER"
    -e "MYSQL_ADMIN_PASSWORD=$MYSQL_ADMIN_PASSWORD"
  )
else
  echo "MYSQL_ADMIN_* não configurados — usando mysql:3306 (modo dev)"
  ADMIN_ENV_ARGS=(
    -e MYSQL_HOST="mysql"
    -e MYSQL_EXPOSED_PORT="3306"
    -e "MYSQL_ROOT_USER=${MYSQL_ROOT_USER:-root}"
    -e "MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD"
  )
fi

# Credenciais do admin do ProxySQL — encaminhadas só quando presentes. Sem elas,
# proxysql_users.py faz no-op (ambiente sem ProxySQL).
PROXY_ADMIN_ENV_ARGS=()
if [ -n "$MYSQL_PROXY_ADMIN_HOST" ] && [ -n "$MYSQL_PROXY_ADMIN_PORT" ] && \
   [ -n "$MYSQL_PROXY_ADMIN_USER" ] && [ -n "$MYSQL_PROXY_ADMIN_PASSWORD" ]; then
  echo "Encaminhando MYSQL_PROXY_ADMIN_* para sync de usuários no ProxySQL ($MYSQL_PROXY_ADMIN_HOST:$MYSQL_PROXY_ADMIN_PORT)"
  PROXY_ADMIN_ENV_ARGS=(
    -e "MYSQL_PROXY_ADMIN_HOST=$MYSQL_PROXY_ADMIN_HOST"
    -e "MYSQL_PROXY_ADMIN_PORT=$MYSQL_PROXY_ADMIN_PORT"
    -e "MYSQL_PROXY_ADMIN_USER=$MYSQL_PROXY_ADMIN_USER"
    -e "MYSQL_PROXY_ADMIN_PASSWORD=$MYSQL_PROXY_ADMIN_PASSWORD"
  )
fi

docker run --rm \
  --name "$CONTAINER_NAME" \
  --network "$NETWORK" \
  -v "$PROJECT_ROOT":/workspace \
  -w /workspace/jk-database \
  "${ADMIN_ENV_ARGS[@]}" \
  "${PROXY_ADMIN_ENV_ARGS[@]}" \
  "$IMAGE_NAME:latest" \
  bash -c "figlet JK-DATABASE && python create_databases.py && python create_users.py && python create_dummy_tables.py && python proxysql_users.py"

  echo $?