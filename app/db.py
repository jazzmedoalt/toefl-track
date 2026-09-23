"""SQLite storage: sets -> practices (score /10) -> mistakes."""
import csv
import sqlite3
from datetime import date

from .paths import DB_PATH

DEFAULT_CATEGORIES = [
    "Vocabulary", "Grammar", "Reading", "Listening", "Speaking", "Writing",
    "Inference", "Main Idea", "Detail", "Spelling",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS practices (
    id INTEGER PRIMARY KEY,
    set_id INTEGER NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    score INTEGER,
    date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    wrong TEXT NOT NULL DEFAULT '',
    correct TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

_conn = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def _run(sql, args=()):
    c = conn()
    cur = c.execute(sql, args)
    c.commit()
    return cur


def _all(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args).fetchall()]


# ---------- settings ----------
def get_setting(key, default=None):
    row = conn().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    _run("INSERT INTO settings(key, value) VALUES(?, ?) "
         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


# ---------- sets ----------
def list_sets():
    return _all("""
        SELECT s.id, s.name,
               COUNT(p.id) AS practices,
               AVG(p.score) AS avg,
               (SELECT COUNT(*) FROM mistakes m JOIN practices p2 ON p2.id = m.practice_id
                 WHERE p2.set_id = s.id) AS mistakes
        FROM sets s LEFT JOIN practices p ON p.set_id = s.id
        GROUP BY s.id ORDER BY s.id""")


def get_set(set_id):
    rows = _all("SELECT * FROM sets WHERE id=?", (set_id,))
    return rows[0] if rows else None


def add_set(name):
    return _run("INSERT INTO sets(name) VALUES(?)", (name,)).lastrowid


def rename_set(set_id, name):
    _run("UPDATE sets SET name=? WHERE id=?", (name, set_id))


def delete_set(set_id):
    _run("DELETE FROM sets WHERE id=?", (set_id,))


def set_scores(set_id):
    return [r["score"] for r in _all(
        "SELECT score FROM practices WHERE set_id=? AND score IS NOT NULL ORDER BY date, id", (set_id,))]


# ---------- practices ----------
def list_practices(set_id):
    return _all("""
        SELECT p.*, (SELECT COUNT(*) FROM mistakes m WHERE m.practice_id = p.id) AS mistakes
        FROM practices p WHERE p.set_id=? ORDER BY p.date, p.id""", (set_id,))


def get_practice(pid):
    rows = _all("""SELECT p.*, s.name AS set_name FROM practices p
                   JOIN sets s ON s.id = p.set_id WHERE p.id=?""", (pid,))
    return rows[0] if rows else None


def add_practice(set_id):
    n = conn().execute("SELECT COUNT(*) FROM practices WHERE set_id=?", (set_id,)).fetchone()[0]
    return _run("INSERT INTO practices(set_id, name, score, date) VALUES(?, ?, NULL, ?)",
                (set_id, f"Practice {n + 1}", date.today().isoformat())).lastrowid


_PRACTICE_FIELDS = {"name", "score", "date", "notes"}


def update_practice(pid, **fields):
    fields = {k: v for k, v in fields.items() if k in _PRACTICE_FIELDS}
    if fields:
        cols = ", ".join(f"{k}=?" for k in fields)
        _run(f"UPDATE practices SET {cols} WHERE id=?", (*fields.values(), pid))


def delete_practice(pid):
    _run("DELETE FROM practices WHERE id=?", (pid,))


# ---------- mistakes ----------
def list_mistakes(pid):
    return _all("SELECT * FROM mistakes WHERE practice_id=? ORDER BY id", (pid,))


def add_mistake(pid, wrong, correct, category, topic):
    return _run("INSERT INTO mistakes(practice_id, wrong, correct, category, topic) VALUES(?,?,?,?,?)",
                (pid, wrong, correct, category, topic)).lastrowid


_MISTAKE_FIELDS = {"wrong", "correct", "category", "topic"}


def update_mistake(mid, field, value):
    if field in _MISTAKE_FIELDS:
        _run(f"UPDATE mistakes SET {field}=? WHERE id=?", (value, mid))


def delete_mistake(mid):
    _run("DELETE FROM mistakes WHERE id=?", (mid,))


def all_mistakes(search="", category="", set_id=None):
    sql = """SELECT m.*, p.name AS practice_name, p.id AS practice_id, s.name AS set_name, s.id AS set_id
             FROM mistakes m JOIN practices p ON p.id = m.practice_id JOIN sets s ON s.id = p.set_id
             WHERE 1=1"""
    args = []
    if search:
        sql += " AND (m.wrong LIKE ? OR m.correct LIKE ? OR m.topic LIKE ? OR m.category LIKE ?)"
        args += [f"%{search}%"] * 4
    if category:
        sql += " AND m.category = ?"
        args.append(category)
    if set_id:
        sql += " AND s.id = ?"
        args.append(set_id)
    return _all(sql + " ORDER BY m.id DESC", args)


def categories():
    used = [r["category"] for r in _all(
        "SELECT category, COUNT(*) c FROM mistakes WHERE category != '' GROUP BY category ORDER BY c DESC")]
    return used + [c for c in DEFAULT_CATEGORIES if c not in used]


def used_categories():
    return [r["category"] for r in _all(
        "SELECT DISTINCT category FROM mistakes WHERE category != '' ORDER BY category")]


# ---------- dashboard ----------
def stats():
    c = conn()
    row = c.execute("""SELECT COUNT(*) n, AVG(score) avg, MAX(score) best
                       FROM practices WHERE score IS NOT NULL""").fetchone()
    series = _all("""SELECT p.score, p.name, p.date, s.name AS set_name FROM practices p
                     JOIN sets s ON s.id = p.set_id WHERE p.score IS NOT NULL
                     ORDER BY p.date, p.id""")
    top = _all("""SELECT CASE WHEN category='' THEN 'Uncategorized' ELSE category END AS category,
                         COUNT(*) AS n FROM mistakes GROUP BY 1 ORDER BY n DESC LIMIT 6""")
    recent = _all("""SELECT p.id, p.name, p.score, p.date, s.name AS set_name,
                            (SELECT COUNT(*) FROM mistakes m WHERE m.practice_id = p.id) AS mistakes
                     FROM practices p JOIN sets s ON s.id = p.set_id
                     ORDER BY p.date DESC, p.id DESC LIMIT 5""")
    return {
        "practices": row["n"],
        "avg": row["avg"],
        "best": row["best"],
        "mistakes": c.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0],
        "sets": c.execute("SELECT COUNT(*) FROM sets").fetchone()[0],
        "series": series,
        "top": top,
        "recent": recent,
    }


def export_csv(path):
    rows = _all("""SELECT s.name AS "set", p.name AS practice, p.date, p.score,
                          m.wrong, m.correct, m.category AS type, m.topic
                   FROM practices p JOIN sets s ON s.id = p.set_id
                   LEFT JOIN mistakes m ON m.practice_id = p.id
                   ORDER BY s.id, p.date, p.id, m.id""")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["set", "practice", "date", "score", "wrong", "correct", "type", "topic"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)
