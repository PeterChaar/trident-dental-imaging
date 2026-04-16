"""Patient database — SQLite. Images table stores both original and processed paths;
original file is never modified (immutable audit trail for medical use)."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "dental_clinic.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth TEXT,
            phone TEXT,
            email TEXT,
            gender TEXT,
            medical_history TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            original_path TEXT,
            image_type TEXT DEFAULT 'periapical',
            tooth_number TEXT,
            notes TEXT,
            kv INTEGER,
            ma REAL,
            exposure_time REAL,
            captured_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS image_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            annotation_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tooth_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            tooth_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'healthy',
            surfaces TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (patient_id, tooth_number),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            tooth_number INTEGER,
            treatment_date TEXT NOT NULL DEFAULT (date('now')),
            procedure TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        );
    """)
    _migrate(conn)
    conn.commit()
    conn.close()


def _migrate(conn):
    """Idempotent column adds for DBs created by older schema versions."""
    def cols(table):
        return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}

    patient_cols = cols("patients")
    for col, ddl in [
        ("gender",           "ALTER TABLE patients ADD COLUMN gender TEXT"),
        ("medical_history",  "ALTER TABLE patients ADD COLUMN medical_history TEXT"),
        ("notes",            "ALTER TABLE patients ADD COLUMN notes TEXT"),
    ]:
        if col not in patient_cols:
            conn.execute(ddl)

    image_cols = cols("images")
    for col, ddl in [
        ("original_path",  "ALTER TABLE images ADD COLUMN original_path TEXT"),
        ("tooth_number",   "ALTER TABLE images ADD COLUMN tooth_number TEXT"),
        ("notes",          "ALTER TABLE images ADD COLUMN notes TEXT"),
        ("kv",             "ALTER TABLE images ADD COLUMN kv INTEGER"),
        ("ma",             "ALTER TABLE images ADD COLUMN ma REAL"),
        ("exposure_time",  "ALTER TABLE images ADD COLUMN exposure_time REAL"),
    ]:
        if col not in image_cols:
            conn.execute(ddl)


def add_patient(first_name, last_name, date_of_birth=None, phone=None,
                email=None, gender=None, medical_history=None, notes=None):
    conn = get_connection()
    c = conn.execute(
        "INSERT INTO patients (first_name, last_name, date_of_birth, phone, email, "
        "gender, medical_history, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (first_name, last_name, date_of_birth, phone, email,
         gender, medical_history, notes),
    )
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


def update_patient(pid, **fields):
    allowed = {"first_name", "last_name", "date_of_birth", "phone", "email",
               "gender", "medical_history", "notes"}
    keys = [k for k in fields.keys() if k in allowed]
    if not keys:
        return
    values = [fields[k] for k in keys] + [pid]
    set_clause = ", ".join(f"{k}=?" for k in keys)
    conn = get_connection()
    conn.execute(f"UPDATE patients SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_patient(pid):
    conn = get_connection()
    conn.execute("DELETE FROM patients WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def search_patients(query=""):
    conn = get_connection()
    if query:
        rows = conn.execute(
            "SELECT * FROM patients WHERE first_name LIKE ? OR last_name LIKE ? "
            "OR phone LIKE ? ORDER BY last_name, first_name",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM patients ORDER BY last_name, first_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient(pid):
    conn = get_connection()
    r = conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(r) if r else None


def add_image(patient_id, file_path, image_type="periapical",
              tooth_number=None, notes=None, original_path=None):
    """Store image. original_path points to immutable original — never modified."""
    conn = get_connection()
    c = conn.execute(
        "INSERT INTO images (patient_id, file_path, original_path, image_type, "
        "tooth_number, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (patient_id, file_path, original_path or file_path, image_type, tooth_number, notes),
    )
    img_id = c.lastrowid
    conn.commit()
    conn.close()
    return img_id


def update_image(image_id, **fields):
    allowed = {"image_type", "tooth_number", "notes"}
    keys = [k for k in fields.keys() if k in allowed]
    if not keys:
        return
    values = [fields[k] for k in keys] + [image_id]
    set_clause = ", ".join(f"{k}=?" for k in keys)
    conn = get_connection()
    conn.execute(f"UPDATE images SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()


def get_patient_images(patient_id, tooth_number=None, image_type=None):
    conn = get_connection()
    query = "SELECT * FROM images WHERE patient_id=?"
    params = [patient_id]
    if tooth_number:
        query += " AND tooth_number=?"
        params.append(str(tooth_number))
    if image_type:
        query += " AND image_type=?"
        params.append(image_type)
    query += " ORDER BY captured_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_image(image_id):
    conn = get_connection()
    r = conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def delete_image(image_id):
    conn = get_connection()
    conn.execute("DELETE FROM images WHERE id=?", (image_id,))
    conn.commit()
    conn.close()


def set_tooth_status(patient_id, tooth_number, status, surfaces=None, notes=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO tooth_status (patient_id, tooth_number, status, surfaces, notes) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(patient_id, tooth_number) DO UPDATE SET "
        "status=excluded.status, surfaces=excluded.surfaces, notes=excluded.notes, "
        "updated_at=datetime('now')",
        (patient_id, tooth_number, status, surfaces, notes),
    )
    conn.commit()
    conn.close()


def get_tooth_statuses(patient_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tooth_status WHERE patient_id=?", (patient_id,)
    ).fetchall()
    conn.close()
    return {r["tooth_number"]: dict(r) for r in rows}


def clear_tooth_status(patient_id, tooth_number):
    conn = get_connection()
    conn.execute(
        "DELETE FROM tooth_status WHERE patient_id=? AND tooth_number=?",
        (patient_id, tooth_number),
    )
    conn.commit()
    conn.close()


def add_treatment(patient_id, procedure, tooth_number=None,
                  treatment_date=None, notes=None):
    conn = get_connection()
    if treatment_date:
        c = conn.execute(
            "INSERT INTO treatments (patient_id, tooth_number, treatment_date, "
            "procedure, notes) VALUES (?, ?, ?, ?, ?)",
            (patient_id, tooth_number, treatment_date, procedure, notes),
        )
    else:
        c = conn.execute(
            "INSERT INTO treatments (patient_id, tooth_number, procedure, notes) "
            "VALUES (?, ?, ?, ?)",
            (patient_id, tooth_number, procedure, notes),
        )
    tid = c.lastrowid
    conn.commit()
    conn.close()
    return tid


def get_treatments(patient_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM treatments WHERE patient_id=? "
        "ORDER BY treatment_date DESC, id DESC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_treatment(treatment_id):
    conn = get_connection()
    conn.execute("DELETE FROM treatments WHERE id=?", (treatment_id,))
    conn.commit()
    conn.close()
