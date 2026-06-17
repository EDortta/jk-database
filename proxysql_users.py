"""Sincroniza os app users (users.json) na tabela mysql_users do ProxySQL.

Roda como passo final do jk-database, DEPOIS de create_databases.py/create_users.py.
É condicional e idempotente:

- Só age quando as quatro MYSQL_PROXY_ADMIN_* estão presentes no ambiente
  (ProxySQL em uso). Sem elas (dev/local sem ProxySQL) faz no-op silencioso.
- Upsert aditivo (REPLACE INTO) por usuário — nunca remove usuários, para
  preservar contas de infra (monitor, tunnel, etc.).

Convenções espelhadas de tools/proxysql/manage.py: default_hostgroup=10 (writer),
transaction_persistent=1, active=1. Writes vão ao primary; SELECTs são roteados
ao reader pelas query rules já configuradas no ProxySQL.
"""

import json
import os

import mysql.connector

from create_users import exec_sql, log, wait_for_port_open

# Espelha tools/proxysql/manage.py (WRITER_HOSTGROUP).
WRITER_HOSTGROUP = 10
DEFAULT_ADMIN_PORT = 36032


def load_proxysql_admin_credentials():
    """Retorna dict com credenciais do admin do ProxySQL, ou None se ausentes."""
    host = (os.environ.get("MYSQL_PROXY_ADMIN_HOST") or "").strip()
    port = (os.environ.get("MYSQL_PROXY_ADMIN_PORT") or "").strip()
    user = (os.environ.get("MYSQL_PROXY_ADMIN_USER") or "").strip()
    password = os.environ.get("MYSQL_PROXY_ADMIN_PASSWORD")

    if not host or not user or password is None or password == "":
        return None

    return {
        "host": host,
        "port": int(port) if port else DEFAULT_ADMIN_PORT,
        "user": user,
        "password": password,
    }


def sync_proxysql_users():
    admin = load_proxysql_admin_credentials()
    if admin is None:
        log("ProxySQL admin não configurado (MYSQL_PROXY_ADMIN_*) — pulando sync de mysql_users")
        return

    with open("users.json") as file:
        data = json.load(file)

    users = [u for u in data.get("users", []) if isinstance(u, dict)]
    app_users = [
        (str(u.get("name", "")).strip(), str(u.get("password", "")).strip())
        for u in users
    ]
    app_users = [(name, password) for name, password in app_users if name and password]

    log(f"Sincronizando {len(app_users)} app users no ProxySQL em {admin['host']}:{admin['port']}")
    wait_for_port_open(admin["host"], admin["port"])

    conn = mysql.connector.connect(
        host=admin["host"],
        port=admin["port"],
        user=admin["user"],
        password=admin["password"],
    )
    cursor = conn.cursor()

    for name, password in app_users:
        log(f"REPLACE INTO mysql_users username={name} default_hostgroup={WRITER_HOSTGROUP}")
        cursor.execute(
            "REPLACE INTO mysql_users "
            "(username, password, default_hostgroup, transaction_persistent, active) "
            "VALUES (%s, %s, %s, 1, 1)",
            (name, password, WRITER_HOSTGROUP),
        )

    exec_sql(cursor, "LOAD MYSQL USERS TO RUNTIME")
    exec_sql(cursor, "SAVE MYSQL USERS TO DISK")

    cursor.close()
    conn.close()
    log("proxysql_users.py finished successfully")


if __name__ == "__main__":
    sync_proxysql_users()
