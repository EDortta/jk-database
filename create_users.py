import json
import socket
import time
from datetime import datetime, timezone

from db_credentials import load_db_credentials
from db_grants import ensure_can_manage_users


FORBIDDEN_PRIVILEGES = {"ALL", "ALL PRIVILEGES"}


def log(message):
    print(message, flush=True)

def sanitize_privileges(privileges):
    cleaned = []
    removed = []

    for privilege in privileges:
        normalized = str(privilege).strip().upper()
        if not normalized:
            continue
        if normalized in FORBIDDEN_PRIVILEGES:
            removed.append(normalized)
            continue
        cleaned.append(normalized)

    return cleaned, removed


def wait_for_port_open(host, port):
    count_down = 90
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            log(f"Trying to connect to {host}:{port}. Count down: {count_down}")
            s.connect((host, int(port)))
            s.close()
            break
        except socket.error:
            pass
        count_down -= 1
        if count_down == 0:
            raise Exception(f"Could not connect to {host}:{port}")
        time.sleep(0.5)


def exec_sql(cursor, sql):
    log(sql)
    cursor.execute(sql)


def quote_mysql_string(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def quote_mysql_identifier(value):
    return "`" + str(value).replace("`", "``") + "`"


def build_user_id(user_name, user_host):
    return f"{quote_mysql_string(user_name)}@{quote_mysql_string(user_host)}"


def build_grantee(user_name, user_host):
    return f"'{str(user_name)}'@'{str(user_host)}'"


def desired_schema_privileges_for_user(user):
    desired = {}
    for privilege in user.get("privileges", []):
        database_name = privilege["database"]
        safe_privileges, _ = sanitize_privileges(privilege.get("privileges", []))
        if not safe_privileges:
            continue
        desired.setdefault(database_name, set()).update(safe_privileges)
    return desired


def compute_privilege_changes(current_privileges, desired_privileges):
    current = {str(item).strip().upper() for item in (current_privileges or []) if str(item).strip()}
    desired = {str(item).strip().upper() for item in (desired_privileges or []) if str(item).strip()}
    missing = sorted(desired - current)
    extra = sorted(current - desired)
    return missing, extra


def fetch_current_schema_privileges(cursor, grantee):
    cursor.execute(
        """
        SELECT TABLE_SCHEMA, PRIVILEGE_TYPE
        FROM information_schema.SCHEMA_PRIVILEGES
        WHERE GRANTEE = %s
        """,
        (grantee,),
    )
    privileges = {}
    for schema_name, privilege_type in cursor.fetchall():
        normalized = str(privilege_type or "").strip().upper()
        if not normalized:
            continue
        privileges.setdefault(schema_name, set()).add(normalized)
    return privileges


def collect_required_schema_privileges(users):
    required = {}
    for user in users:
        for database_name, privileges in desired_schema_privileges_for_user(user).items():
            required.setdefault(database_name, set()).update(privileges)
    return required


def create_users():
    import mysql.connector

    log(f"create_users.py started at {datetime.now(timezone.utc).isoformat()}")
    with open('users.json') as file:
        data = json.load(file)
    credentials = load_db_credentials()

    users = data.get('users', [])
    log(f"Loaded {len(users)} user entries from users.json")
    log("Waiting for MySQL to start...")
    time.sleep(5)
    wait_for_port_open(credentials['host'], credentials['port'])
    log(
        "Connecting with mysql.connector "
        f"host={credentials['host']} port={credentials['port']} "
        f"user={credentials['username']} database=mysql",
    )

    db = mysql.connector.connect(
        user=credentials['username'],
        password=credentials['password'],
        host=credentials['host'],
        port=credentials['port'],
        database='mysql'
    )

    cursor = db.cursor()
    ensure_can_manage_users(cursor, collect_required_schema_privileges(users))

    for user in users:
        user_name = user['name']
        user_host = user['host']
        user_password = user['password']
        user_id = build_user_id(user_name, user_host)
        grantee = build_grantee(user_name, user_host)
        desired_by_schema = desired_schema_privileges_for_user(user)
        current_by_schema = fetch_current_schema_privileges(cursor, grantee)

        exec_sql(cursor, f"CREATE USER IF NOT EXISTS {user_id} IDENTIFIED BY {quote_mysql_string(user_password)}")
        exec_sql(cursor, f"ALTER USER {user_id} IDENTIFIED BY {quote_mysql_string(user_password)}")

        for database_name, desired_privileges in sorted(desired_by_schema.items()):
            db_scope = f"{quote_mysql_identifier(database_name)}.*"
            current_privileges = current_by_schema.get(database_name, set())
            to_grant, to_revoke = compute_privilege_changes(current_privileges, desired_privileges)

            if to_revoke:
                revoke_query = "REVOKE {} ON {} FROM {}".format(
                    ", ".join(to_revoke), db_scope, user_id
                )
                exec_sql(cursor, revoke_query)

            if to_grant:
                grant_query = "GRANT {} ON {} TO {}".format(
                    ", ".join(to_grant), db_scope, user_id
                )
                exec_sql(cursor, grant_query)

            if not to_revoke and not to_grant:
                log(f"No privilege changes needed for {user_id} on {db_scope}")

        for database_name in sorted(set(current_by_schema) - set(desired_by_schema)):
            log(
                "Keeping unmanaged schema privileges for "
                f"{user_id} on {quote_mysql_identifier(database_name)}.*"
            )

    db.commit()
    cursor.close()
    db.close()
    log("create_users.py finished successfully")


if __name__ == "__main__":
    create_users()
