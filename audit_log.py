"""Audit log — records every significant action for medical traceability."""

import os
from datetime import datetime
from database import get_connection


def init_audit_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            action TEXT NOT NULL,
            patient_id INTEGER,
            image_id INTEGER,
            details TEXT,
            user TEXT DEFAULT 'system'
        )
    """)
    conn.commit()
    conn.close()


def log(action, patient_id=None, image_id=None, details="", user="system"):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO audit_log (action, patient_id, image_id, details, user) "
            "VALUES (?, ?, ?, ?, ?)",
            (action, patient_id, image_id, details, user),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_recent(limit=200):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
