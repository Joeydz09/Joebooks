/**
 * Front-end integration for Joebooks Maktabati.
 * Preview branch only. Never place BOT_TOKEN or server secrets here.
 */
(() => {
  "use strict";

  const API_BASE = "https://joebooks-maktabati.jo-dz-jd.workers.dev";
  const tg = window.Telegram?.WebApp;

  function hasLiveConfig() {
    return Boolean(API_BASE && tg?.initData);
  }

  async function api(method, bookId) {
    if (!hasLiveConfig()) throw new Error("OPEN_IN_TELEGRAM_MINI_APP");
    const options = {
      method,
      headers: {
        "content-type": "application/json",
        "X-Telegram-Init-Data": tg.initData
      }
    };
    if (bookId !== undefined) options.body = JSON.stringify({ book_id: Number(bookId) });
    const response = await fetch(API_BASE.replace(/\/$/, "") + "/api/library", options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "LIBRARY_REQUEST_FAILED");
    return result;
  }

  async function getBookIds() {
    const result = await api("GET");
    if (!Array.isArray(result.book_ids)) throw new Error("INVALID_LIBRARY_RESPONSE");
    return result.book_ids.map(Number).filter((id) => Number.isSafeInteger(id) && id > 0);
  }

  async function addBook(bookId) {
    const id = Number(bookId);
    if (!Number.isSafeInteger(id) || id <= 0) throw new Error("INVALID_BOOK_ID");
    return api("POST", id);
  }

  async function removeBook(bookId) {
    const id = Number(bookId);
    if (!Number.isSafeInteger(id) || id <= 0) throw new Error("INVALID_BOOK_ID");
    return api("DELETE", id);
  }

  window.JoebooksMaktabatiAPI = Object.freeze({
    isConfigured: hasLiveConfig,
    getBookIds,
    addBook,
    removeBook
  });
})();
