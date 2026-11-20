# Joebooks Admin API — read-only foundation

This Worker is intentionally read-only. It exposes only:
- `GET /api/health`
- `GET /api/books` (reads `books.json` from the configured GitHub branch)

All other paths and all non-GET methods are rejected. No write, commit, PR, merge, R2-delete, or D1 mutation endpoints exist in this stage.

## Required Worker secrets / variables

Set these in the Cloudflare Worker settings (never in frontend files or git):
- Secret `GITHUB_TOKEN`: fine-grained GitHub token restricted to `Joeydz09/Joebooks`, **Contents: Read-only** and Metadata read-only. No Contents write permission.
- Variable `GITHUB_OWNER`: `Joeydz09`
- Variable `GITHUB_REPO`: `Joebooks`
- Variable `GITHUB_BRANCH`: `main`
- Variable `CF_ACCESS_TEAM_DOMAIN`: your Cloudflare Access team domain, without `https://`
- Variable `CF_ACCESS_AUD`: the Access application's AUD tag
- Variable `ADMIN_EMAIL`: the one administrator's exact email address
- Variable `ADMIN_ORIGIN`: the dedicated admin origin, e.g. `https://admin.example.com`

## Cloudflare Access prerequisites

1. Create a dedicated admin hostname, not the public library hostname.
2. Create a Cloudflare Access self-hosted application for that hostname.
3. Set an allow policy for exactly the administrator identity; do not use broad email-domain access.
4. Configure the Worker route only after Access is active on that hostname.
5. Verify Access JWT issuer, audience, and email claim. This Worker independently validates the `Cf-Access-Jwt-Assertion` signature against the team's published JWKS, then checks issuer, audience, and exact admin email.
6. Keep the Worker endpoint private behind Access. Do not expose it on `workers.dev`.

## Safety notes

- The GitHub token is only used server-side and must be read-only.
- The Worker rejects requests without a valid Access JWT.
- The Worker checks the request Origin when present.
- Responses are private and not cacheable.
- The API returns the current configured branch's `books.json`; it does not edit GitHub.
- Do not deploy until the Access app, exact admin email, hostname, and secrets are configured and verified.
- Do not connect this API to the existing public PDF or Maktabati Workers.

## Local validation

Install dependencies, then run:
```sh
npm install
npm run typecheck
npm run dev
```

No Cloudflare resources are created by this repository scaffold.
