-- Infra de jobs do template (migrations 0000000000001..0000000000003) consolidada
-- para o banco `dummy`. Serviços baseados no template (ex.: caas_baas_bff) que não
-- têm banco próprio apontam para `dummy` e exigem as tabelas jobs/job_events no boot
-- (scheduler de jobs adiados). Idempotente: CREATE TABLE IF NOT EXISTS + índices inline.

CREATE TABLE IF NOT EXISTS jobs (
  id                   CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  channel              ENUM('sms','email','whatsapp','telegram','push','webhook','api','undefined') NOT NULL,
  stage                VARCHAR(32)  NOT NULL,
  state                VARCHAR(32)  NOT NULL,
  error                TEXT         NULL,
  provider             JSON         NULL,
  payload              JSON         NULL,
  version              BIGINT       NOT NULL DEFAULT 0,
  created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  execution_status     ENUM('scheduled','ready','running','done','failed') NOT NULL DEFAULT 'ready',
  run_at               TIMESTAMP    NULL,
  correlation_key      VARCHAR(191) NULL,
  dedupe_key           VARCHAR(191) NULL,
  deferral_count       INT          NOT NULL DEFAULT 0,
  max_deferrals        INT          NULL,
  last_deferral_reason VARCHAR(255) NULL,
  PRIMARY KEY (id),
  KEY IDX_JOBS_CHANNEL_UPDATED (channel, updated_at),
  KEY IDX_JOBS_EXECUTION_RUN_AT (execution_status, run_at),
  KEY IDX_JOBS_CORRELATION_UPDATED (correlation_key, updated_at),
  UNIQUE KEY UK_JOBS_DEDUPE_KEY (dedupe_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS job_events (
  id          CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  job_id      CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  stage       VARCHAR(32) NOT NULL,
  state       VARCHAR(32) NOT NULL,
  error       TEXT        NULL,
  meta        JSON        NULL,
  version     BIGINT      NOT NULL DEFAULT 0,
  created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id, job_id),
  UNIQUE KEY UK_JOB_EVENTS_JOB_VERSION (job_id, version),
  KEY IDX_JOB_EVENTS_JOB_CREATED (job_id, created_at),
  CONSTRAINT FK_JOB_EVENTS_JOB_ID FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
