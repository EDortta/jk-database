"""Cria as tabelas de infra (jobs/job_events) no banco `dummy`.

Serviços baseados no template que não têm banco próprio apontam para `dummy`
(ver functions/*/.env: DB_DATABASE=dummy). O boot do template inicia o scheduler
de jobs adiados, que exige as tabelas jobs/job_events. As migrations TypeORM não
rodam em modo deployment, então aplicamos o DDL consolidado aqui.

Roda DEPOIS de create_databases.py (que garante o database `dummy`).
"""

import mysql.connector

from db_credentials import load_db_credentials

SQL_FILE = 'estrutura/dummy_jobs.sql'
TARGET_DB = 'dummy'

credentials = load_db_credentials()

with open(SQL_FILE) as f:
    sql_script = f.read()

statements = [s.strip() for s in sql_script.split(';') if s.strip()]

cnx = mysql.connector.connect(
    user=credentials['username'],
    password=credentials['password'],
    host=credentials['host'],
    port=credentials['port'],
    database=TARGET_DB,
)

cursor = cnx.cursor()
for stmt in statements:
    print(f"[{TARGET_DB}] executando: {stmt.splitlines()[0]} ...")
    cursor.execute(stmt)
cnx.commit()
cursor.close()
cnx.close()

print(f"-> tabelas de infra garantidas em `{TARGET_DB}`")
