import { createRemoteJWKSet, jwtVerify } from "jose";

interface Env {
  GITHUB_TOKEN?: string;
  GITHUB_OWNER?: string;
  GITHUB_REPO?: string;
  GITHUB_BRANCH?: string;
  CF_ACCESS_TEAM_DOMAIN: string;
  CF_ACCESS_AUD: string;
  ADMIN_EMAIL: string;
  // Exact origin of the admin frontend (scheme + host + optional port), no path or trailing slash.
  ADMIN_ORIGIN: string;
}

const MAX_BOOKS_BYTES = 4 * 1024 * 1024;
const encoder = new TextEncoder();

function json(
  data: unknown,
  status = 200,
  origin?: string | null,
  env?: Env,
): Response {
  const headers = new Headers({
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store, private",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "vary": "Origin",
  });

  if (origin && env?.ADMIN_ORIGIN && origin === env.ADMIN_ORIGIN) {
    headers.set("access-control-allow-origin", origin);
    headers.set("access-control-allow-credentials", "true");
    headers.set("access-control-allow-methods", "GET, OPTIONS");
    headers.set("access-control-allow-headers", "Accept, Content-Type");
  }

  return new Response(JSON.stringify(data), { status, headers });
}

function accessConfigIsPresent(env: Env): boolean {
  return Boolean(
    env.CF_ACCESS_TEAM_DOMAIN &&
    env.CF_ACCESS_AUD &&
    env.ADMIN_EMAIL &&
    env.ADMIN_ORIGIN
  );
}

async function requireAdmin(request: Request, env: Env): Promise<boolean> {
  if (!accessConfigIsPresent(env)) return false;

  const assertion = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!assertion) return false;

  const issuer = `https://${env.CF_ACCESS_TEAM_DOMAIN}`;

  try {
    const jwks = createRemoteJWKSet(
      new URL(`${issuer}/cdn-cgi/access/certs`),
    );
    const { payload } = await jwtVerify(assertion, jwks, {
      issuer,
      audience: env.CF_ACCESS_AUD,
    });

    return typeof payload.email === "string" &&
      payload.email.toLowerCase() === env.ADMIN_EMAIL.toLowerCase();
  } catch {
    return false;
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin");

    // Browser origins are restricted to the one explicitly configured frontend.
    if (origin && (!env.ADMIN_ORIGIN || origin !== env.ADMIN_ORIGIN)) {
      return json({ error: "origin_not_allowed" }, 403);
    }

    // CORS preflight carries no application data, so it is answered before JWT
    // validation. It is accepted only from the exact configured frontend origin.
    if (request.method === "OPTIONS") {
      if (!origin || !env.ADMIN_ORIGIN || origin !== env.ADMIN_ORIGIN) {
        return json({ error: "origin_not_allowed" }, 403);
      }
      const requestedMethod = request.headers.get("Access-Control-Request-Method");
      if (requestedMethod && requestedMethod !== "GET") {
        return json({ error: "method_not_allowed" }, 405, origin, env);
      }
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": origin,
          "access-control-allow-credentials": "true",
          "access-control-allow-methods": "GET, OPTIONS",
          "access-control-allow-headers": "Accept, Content-Type",
          "access-control-max-age": "600",
          "vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
          "cache-control": "no-store",
        },
      });
    }

    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, 405, origin, env);
    }

    if (url.pathname !== "/api/health" && url.pathname !== "/api/books") {
      return json({ error: "not_found" }, 404, origin, env);
    }

    // Both endpoints require a valid Cloudflare Access JWT and the exact
    // administrator email. GitHub credentials are deliberately not required here.
    if (!(await requireAdmin(request, env))) {
      return json({ error: "unauthorized" }, 401, origin, env);
    }

    if (url.pathname === "/api/health") {
      return json({ ok: true, mode: "read-only" }, 200, origin, env);
    }

    // GitHub credentials are needed only for the books endpoint.
    if (!env.GITHUB_TOKEN || !env.GITHUB_OWNER || !env.GITHUB_REPO || !env.GITHUB_BRANCH) {
      return json({ error: "github_read_not_configured" }, 503, origin, env);
    }

    const githubUrl = new URL(
      `https://api.github.com/repos/${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}/contents/books.json`,
    );
    githubUrl.searchParams.set("ref", env.GITHUB_BRANCH);

    try {
      const upstream = await fetch(githubUrl, {
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github.raw+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "Joebooks-Admin-ReadOnly",
        },
        cf: { cacheTtl: 0, cacheEverything: false },
      });

      if (!upstream.ok) {
        return json({ error: "github_read_failed" }, 502, origin, env);
      }

      const contentLength = Number(upstream.headers.get("content-length") || 0);
      if (contentLength > MAX_BOOKS_BYTES) {
        return json({ error: "books_file_too_large" }, 413, origin, env);
      }

      const body = await upstream.text();
      if (encoder.encode(body).byteLength > MAX_BOOKS_BYTES) {
        return json({ error: "books_file_too_large" }, 413, origin, env);
      }

      let parsed: unknown;
      try {
        parsed = JSON.parse(body);
      } catch {
        return json({ error: "invalid_books_json" }, 502, origin, env);
      }

      if (!Array.isArray(parsed)) {
        return json({ error: "unexpected_books_format" }, 502, origin, env);
      }

      return json({
        source: "github",
        repository: `${env.GITHUB_OWNER}/${env.GITHUB_REPO}`,
        branch: env.GITHUB_BRANCH,
        count: parsed.length,
        books: parsed,
      }, 200, origin, env);
    } catch {
      return json({ error: "github_read_failed" }, 502, origin, env);
    }
  },
};
