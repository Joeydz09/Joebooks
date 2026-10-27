/**
 * Front-end integration template for Joebooks Maktabati.
 * PREVIEW ONLY: set API_BASE after deploying and testing a dedicated Worker.
 * Do not put BOT_TOKEN or any server secret in this file.
 */
(() => {
  "use strict";

  const API_BASE = ""; // Example after approval: "https://YOUR-DEDICATED-WORKER.workers.dev"
  const tg = window.Telegram?.WebApp;

  function hasLiveConfig() {
    return Boolean(API_BASE && tg?.initData);
  }

  async function api(method, bookId) {
    if (!hasLiveConfig()) throw new Error("TELEGRAM_LIBRARY_NOT_CONFIGURED");
    const options = {
      method,
      headers: {
        "content-type": "application/json",
        "X-Telegram-Init-Data": tg.initData
      }
    };
    if (bookId !== undefined) options.body = JSON.stringify({ book_id: bookId });
    const response = await fetch(API_BASE.replace(/\/$/, "") + "/api/library", options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "LIBRARY_REQUEST_FAILED");
    return result;
  }

  async function getBookIds() {
    const result = await api("GET");
    if (!Array.isArray(result.book_ids)) throw new Error("INVALID_LIBRARY_RESPONSE");
    return result.book_ids.map(Number).filter(Number.isSafeInteger);
  }

  async function addBook(bookId) {
    return api("POST", Number(bookId));
  }

  async function removeBook(bookId) {
    return api("DELETE", Number(bookId));
  }

  // Expose only library operations, never identity or secrets.
  window.JoebooksMaktabatiAPI = Object.freeze({
    isConfigured: hasLiveConfig,
    getBookIds,
    addBook,
    removeBook
  });

  // This file deliberately does not auto-connect or change the preview UI.
  // Integration into the real book cards should happen only after API deployment
  // and testing, then must be reviewed before merging to the default branch.
})();