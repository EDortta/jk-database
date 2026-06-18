# 1) Fix mysqlclient build tooling (optional unless you really need mysqlclient)
sudo apt-get update
sudo apt-get install -y pkg-config build-essential python3-dev default-libmysqlclient-dev

# 2) Install the connector you are actually importing
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install mysql-connector-python

---

## Banco `dummy` e tabelas de infra (jobs/job_events)

O banco `dummy` (em `databases.json`) e o `dummy_user` (em `users.json`) existem para
serviços baseados no template que NÃO têm banco próprio (ex.: `caas_baas_bff`). Esses
serviços apontam `DB_DATABASE=dummy` no `.env` e, no boot, o scheduler de jobs adiados
exige as tabelas `jobs` e `job_events`.

Como em modo `deployment` o container roda o `dist` e NÃO executa as migrations TypeORM,
o DDL dessas tabelas é mantido em `estrutura/dummy_jobs.sql` e aplicado por
`create_dummy_tables.py` (encadeado no `run.sh`, após `create_users.py`).

ATENÇÃO — DRIFT: `estrutura/dummy_jobs.sql` é uma cópia manual consolidada das migrations
de jobs do template:
- `template/src/database/migrations/0000000000001-create-jobs-table.ts`
- `template/src/database/migrations/0000000000002-create-job-events-table.ts`
- `template/src/database/migrations/0000000000003-add-job-scheduling-and-idempotency.ts`

Se essas migrations mudarem, atualize `estrutura/dummy_jobs.sql` na mesma mudança.