"""SQLite storage: sets -> practices (score /10) -> mistakes."""
import csv
import re
import sqlite3
from datetime import date, timedelta

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
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL DEFAULT '',
    meaning TEXT NOT NULL DEFAULT '',
    example TEXT NOT NULL DEFAULT '',
    synonyms TEXT NOT NULL DEFAULT '',
    mistake_id INTEGER REFERENCES mistakes(id) ON DELETE SET NULL,
    box INTEGER NOT NULL DEFAULT 0,
    due TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    reviews INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS study_log (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,          -- 'card' | 'quiz'
    ref_id INTEGER,
    result INTEGER NOT NULL,     -- card: grade 0-3, quiz: 1 correct / 0 wrong
    day TEXT NOT NULL
);
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
        "due": c.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (_today().isoformat(),)).fetchone()[0],
        "cards": c.execute("SELECT COUNT(*) FROM cards").fetchone()[0],
        "streak": streak(),
    }


# ---------- flashcards (Leitner boxes) ----------
BOX_DAYS = [0, 1, 3, 7, 14, 30, 60]
AGAIN, HARD, GOOD, EASY = range(4)


def _today():
    return date.today()


def list_cards(search=""):
    sql = "SELECT * FROM cards"
    args = []
    if search:
        sql += " WHERE word LIKE ? OR meaning LIKE ? OR synonyms LIKE ? OR example LIKE ?"
        args = [f"%{search}%"] * 4
    return _all(sql + " ORDER BY due, id", args)


def parse_card_lines(text):
    """Parse 'word:meaning' lines. Returns (pairs, problems) where problems are (line_no, reason)."""
    pairs, problems = [], []
    for n, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip().replace("：", ":")
        if not line:
            continue
        if ":" not in line:
            problems.append((n, "no colon"))
            continue
        word, meaning = (x.strip() for x in line.split(":", 1))
        if not word:
            problems.append((n, "no word before the colon"))
            continue
        pairs.append((word, meaning))
    return pairs, problems


def existing_words():
    return {r["word"].lower(): r["id"] for r in _all("SELECT id, word FROM cards")}


def import_cards(pairs, update_existing=False):
    """Add pasted cards. Existing words (case-insensitive) are skipped, or get their meaning updated.
    Returns (added, updated, skipped)."""
    have = existing_words()
    added = updated = skipped = 0
    seen = set()
    for word, meaning in pairs:
        key = word.lower()
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        if key in have:
            if update_existing and meaning:
                update_card(have[key], "meaning", meaning)
                updated += 1
            else:
                skipped += 1
        else:
            add_card(word, meaning)
            added += 1
    return added, updated, skipped


def get_card(cid):
    rows = _all("SELECT * FROM cards WHERE id=?", (cid,))
    return rows[0] if rows else None


def add_card(word, meaning="", example="", synonyms="", mistake_id=None):
    return _run("INSERT INTO cards(word, meaning, example, synonyms, mistake_id, due) VALUES(?,?,?,?,?,?)",
                (word, meaning, example, synonyms, mistake_id, _today().isoformat())).lastrowid


_CARD_FIELDS = {"word", "meaning", "example", "synonyms"}


def update_card(cid, field, value):
    if field in _CARD_FIELDS:
        _run(f"UPDATE cards SET {field}=? WHERE id=?", (value, cid))


def delete_card(cid):
    _run("DELETE FROM cards WHERE id=?", (cid,))


def due_cards():
    return _all("SELECT * FROM cards WHERE due <= ? ORDER BY box, due, id", (_today().isoformat(),))


def card_mistake_ids():
    return {r["mistake_id"] for r in _all("SELECT mistake_id FROM cards WHERE mistake_id IS NOT NULL")}


def review_card(cid, grade):
    """Move the card between Leitner boxes and schedule its next review."""
    c = get_card(cid)
    box, lapses = c["box"], c["lapses"]
    if grade == AGAIN:
        box, lapses, days = 0, lapses + 1, 0
    elif grade == HARD:
        days = 1
    else:
        box = min(len(BOX_DAYS) - 1, box + (1 if grade == GOOD else 2))
        days = BOX_DAYS[box]
    due = (_today() + timedelta(days=days)).isoformat()
    _run("UPDATE cards SET box=?, due=?, lapses=?, reviews=reviews+1 WHERE id=?", (box, due, lapses, cid))
    _log("card", cid, grade)
    return box, due


