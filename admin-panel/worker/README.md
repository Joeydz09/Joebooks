# Joebooks Admin API — read-only foundation

This Worker is intentionally read-only. It exposes only:
- `GET /api/health` — checks the protected API without requiring a GitHub token.
- `GET /api/books` — reads `books.json` from the configured GitHub branch and requires a server-side GitHub token.
- `GET /api/daily` — reads and validates `daily-content.json` (30 quotes, days 1–30, `Africa/Algiers`) from the configured GitHub branch; requires the same Cloudflare Access administrator authentication and GitHub read secret.

All other paths and all non-GET methods are rejected. CORS preflight (`OPTIONS`) is answered only for the one exact configured frontend origin; it exposes no application data and does not bypass authentication for GET requests. No write, commit, PR, merge, R2-delete, or D1 mutation endpoints exist in this stage.

## Deployment target

The isolated Worker uses its own `workers.dev` hostname; no custom domain is required:
`https://joebooks-admin-api.<YOUR_ACCOUNT_SUBDOMAIN>.workers.dev`

The exact account subdomain is assigned by Cloudflare and must be copied from the dashboard after deployment. Do not guess or publish the URL before it is confirmed.

`workers.dev` is intended for development and hobby use rather than business-critical production. This is an early, read-only admin foundation. Keep it protected and do not use it as a public API.

## Required Worker variables and secrets

Set these in the Cloudflare Worker settings (never in frontend files or git):
- Secret `GITHUB_TOKEN`: fine-grained GitHub token restricted to `Joeydz09/Joebooks`, **Contents: Read-only** and Metadata read-only. No Contents write permission. This is required only by `/api/books`, not by `/api/health`.
- Variable `GITHUB_OWNER`: `Joeydz09`
- Variable `GITHUB_REPO`: `Joebooks`
- Variable `GITHUB_BRANCH`: `main`
- Variable `CF_ACCESS_TEAM_DOMAIN`: your Cloudflare Access team domain, without `https://`
- Variable `CF_ACCESS_AUD`: the Access application's AUD tag
- Variable `ADMIN_EMAIL`: the one administrator's exact email address
- Variable `ADMIN_ORIGIN`: the exact **admin frontend origin** (scheme + host + optional port; no path and no trailing slash). This is not necessarily the API Worker's origin. Set it only after the frontend hosting origin is chosen.

The health endpoint needs only the Cloudflare Access variables. The books endpoint additionally needs the GitHub repository variables and `GITHUB_TOKEN`.

## Cloudflare Access prerequisites — no custom domain required

Protect this Worker before using or sharing its URL:

1. In Cloudflare Dashboard, open **Workers & Pages** and select `joebooks-admin-api`.
2. Open the Access settings for this Worker.
3. Select **All traffic** so production and preview URLs are protected, not previews only.
4. Configure the allow policy for the single administrator email only. Do not allow an entire email domain, all account members, or everyone.
5. Save/apply the policy. Confirm the Worker's production `workers.dev` URL redirects to Access login when unauthenticated.
6. Copy the Access application's team domain and AUD tag into Worker variables. Set `ADMIN_EMAIL` to the same exact allowed email.
7. Verify that the administrator can authenticate and that a different email and an unauthenticated request are denied.

Cloudflare documents Worker-level Access as protecting every hostname associated with the Worker, including its `workers.dev` hostname and previews. Prefer Worker-level protection over a hostname-only rule so a second route cannot bypass the login:
https://developers.cloudflare.com/workers/configuration/cloudflare-access/

Do not rely on the frontend hiding the page. The API independently validates the `Cf-Access-Jwt-Assertion` signature against the team's published JWKS, then checks issuer, audience, and exact administrator email.

## CORS and request-origin protection

- Browser requests that include an `Origin` are accepted only when it exactly matches `ADMIN_ORIGIN`.
- The Worker returns CORS headers only for that exact origin; it never uses a wildcard.
- Preflight accepts only `GET` and only from that exact configured origin.
- Requests without an `Origin` can still be used for command-line diagnostics, but they must pass Cloudflare Access JWT validation.
- The browser frontend's final origin has not yet been selected. Do not assume the current Worker URL is the frontend origin; update `ADMIN_ORIGIN` when the frontend hosting location is decided.

## Safety notes

- The GitHub token is only used server-side and must be read-only.
- Both API endpoints reject requests without a valid Access JWT and the exact administrator email.
- The books endpoint returns the configured branch's `books.json`; it does not edit GitHub.
- Responses are private and not cacheable.
- Do not leave the Worker publicly accessible. Enable Access for all traffic before operational use.
- Do not connect this API to the existing public PDF or Maktabati Workers.
- No Cloudflare resources, secrets, Access applications, or deployments are created by this repository change.

## Local validation

Install dependencies, then run:
```sh
npm install
npm run typecheck
npm run dev
```
