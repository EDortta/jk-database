<!-- id: SEC-0024 | status: open | grupo: ZeeCred | severidade: critica | relacionadas: SEC-0189, SEC-0190, SEC-0191 -->

# SECURITY ALERT — SEC-0024: senhas de usuários de banco versionadas em texto claro

**Projeto:** YouBR/ZeeCred/jk-database
**Branch:** `WK-20260704-security-fixes` (work_id `WK-20260704-security-fixes`)
**Data:** 2026-07-04

## O que foi feito

- `users.json`: as 14 senhas em texto claro foram substituídas por placeholders
  de ambiente no formato `${USERS_PASSWORD_<NOME_DO_USUARIO_EM_MAIUSCULAS>}`
  (ex.: `core_user` -> `${USERS_PASSWORD_CORE_USER}`). O arquivo versionado
  passa a conter apenas nome/host/privilégios e a referência da variável.
- `db_credentials.py`: nova função `resolve_user_password()` que resolve o
  placeholder em runtime — primeiro em `os.environ`, depois no `.env` da raiz
  do projeto (não versionado). Falha com erro claro se a variável não existir.
- `create_users.py`: usa `resolve_user_password()`; os comandos
  `CREATE USER`/`ALTER USER` agora são logados com a senha redigida (`'***'`)
  para não vazar segredo em logs de container.
- `proxysql_users.py`: resolve as senhas pelo mesmo mecanismo antes de
  sincronizar a tabela `mysql_users` do ProxySQL.
- `run.sh`: encaminha automaticamente todas as variáveis `USERS_PASSWORD_*`
  do `.env` raiz para o container de provisionamento.
- `.gitignore`: reforçado para ignorar `.env.*` (exceto `*.example`),
  `users.local.json`, `*.secrets.json` e `*.secrets.env`.

## Como operar a partir de agora

Definir no `.env` da raiz do projeto (fora do controle de versão) uma variável
por usuário:

```
USERS_PASSWORD_CORE_USER=...
USERS_PASSWORD_CCB_USER=...
USERS_PASSWORD_EMPLOYEECREDIT_USER=...
USERS_PASSWORD_FGTSBMP_USER=...
USERS_PASSWORD_PAYROLLLOANBMP_USER=...
USERS_PASSWORD_WH_INGESTOR_USER=...
USERS_PASSWORD_PRIVATELABEL_USER=...
USERS_PASSWORD_WEBHOOK_PROXY_USER=...
USERS_PASSWORD_CREDIT_ENGINE_UY3_USER=...
USERS_PASSWORD_CREDIT_ENGINE_MILENIO_USER=...
USERS_PASSWORD_EMPLOYEE_CREDIT_UY3_USER=...
USERS_PASSWORD_PAYROLL_MARGIN_REGISTRAR_USER=...
USERS_PASSWORD_BILLING_CONTROL_NEOFIN_USER=...
USERS_PASSWORD_DUMMY_USER=...
```

Sem essas variáveis o provisionamento falha explicitamente (comportamento
intencional — nunca provisionar com senha ausente ou em claro no repo).

## PENDÊNCIA CRÍTICA (ação humana obrigatória)

**ROTACIONAR todas as senhas de banco expostas; limpeza de histórico git.**

- As 14 senhas removidas deste commit permanecem no histórico git local e no
  remoto (`github.com:EDortta/jk-database`, incluindo clones/forks/backups) e
  devem ser consideradas comprometidas.
- Ordem correta: (1) rotacionar TODAS as senhas no MySQL/ProxySQL e atualizar o
  `.env` dos ambientes; (2) só então limpar o histórico (git filter-repo/BFG) e
  coordenar force-push com quem tem clones.
- Recomendações complementares da issue: restringir `host` dos usuários a
  redes/CIDRs conhecidos em vez de `%`; avaliar secret manager (Vault/Docker
  secrets) no lugar do `.env`.

Nenhum push, deploy ou rotação foi executado por este agente (proibido sem
aprovação explícita do operador).

---

## Adendo 2026-07-04 — SEC-0189 / SEC-0190 / SEC-0191 (mesma branch)

### O que foi feito no código

- **SEC-0190**: `my-credentials.json` (root/`rootpass`) removido do versionamento
  e do working tree; adicionado ao `.gitignore`. `db_credentials.py` não tem mais
  fallback de credenciais: sem `MYSQL_ADMIN_*` (ou `MYSQL_ROOT_*` em modo dev) no
  ambiente/`.env` raiz, o provisionamento falha com erro claro. Variáveis passadas
  por `run.sh` via `-e` agora têm precedência sobre o `.env`. Criado `.env.example`
  documentando todas as variáveis exigidas (sem valores reais).
- **SEC-0189**: privilégios do `dummy_user` em `users.json` reduzidos ao mínimo que
  o scheduler de jobs precisa (`SELECT/INSERT/UPDATE/DELETE` em `dummy.*`);
  removidos `CREATE/ALTER/DROP/CREATE ROUTINE/TRIGGER/...`. O DDL de
  `jobs`/`job_events` já é aplicado com credencial admin (`create_dummy_tables.py`).
  No próximo provisionamento, `create_users.py` REVOGA os privilégios excedentes.
- **SEC-0191**: `resolve_user_password()` agora emite aviso `[SEC-0191]` (não fatal)
  quando a senha resolvida tem menos de 16 caracteres, para expor senhas fracas
  remanescentes a cada provisionamento.

### ROTAÇÕES PENDENTES (ação humana obrigatória — needs_operator)

1. **SEC-0190 — root/`rootpass`**: verificar TODOS os MySQL dev/staging criados com o
   fallback antigo e trocar a senha do `root` (`rootpass` está público no histórico
   git desde `661a524`). Nunca reutilizar `rootpass`.
2. **SEC-0189 — `dummy_user`**: rotacionar `dummy_pass` (exposta no histórico) em
   MySQL **e** ProxySQL de todos os ambientes (inclusive produção — o `run.sh`
   provisionava esse usuário incondicionalmente); atualizar
   `USERS_PASSWORD_DUMMY_USER` no `.env` e re-provisionar para aplicar também a
   redução de privilégios (REVOKE). Avaliar restringir `host` (`%` hoje) à rede do
   ProxySQL/backend.
3. **SEC-0191 — senhas curtas com template `Xx9#Xx@Jk`**: ao rotacionar as senhas de
   `core_user`, `ccb_user`, `employeecredit_user`, `fgtsbmp_user`,
   `payrollloanbmp_user` e `privatelabel_user` (obrigatório pelo SEC-0024), gerar
   >= 24 caracteres aleatórios POR USUÁRIO, sem template comum:
   `openssl rand -base64 24`. O mesmo vale para os demais usuários da lista acima.
4. Após as rotações: limpeza de histórico git (filter-repo/BFG) coordenada, como já
   descrito na pendência do SEC-0024.
