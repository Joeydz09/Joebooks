-- Dedicated table for Joebooks Maktabati. Apply only to a NEW dedicated D1 database.
CREATE TABLE IF NOT EXISTS user_library (
  telegram_user_id TEXT NOT NULL,
  book_id INTEGER NOT NULL CHECK (book_id > 0),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY (telegram_user_id, book_id)
);
CREATE INDEX IF NOT EXISTS idx_user_library_user_created
  ON user_library (telegram_user_id, created_at DESC);