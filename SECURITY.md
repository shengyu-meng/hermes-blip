# Security Policy

## Secrets

Do not commit bot tokens, API keys, OAuth tokens, cookies, `.env` files, `auth.json`, profile configs, browser profiles, or session logs.

The patch script is designed to modify only:

- Hermes source files under `gateway/`;
- the explicit `config.yaml` path passed by the user.

It should not read or print secrets.

## Reporting a vulnerability

Open a GitHub issue with a minimal reproduction. If the issue involves a real secret, redact it before posting.
