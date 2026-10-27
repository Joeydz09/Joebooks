/**
 * Joebooks "Maktabati" API — PREVIEW SOURCE ONLY.
 * Not deployed. Configure BOT_TOKEN and D1 binding DB before any deployment.
 */
const ALLOWED_ORIGIN = "https://joeydz09.github.io";
const MAX_INITDATA_AGE_SECONDS = 24 * 60 * 60;

function response(data, status = 200, origin = "") {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : "null",
      "vary": "Origin",
    },
  });
}

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function hmac(keyBytes, message) {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message)));
}
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
async function verifiedTelegramUser(initData, botToken) {
  if (!initData || !botToken) throw new Error("TELEGRAM_AUTH_REQUIRED");
  const params = new URLSearchParams(initData);
  const receivedHash = params.get("hash");
  if (!receivedHash || !/^[a-f0-9]{64}$/i.test(receivedHash)) throw new Error("INVALID_TELEGRAM_SIGNATURE");
  params.delete("hash");
  const entries = [...params.entries()].sort(([a], [b]) => a.localeCompare(b));
  const checkString = entries.map(([k, v]) => `${k}=${v}`).join("\n");
  const secretKey = await hmac(new TextEncoder().encode(botToken), "WebAppData");
  const expectedHash = hex(await hmac(secretKey, checkString));
  if (!safeEqual(expectedHash, receivedHash.toLowerCase())) throw new Error("INVALID_TELEGRAM_SIGNATURE");
  const authDate = Number(params.get("auth_date"));
  const now = Math.floor(Date.now() / 1000);
  if (!Number.isFinite(authDate) || authDate > now + 60 || now - authDate > MAX_INITDATA_AGE_SECONDS) {
    throw new Error("TELEGRAM_AUTH_EXPIRED");
  }
  let user;
  try { user = JSON.parse(params.get("user") || ""); } catch { throw new Error("INVALID_TELEGRAM_USER"); }
  if (!user || !Number.isSafeInteger(user.id) || user.id <= 0) throw new Error("INVALID_TELEGRAM_USER");
  return String(user.id);
}
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (origin !== ALLOWED_ORIGIN) return response({ error: "ORIGIN_NOT_ALLOWED" }, 403, origin);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: {
        "access-control-allow-origin": ALLOWED_ORIGIN,
        "access-control-allow-methods": "GET, POST, DELETE, OPTIONS",
        "access-control-allow-headers": "content-type, x-telegram-init-data",
        "access-control-max-age": "600",
        "vary": "Origin",
      }});
    }
    if (!env.DB || !env.BOT_TOKEN) return response({ error: "SERVER_NOT_CONFIGURED" }, 503, origin);
    const url = new URL(request.url);
    if (url.pathname !== "/api/library") return response({ error: "NOT_FOUND" }, 404, origin);
    let userId;
    try {
      userId = await verifiedTelegramUser(request.headers.get("X-Telegram-Init-Data"), env.BOT_TOKEN);
    } catch (error) {
      const code = error instanceof Error ? error.message : "TELEGRAM_AUTH_FAILED";
      return response({ error: code }, 401, origin);
    }
    try {
      if (request.method === "GET") {
        const rows = await env.DB.prepare(
          "SELECT book_id FROM user_library WHERE telegram_user_id = ? ORDER BY created_at DESC"
        ).bind(userId).all();
        return response({ book_ids: (rows.results || []).map((r) => Number(r.book_id)) }, 200, origin);
      }
      if (request.method === "POST") {
        let body;
        try { body = await request.json(); } catch { return response({ error: "INVALID_JSON" }, 400, origin); }
        const bookId = Number(body?.book_id);
        if (!Number.isSafeInteger(bookId) || bookId <= 0) return response({ error: "INVALID_BOOK_ID" }, 400, origin);
        await env.DB.prepare(
          "INSERT INTO user_library (telegram_user_id, book_id) VALUES (?, ?) ON CONFLICT(telegram_user_id, book_id) DO NOTHING"
        ).bind(userId, bookId).run();
        return response({ ok: true }, 200, origin);
      }
      if (request.method === "DELETE") {
        let body;
        try { body = await request.json(); } catch { return response({ error: "INVALID_JSON" }, 400, origin); }
        const bookId = Number(body?.book_id);
        if (!Number.isSafeInteger(bookId) || bookId <= 0) return response({ error: "INVALID_BOOK_ID" }, 400, origin);
        await env.DB.prepare(
          "DELETE FROM user_library WHERE telegram_user_id = ? AND book_id = ?"
        ).bind(userId, bookId).run();
        return response({ ok: true }, 200, origin);
      }
      return response({ error: "METHOD_NOT_ALLOWED" }, 405, origin);
    } catch {
      return response({ error: "DATABASE_ERROR" }, 500, origin);
    }
  }
};