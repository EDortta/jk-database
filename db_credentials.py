import os
import re
from pathlib import Path


ROOT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# SEC-0024: senhas de app users não vivem mais em texto claro no users.json.
# O campo "password" traz um placeholder "${VAR}" resolvido em runtime a partir
# do ambiente (ou do .env raiz, não versionado).
PASSWORD_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
# SEC-0191: senhas resolvidas com menos que isto geram aviso no provisionamento.
MIN_PASSWORD_LENGTH = 16
MYSQL_ADMIN_KEYS = (
    "MYSQL_ADMIN_HOST",
    "MYSQL_ADMIN_PORT",
    "MYSQL_ADMIN_USER",
    "MYSQL_ADMIN_PASSWORD",
)


def load_env_map(path):
    env_path = Path(path)
    if not env_path.exists():
        return {}
    result = {}
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _pick_first(values):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text != "":
            return text
    return None


def _warn_if_weak_password(user_name, value):
    """SEC-0191: aviso (não fatal) para senha curta/previsível ainda em uso.

    Senhas dos usuários de banco devem ter >= 24 caracteres aleatórios
    (ex.: `openssl rand -base64 24`), sem template comum entre usuários.
    Não falha para não travar re-provisionamento antes da rotação.
    """
    if len(value) < MIN_PASSWORD_LENGTH:
        print(
            f"[SEC-0191] AVISO: senha do usuário '{user_name}' tem menos de "
            f"{MIN_PASSWORD_LENGTH} caracteres. Rotacione para >= 24 caracteres "
            "aleatórios (openssl rand -base64 24).",
            flush=True,
        )


def resolve_user_password(user, env_map=None):
    """Resolve a senha de uma entrada do users.json (SEC-0024).

    - "${VAR}" -> busca VAR em os.environ e depois no .env raiz (não versionado).
    - Valor literal -> mantido por retrocompatibilidade (não recomendado).
    Levanta RuntimeError se a variável referenciada não estiver definida.
    """
    user_name = str(user.get("name", "")).strip() or "<sem nome>"
    raw = user.get("password")
    if raw is None or str(raw).strip() == "":
        raise RuntimeError(
            f"Usuário '{user_name}' em users.json não tem campo 'password'. "
            "Use um placeholder \"${USERS_PASSWORD_<NOME>}\" e defina a variável no ambiente."
        )

    match = PASSWORD_PLACEHOLDER_RE.match(str(raw).strip())
    if not match:
        _warn_if_weak_password(user_name, str(raw))
        return str(raw)

    var_name = match.group(1)
    value = os.environ.get(var_name)
    if value is None or value == "":
        if env_map is None:
            env_map = load_env_map(ROOT_ENV_PATH)
        value = env_map.get(var_name)
    if value is None or value == "":
        raise RuntimeError(
            f"Senha do usuário '{user_name}' referencia a variável '{var_name}', "
            f"que não está definida no ambiente nem em {ROOT_ENV_PATH}. "
            "Defina-a antes de provisionar (SEC-0024 — senhas fora do versionado)."
        )
    _warn_if_weak_password(user_name, value)
    return value


def load_db_credentials():
    """Credenciais admin do MySQL — SOMENTE de os.environ ou do .env raiz.

    SEC-0190: o fallback versionado my-credentials.json (root/rootpass) foi
    removido. Sem credenciais no ambiente/.env o provisionamento falha com
    erro claro em vez de tentar silenciosamente uma senha conhecida.
    """
    env_map = dict(load_env_map(ROOT_ENV_PATH))
    # os.environ tem precedência (run.sh injeta as variáveis no container).
    env_map.update(os.environ)
    admin_values = {key: env_map.get(key) for key in MYSQL_ADMIN_KEYS}
    admin_present = [key for key, value in admin_values.items() if value is not None]

    if admin_present:
        missing_admin = [key for key in MYSQL_ADMIN_KEYS if not str(admin_values.get(key) or "").strip()]
        if missing_admin:
            missing_text = ", ".join(missing_admin)
            raise RuntimeError(
                f"MYSQL_ADMIN_* variables must all be present and non-empty in {ROOT_ENV_PATH}. "
                f"Missing: {missing_text}."
            )
        return {
            "host": admin_values["MYSQL_ADMIN_HOST"].strip(),
            "port": int(admin_values["MYSQL_ADMIN_PORT"]),
            "username": admin_values["MYSQL_ADMIN_USER"].strip(),
            "password": admin_values["MYSQL_ADMIN_PASSWORD"],
        }

    host = _pick_first([
        env_map.get("MYSQL_HOST"),
        env_map.get("DB_HOST"),
    ])
    port = _pick_first([
        env_map.get("MYSQL_EXPOSED_PORT"),
        env_map.get("MYSQL_PORT"),
        env_map.get("DB_PORT"),
    ])
    username = _pick_first([
        env_map.get("MYSQL_ROOT_USER"),
        env_map.get("MYSQL_USER"),
        env_map.get("DB_USERNAME"),
    ])
    password = _pick_first([
        env_map.get("MYSQL_ROOT_PASSWORD"),
        env_map.get("MYSQL_PASSWORD"),
        env_map.get("DB_PASSWORD"),
    ])

    missing = [name for name, value in {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }.items() if value is None]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            f"Missing DB credentials: {missing_text}. "
            "Define MYSQL_ADMIN_* (ou MYSQL_HOST/MYSQL_EXPOSED_PORT/"
            "MYSQL_ROOT_USER/MYSQL_ROOT_PASSWORD) no ambiente ou em "
            f"{ROOT_ENV_PATH} (ver .env.example). "
            "SEC-0190: não existe mais fallback versionado de credenciais."
        )

    return {
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
    }
