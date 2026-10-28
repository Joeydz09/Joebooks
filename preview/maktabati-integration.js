/**
 * Front-end integration for Joebooks Maktabati.
 * Preview branch only. Never place BOT_TOKEN or server secrets here.
 */
(() => {
  "use strict";

  const API_BASE = "https://joebooks-maktabati.jo-dz-jd.workers.dev";
  const tg = window.Telegram?.WebApp;

  function getInitData() {
    const direct = typeof tg?.initData === "string" ? tg.initData.trim() : "";
    if (direct) return direct;

    try {
      const saved = window.sessionStorage?.getItem("maktabat_telegram_init_data");
      return typeof saved === "string" ? saved.trim() : "";
    } catch {
      return "";
    }
  }

  function hasLiveConfig() {
    return Boolean(API_BASE && getInitData());
  }

  async function api(method, bookId) {
    const initData = getInitData();
    if (!API_BASE || !initData) throw new Error("OPEN_IN_TELEGRAM_MINI_APP");
    const options = {
      method,
      headers: {
        "content-type": "application/json",
        "X-Telegram-Init-Data": initData
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
