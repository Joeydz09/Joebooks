import { createRemoteJWKSet, jwtVerify } from "jose";

interface Env {
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  CF_ACCESS_TEAM_DOMAIN: string;
  CF_ACCESS_AUD: string;
  ADMIN_EMAIL: string;
  ADMIN_ORIGIN: string;
}

const MAX_BOOKS_BYTES = 4 * 1024 * 1024;
const encoder = new TextEncoder();

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, private",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
      "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    },
  });
}

function required(env: Env): string[] {
  return [
    env.GITHUB_TOKEN,
    env.GITHUB_OWNER,
    env.GITHUB_REPO,
    env.GITHUB_BRANCH,
    env.CF_ACCESS_TEAM_DOMAIN,
    env.CF_ACCESS_AUD,
    env.ADMIN_EMAIL,
    env.ADMIN_ORIGIN,
  ];
}

async function requireAdmin(request: Request, env: Env): Promise<boolean> {
  if (required(env).some((value) => !value)) return false;

  const origin = request.headers.get("Origin");
  if (origin && origin !== env.ADMIN_ORIGIN) return false;

  const assertion = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!assertion) return false;

  const issuer = `https://${env.CF_ACCESS_TEAM_DOMAIN}`;
  const jwks = createRemoteJWKSet(
    new URL(`${issuer}/cdn-cgi/access/certs`),
  );

  try {
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

    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, 405);
    }

    if (!url.pathname.startsWith("/api/")) {
      return json({ error: "not_found" }, 404);
    }

    if (!(await requireAdmin(request, env))) {
      return json({ error: "unauthorized" }, 401);
    }

    if (url.pathname === "/api/health") {
      return json({
        ok: true,
        mode: "read-only",
        repository: `${env.GITHUB_OWNER}/${env.GITHUB_REPO}`,
        branch: env.GITHUB_BRANCH,
      });
    }

    if (url.pathname === "/api/books") {
      const githubUrl = new URL(
        `https://api.github.com/repos/${encodeURIComponent(env.GITHUB_OWNER)}/${encodeURIComponent(env.GITHUB_REPO)}/contents/books.json`,
      );
      githubUrl.searchParams.set("ref", env.GITHUB_BRANCH);

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
        return json({ error: "github_read_failed", status: upstream.status }, 502);
      }

      const body = await upstream.text();
      if (encoder.encode(body).byteLength > MAX_BOOKS_BYTES) {
        return json({ error: "books_file_too_large" }, 413);
      }

      try {
        const parsed: unknown = JSON.parse(body);
        if (!Array.isArray(parsed)) {
          return json({ error: "unexpected_books_format" }, 502);
        }
        return json({
          source: "github",
          repository: `${env.GITHUB_OWNER}/${env.GITHUB_REPO}`,
          branch: env.GITHUB_BRANCH,
          count: parsed.length,
          books: parsed,
        });
      } catch {
        return json({ error: "invalid_books_json" }, 502);
      }
    }

    return json({ error: "not_found" }, 404);
  },
};