def _log(kind, ref_id, result):
    _run("INSERT INTO study_log(kind, ref_id, result, day) VALUES(?,?,?,?)",
         (kind, ref_id, int(result), _today().isoformat()))


# ---------- quiz ----------
def normalize(text):
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def is_correct(answer, expected):
    return normalize(answer) == normalize(expected) and normalize(expected) != ""


def quiz_pool(set_id=None, category="", n=None):
    """Never-quizzed mistakes first, then the most recently failed, then the rest (oldest first)."""
    sql = """SELECT m.*, s.name AS set_name, p.name AS practice_name,
                    (SELECT COUNT(*) FROM study_log l WHERE l.kind='quiz' AND l.ref_id=m.id) AS tries,
                    (SELECT l.result FROM study_log l WHERE l.kind='quiz' AND l.ref_id=m.id
                      ORDER BY l.id DESC LIMIT 1) AS last_ok,
                    (SELECT MAX(l.id) FROM study_log l WHERE l.kind='quiz' AND l.ref_id=m.id) AS last_id
             FROM mistakes m JOIN practices p ON p.id = m.practice_id JOIN sets s ON s.id = p.set_id
             WHERE m.correct != ''"""
    args = []
    if set_id:
        sql += " AND s.id = ?"
        args.append(set_id)
    if category:
        sql += " AND m.category = ?"
        args.append(category)
    rows = _all(sql, args)
    rows.sort(key=lambda r: (0, 0, r["id"]) if r["tries"] == 0
              else (1, -r["last_id"], 0) if r["last_ok"] == 0
              else (2, r["last_id"], 0))
    return rows[:n] if n else rows


def log_quiz(mid, ok):
    _log("quiz", mid, 1 if ok else 0)


# ---------- activity / streak / exam ----------
def activity_days():
    """{iso_day: {'practices': n, 'reviews': n, 'quiz': n}}"""
    out = {}
    for r in _all("SELECT date AS day, COUNT(*) n FROM practices GROUP BY date"):
        out.setdefault(r["day"], {"practices": 0, "reviews": 0, "quiz": 0})["practices"] = r["n"]
    for r in _all("SELECT day, kind, COUNT(*) n FROM study_log GROUP BY day, kind"):
        key = "reviews" if r["kind"] == "card" else "quiz"
        out.setdefault(r["day"], {"practices": 0, "reviews": 0, "quiz": 0})[key] = r["n"]
    return out


def streak(days=None):
    """Consecutive active days ending today (or yesterday, so it survives until you study today)."""
    days = set(days if days is not None else activity_days())
    d = _today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def exam():
    """Exam countdown and target progress, or None when no exam date is set."""
    raw = get_setting("exam_date")
    if not raw:
        return None
    target = int(get_setting("target_avg", "8"))
    days_left = (date.fromisoformat(raw) - _today()).days
    recent = [r["score"] for r in _all(
        "SELECT score FROM practices WHERE score IS NOT NULL ORDER BY date DESC, id DESC LIMIT 5")]
    avg = sum(recent) / len(recent) if recent else None
    return {"date": raw, "days_left": days_left, "target": target, "recent_avg": avg,
            "gap": None if avg is None else max(0.0, target - avg)}


def scores_by_day(start, end):
    """{iso_day: [{id, name, score, set_name}]} for practices dated start..end (inclusive)."""
    out = {}
    for r in _all("""SELECT p.id, p.name, p.score, p.date, s.name AS set_name FROM practices p
                     JOIN sets s ON s.id = p.set_id WHERE p.date BETWEEN ? AND ?
                     ORDER BY p.date, p.id""", (str(start), str(end))):
        out.setdefault(r["date"], []).append(r)
    return out


def day_average(items):
    scored = [i["score"] for i in items if i["score"] is not None]
    return sum(scored) / len(scored) if scored else None


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
