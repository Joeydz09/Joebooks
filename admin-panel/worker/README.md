# Joebooks Admin API — read-only foundation

This Worker is intentionally read-only. It exposes only:
- `GET /api/health`
- `GET /api/books` (reads `books.json` from the configured GitHub branch)

All other paths and all non-GET methods are rejected. No write, commit, PR, merge, R2-delete, or D1 mutation endpoints exist in this stage.

## Deployment target

The isolated Worker uses its own `workers.dev` hostname; no custom domain is required:
`https://joebooks-admin-api.<YOUR_ACCOUNT_SUBDOMAIN>.workers.dev`

The exact account subdomain is assigned by Cloudflare and must be copied from the dashboard after deployment. Do not guess or publish the URL before it is confirmed.

`workers.dev` is intended for development and hobby use rather than business-critical production. This is an early, read-only admin foundation. Keep it protected and do not use it as a public API.

## Required Worker secrets / variables

Set these in the Cloudflare Worker settings (never in frontend files or git):
- Secret `GITHUB_TOKEN`: fine-grained GitHub token restricted to `Joeydz09/Joebooks`, **Contents: Read-only** and Metadata read-only. No Contents write permission.
- Variable `GITHUB_OWNER`: `Joeydz09`
- Variable `GITHUB_REPO`: `Joebooks`
- Variable `GITHUB_BRANCH`: `main`
- Variable `CF_ACCESS_TEAM_DOMAIN`: your Cloudflare Access team domain, without `https://`
- Variable `CF_ACCESS_AUD`: the Access application's AUD tag
- Variable `ADMIN_EMAIL`: the one administrator's exact email address
- Variable `ADMIN_ORIGIN`: the exact deployed Worker origin, e.g. `https://joebooks-admin-api.<YOUR_ACCOUNT_SUBDOMAIN>.workers.dev` (no trailing slash)

## Cloudflare Access prerequisites — no custom domain required

After the first controlled deployment, immediately protect this Worker before using or sharing its URL:

1. In Cloudflare Dashboard, open **Workers & Pages** and select `joebooks-admin-api`.
2. Open the **Access** tab (or **Settings → Domains & Routes**, depending on dashboard layout).
3. Choose **Protect this Worker behind Access** / **Enable Cloudflare Access**.
4. Select **All traffic** so production and preview URLs are protected, not previews only.
5. Configure the allow policy for the single administrator email only. Do not allow an entire email domain, all account members, or everyone.
6. Save/apply the policy. Confirm the Worker's production `workers.dev` URL redirects to Access login when unauthenticated.
7. Copy the Access application's team domain and AUD tag into Worker variables. Set `ADMIN_EMAIL` to the same exact allowed email and `ADMIN_ORIGIN` to the confirmed Worker URL.
8. Verify that the administrator can authenticate and that a different email and an unauthenticated request are denied.

Cloudflare documents Worker-level Access as protecting every hostname associated with the Worker, including its `workers.dev` hostname and previews. Prefer Worker-level protection over a hostname-only rule so a second route cannot bypass the login:
https://developers.cloudflare.com/workers/configuration/cloudflare-access/

Do not rely on the frontend hiding the page. The API independently validates the `Cf-Access-Jwt-Assertion` signature against the team's published JWKS, then checks issuer, audience, and exact administrator email.

## Safety notes

- The GitHub token is only used server-side and must be read-only.
- The Worker rejects requests without a valid Access JWT.
- The Worker checks the request Origin when present.
- Responses are private and not cacheable.
- The API returns the current configured branch's `books.json`; it does not edit GitHub.
- Do not leave the Worker publicly accessible after deployment. Enable Access for all traffic before operational use.
- Do not connect this API to the existing public PDF or Maktabati Workers.
- No Cloudflare resources, secrets, Access applications, or deployments are created by this repository change.

## Local validation

Install dependencies, then run:
```sh
npm install
npm run typecheck
npm run dev
```
