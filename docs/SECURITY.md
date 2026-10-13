# AgentForge — Security

## Authentication & authorization

- Passwords: bcrypt (`gensalt` + `checkpw`), never plaintext; verified by test.
- JWT (`HS256`): 7-day expiry, `SECRET_KEY` from env (dev default must be replaced in prod).
- Logout revokes via Redis denylist (`SHA-256(token)` → TTL = remaining lifetime).
  Revoked tokens return `401`. No token server-side session to steal.
- Every project endpoint checks ownership (`403` otherwise); query-token paths
  (`preview`, `download`, SSE) authenticate the same way.

## Transport & headers

- CORS allowlist from `CORS_ORIGINS` (exact origins, credentials allowed).
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- Prototype preview sets `frame-ancestors 'self' <frontend origins>` (embeddable, not clickjackable elsewhere).
- Auth endpoints rate-limited (30/min/IP → `429`); envelope errors carry `request_id`, never traces.

## Secrets

- Provider keys (`OPENCODE_ZEN_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, …)
  come from env only; never logged (log redaction filter), never returned by any API,
  never stored in Postgres, never passed to generated-code subprocesses
  (`terminal.sandbox_env` strips the environment to a safe allowlist).
- `.env` is git-ignored; `.env.example` documents every variable without values.

## Untrusted-data handling

- **LLM output**: schema-validated, bounded correction retries, never trusted blindly.
- **RAG content / user requirements / tool output / generated files**: treated as data;
  system prompts forbid them from overriding instructions; prototype HTML escapes all
  spec content; generated file paths validated against traversal.
- **Generated code**: never imported by the server; tests run in a sandboxed subprocess
  (cwd jail, secret-stripped env, timeout, blocked destructive commands); downloads are
  ownership-checked and served by filename, never by raw path.

## What the Security Agent checks per project

Authentication, authorization, input validation, secret exposure (real static scan of
generated files — findings fail the stage when critical), project isolation,
sandboxed execution. Results persist in `security_checks`.
