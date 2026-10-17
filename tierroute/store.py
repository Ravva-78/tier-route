"""SQLite decision log: one row per sub-task, so every routing decision is inspectable."""
import json
import sqlite3
import threading
import time

COLS = ["request_id", "ts", "part_idx", "part_text", "task_type", "score", "strategy", "first_model",
        "final_model", "tier", "reason", "tokens_in", "tokens_out", "cost", "est_strong_cost",
        "latency_s", "escalated", "verified", "override_by", "attempts"]


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        with self._conn() as c:
            c.execute(f"CREATE TABLE IF NOT EXISTS decisions ({', '.join(COLS)})")

    def _conn(self):
        return sqlite3.connect(self.path)

    def log(self, rows):
        with self.lock, self._conn() as c:
            for r in rows:
                vals = [json.dumps(r[k]) if k == "attempts" else r[k] for k in COLS]
                c.execute(f"INSERT INTO decisions VALUES ({','.join('?' * len(COLS))})", vals)

    def recent(self, limit=50):
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("SELECT rowid AS id, * FROM decisions ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["attempts"] = json.loads(d["attempts"] or "[]")
            out.append(d)
        return out

    def stats(self):
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            t = c.execute("SELECT COUNT(DISTINCT request_id) AS requests, COUNT(*) AS parts, "
                          "COALESCE(SUM(cost),0) AS cost, COALESCE(SUM(est_strong_cost),0) AS strong, "
                          "COALESCE(SUM(escalated),0) AS escalations, COALESCE(SUM(override_by IS NOT NULL),0) AS overrides "
                          "FROM decisions").fetchone()
            by_model = c.execute("SELECT final_model AS model, COUNT(*) AS n, SUM(cost) AS cost "
                                 "FROM decisions GROUP BY final_model").fetchall()
        d = dict(t)
        d["savings_pct"] = round(100 * (1 - d["cost"] / d["strong"]), 1) if d["strong"] > 0 else 0.0
        d["by_model"] = [dict(r) for r in by_model]
        return d

    def clear(self):
        with self.lock, self._conn() as c:
            c.execute("DELETE FROM decisions")
