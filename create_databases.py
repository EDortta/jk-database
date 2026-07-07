import mysql.connector
import json
import re

from create_users import quote_mysql_identifier
from db_credentials import load_db_credentials
from db_grants import ensure_can_create_databases

# SEC-0277: nomes de banco vêm de databases.json e são interpolados em SQL
# executado com privilégios admin — restringe ao formato seguro.
DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

with open('databases.json') as f:
    databases = json.load(f)

credentials = load_db_credentials()

import socket
import time

def wait_for_port_open(host, port):
    countDown=90
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print(f"Trying to connect to {host}:{port}. Count down: {countDown}")
            s.connect((host, port))
            s.close()
            break
        except socket.error:
            pass
        countDown -= 1
        if countDown == 0:
            raise Exception(f"Could not connect to {host}:{port}")
        time.sleep(0.5)

print("Waiting for MySQL to start...")
print(f"Host: {credentials['host']} Port: {credentials['port']}")
# SEC-0092: nunca logar a senha admin — apenas host/porta/usuário.
print(f"Username: {credentials['username']}")
time.sleep(5)
wait_for_port_open(credentials['host'], credentials['port'])
print(
    "Connecting with mysql.connector "
    f"host={credentials['host']} port={credentials['port']} "
    f"user={credentials['username']} database=mysql",
)

cnx = mysql.connector.connect(
    user=credentials['username'],
    password=credentials['password'],
    host=credentials['host'],
    port=credentials['port'],
    database='mysql'
)

cursor = cnx.cursor()
ensure_can_create_databases(cursor)

for db in databases:
    if not DATABASE_NAME_PATTERN.match(str(db)):
        raise ValueError(f"Nome de banco inválido em databases.json: {db!r}")
    sql = (
        f"CREATE DATABASE IF NOT EXISTS {quote_mysql_identifier(db)} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
    print(sql)
    cursor.execute(sql)

cursor.close()
cnx.close()
