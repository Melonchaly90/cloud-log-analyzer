"""
Database Manager
Supports:
  - Neon DB (PostgreSQL) when DATABASE_URL is set   ← production
  - SQLite fallback                                  ← local dev
"""

import os
import json
import uuid
import sqlite3
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ─── helpers ──────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ─── DatabaseManager ──────────────────────────────────────────────

class DatabaseManager:
    """
    Thin ORM-free layer that works with either Postgres or SQLite.
    All secrets (DATABASE_URL) are read exclusively from environment variables —
    never hard-coded in source.
    """

    def __init__(self):
        self._use_postgres = bool(DATABASE_URL and PSYCOPG2_AVAILABLE)
        if self._use_postgres:
            self._pg_conn = None   # lazy connection
            self._ensure_pg_schema()
        else:
            self._sqlite_path = os.environ.get("SQLITE_PATH", "log_analyzer.db")
            self._init_sqlite()

    # ── Connection helpers ────────────────────────────────────────

    def _pg(self):
        if self._pg_conn is None or self._pg_conn.closed:
            self._pg_conn = psycopg2.connect(DATABASE_URL)
            self._pg_conn.autocommit = False
        return self._pg_conn

    def _init_sqlite(self):
        con = sqlite3.connect(self._sqlite_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.executescript(SCHEMA_SQL)
        con.commit()
        con.close()

    def _get_sqlite(self):
        con = sqlite3.connect(self._sqlite_path)
        con.row_factory = sqlite3.Row
        return con

    # ── Schema bootstrap (Postgres) ───────────────────────────────

    def _ensure_pg_schema(self):
        con = self._pg()
        cur = con.cursor()
        cur.execute(SCHEMA_SQL_PG)
        con.commit()

    # ── User operations ───────────────────────────────────────────

    def user_count(self) -> int:
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM users;")
            return cur.fetchone()[0]
        else:
            con = self._get_sqlite()
            row = con.execute("SELECT COUNT(*) FROM users;").fetchone()
            con.close()
            return row[0]

    def create_user(self, user_id, username, pw_salt, pw_hash, is_admin):
        sql = (
            "INSERT INTO users (id, username, pw_salt, pw_hash, is_admin, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)" if self._use_postgres else
            "INSERT INTO users (id, username, pw_salt, pw_hash, is_admin, created_at) "
            "VALUES (?,?,?,?,?,?)"
        )
        params = (user_id, username, pw_salt, pw_hash, 1 if is_admin else 0, _now())
        if self._use_postgres:
            con = self._pg()
            con.cursor().execute(sql, params)
            con.commit()
        else:
            con = self._get_sqlite()
            con.execute(sql, params)
            con.commit()
            con.close()

    def get_user_by_username(self, username: str) -> dict | None:
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE username=%s;", (username,))
            row = cur.fetchone()
            return dict(row) if row else None
        else:
            con = self._get_sqlite()
            row = con.execute("SELECT * FROM users WHERE username=?;", (username,)).fetchone()
            con.close()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE id=%s;", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        else:
            con = self._get_sqlite()
            row = con.execute("SELECT * FROM users WHERE id=?;", (user_id,)).fetchone()
            con.close()
            return dict(row) if row else None

    # ── Analysis operations ───────────────────────────────────────

    def save_analysis(self, user_id: str, filename: str, results: dict) -> str:
        analysis_id = uuid.uuid4().hex
        results_json = json.dumps(results)
        sql = (
            "INSERT INTO analyses (id, user_id, filename, results_json, created_at) "
            "VALUES (%s,%s,%s,%s,%s)" if self._use_postgres else
            "INSERT INTO analyses (id, user_id, filename, results_json, created_at) "
            "VALUES (?,?,?,?,?)"
        )
        params = (analysis_id, user_id, filename, results_json, _now())
        if self._use_postgres:
            con = self._pg()
            con.cursor().execute(sql, params)
            con.commit()
        else:
            con = self._get_sqlite()
            con.execute(sql, params)
            con.commit()
            con.close()
        return analysis_id

    def get_analysis(self, analysis_id: str) -> dict | None:
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM analyses WHERE id=%s;", (analysis_id,))
            row = cur.fetchone()
        else:
            con = self._get_sqlite()
            row = con.execute("SELECT * FROM analyses WHERE id=?;", (analysis_id,)).fetchone()
            con.close()
        if not row:
            return None
        data = dict(row)
        data["results"] = json.loads(data.pop("results_json", "{}"))
        return data

    def get_recent_analyses(self, limit: int = 10) -> list[dict]:
        sql = (
            "SELECT a.*, u.username FROM analyses a "
            "JOIN users u ON a.user_id=u.id "
            "ORDER BY a.created_at DESC LIMIT %s" if self._use_postgres else
            "SELECT a.*, u.username FROM analyses a "
            "JOIN users u ON a.user_id=u.id "
            "ORDER BY a.created_at DESC LIMIT ?"
        )
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
        else:
            con = self._get_sqlite()
            rows = con.execute(sql, (limit,)).fetchall()
            con.close()
        return [dict(r) for r in rows]

    def get_all_analyses(self) -> list[dict]:
        return self.get_recent_analyses(limit=500)

    # ── Audit log operations ──────────────────────────────────────

    def log_audit(self, user_id: str, action: str, detail: str):
        sql = (
            "INSERT INTO audit_log (id, user_id, action, detail, created_at) "
            "VALUES (%s,%s,%s,%s,%s)" if self._use_postgres else
            "INSERT INTO audit_log (id, user_id, action, detail, created_at) "
            "VALUES (?,?,?,?,?)"
        )
        params = (uuid.uuid4().hex, user_id, action, detail, _now())
        if self._use_postgres:
            con = self._pg()
            con.cursor().execute(sql, params)
            con.commit()
        else:
            con = self._get_sqlite()
            con.execute(sql, params)
            con.commit()
            con.close()

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        sql = (
            "SELECT al.*, u.username FROM audit_log al "
            "JOIN users u ON al.user_id=u.id "
            "ORDER BY al.created_at DESC LIMIT %s" if self._use_postgres else
            "SELECT al.*, u.username FROM audit_log al "
            "JOIN users u ON al.user_id=u.id "
            "ORDER BY al.created_at DESC LIMIT ?"
        )
        if self._use_postgres:
            con = self._pg()
            cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
        else:
            con = self._get_sqlite()
            rows = con.execute(sql, (limit,)).fetchall()
            con.close()
        return [dict(r) for r in rows]


# ─── Schemas ──────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    pw_salt     TEXT NOT NULL,
    pw_hash     TEXT NOT NULL,
    is_admin    INTEGER DEFAULT 0,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    filename     TEXT NOT NULL,
    results_json TEXT,
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    action     TEXT NOT NULL,
    detail     TEXT,
    created_at TEXT
);
"""

SCHEMA_SQL_PG = """
CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(64) PRIMARY KEY,
    username    VARCHAR(128) UNIQUE NOT NULL,
    pw_salt     VARCHAR(64) NOT NULL,
    pw_hash     VARCHAR(128) NOT NULL,
    is_admin    SMALLINT DEFAULT 0,
    created_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    id           VARCHAR(64) PRIMARY KEY,
    user_id      VARCHAR(64) NOT NULL,
    filename     VARCHAR(256) NOT NULL,
    results_json TEXT,
    created_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         VARCHAR(64) PRIMARY KEY,
    user_id    VARCHAR(64) NOT NULL,
    action     VARCHAR(64) NOT NULL,
    detail     TEXT,
    created_at TIMESTAMP
);
"""
