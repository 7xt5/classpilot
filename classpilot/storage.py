"""
storage.py - The JSON "database" of ClassPilot.

Every collection (users, classes, assignments, ...) lives in its own JSON
file inside the ``data/`` folder.  Each file holds a list of dictionaries
("records").  Every record has a unique ``"id"`` field.

Why this design?
  * It is easy to open the files and see exactly what is stored.
  * Data survives restarts because it is written to disk on every change.
  * Writes are "atomic": we write to a temporary file first and then swap
    it into place, so a crash can never leave a half-written JSON file.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

# The data folder can be changed with an environment variable (used by tests).
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CLASSPILOT_DATA_DIR", PROJECT_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"

# All list-style collections used by the app.
COLLECTIONS = [
    "users",
    "classes",
    "subjects",
    "lessons",
    "assignments",
    "submissions",
    "quizzes",
    "quiz_attempts",
    "attendance",
    "announcements",
    "pulse",
    "teacher_prefs",
    "ai_history",
]

# Default school settings (stored in settings.json, which is a dictionary).
DEFAULT_SETTINGS = {
    "school_name": "ClassPilot Academy",
    "academic_year": "2026-2027",
    # Deadline Conflict Detector
    "conflict_window_days": 2,       # look this many days before/after a due date
    "conflict_max_deadlines": 3,     # warn when this many deadlines fall in the window
    # Early Support Alerts
    "alert_missing_threshold": 2,    # missing items before we raise an alert
    "alert_low_grade": 60,           # average (%) below this is a concern
    "alert_attendance": 85,          # attendance (%) below this is a concern
    "alert_decline_points": 10,      # grade drop (percentage points) that counts as declining
    # ClassPulse
    "pulse_low_threshold": 2.5,      # average confidence (1-5) below this is flagged
    # Assignments
    "default_late_penalty": 10,      # % deducted from late work by default
    # Letter grade scale (checked from top to bottom)
    "grade_scale": [
        {"letter": "A", "min": 90},
        {"letter": "B", "min": 80},
        {"letter": "C", "min": 70},
        {"letter": "D", "min": 60},
        {"letter": "F", "min": 0},
    ],
}

# One lock for the whole app so two browser sessions never write at once.
_lock = threading.RLock()


# --------------------------------------------------------------------------
# Low level file helpers
# --------------------------------------------------------------------------
def _path(name):
    """Return the full path of the JSON file for a collection."""
    return DATA_DIR / f"{name}.json"


def _read_json(path, default):
    """Read a JSON file. If it is missing or broken, return ``default``."""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        # Keep a copy of the damaged file so nothing is silently lost.
        try:
            shutil.copy(path, path.with_suffix(".corrupt.bak"))
        except OSError:
            pass
        return default


def _write_json(path, data):
    """Write data to a JSON file atomically (temp file + rename)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    # On Windows the target can be briefly locked by a reader, so retry.
    for attempt in range(5):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError:
            time.sleep(0.1 * (attempt + 1))
    os.replace(temp_path, path)  # final try - raises if it still fails


# --------------------------------------------------------------------------
# Collection helpers (lists of records)
# --------------------------------------------------------------------------
def load(name):
    """Return every record in a collection as a list of dictionaries."""
    with _lock:
        data = _read_json(_path(name), [])
        return data if isinstance(data, list) else []


def save(name, records):
    """Replace the whole collection with ``records``."""
    with _lock:
        _write_json(_path(name), records)


def new_id(prefix):
    """Create a short unique id such as ``asg_3f9a1c2b``."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def get(name, record_id):
    """Find one record by id. Returns ``None`` if it does not exist."""
    for record in load(name):
        if record.get("id") == record_id:
            return record
    return None


def find(name, **filters):
    """Return records whose fields equal all the given filters.

    Example: ``find("submissions", assignment_id="asg_1", student_id="u_2")``
    """
    return [
        record for record in load(name)
        if all(record.get(key) == value for key, value in filters.items())
    ]


def insert(name, record):
    """Add a record to a collection and return it."""
    with _lock:
        records = load(name)
        records.append(record)
        save(name, records)
    return record


def update(name, record_id, changes):
    """Update fields of one record. Returns the updated record or ``None``."""
    with _lock:
        records = load(name)
        for record in records:
            if record.get("id") == record_id:
                record.update(changes)
                save(name, records)
                return record
    return None


def delete(name, record_id):
    """Delete one record by id. Returns ``True`` if something was deleted."""
    with _lock:
        records = load(name)
        kept = [r for r in records if r.get("id") != record_id]
        if len(kept) == len(records):
            return False
        save(name, kept)
        return True


def delete_where(name, predicate):
    """Delete every record for which ``predicate(record)`` is True.

    Returns the number of deleted records.
    """
    with _lock:
        records = load(name)
        kept = [r for r in records if not predicate(r)]
        removed = len(records) - len(kept)
        if removed:
            save(name, kept)
        return removed


# --------------------------------------------------------------------------
# Settings (a single dictionary instead of a list)
# --------------------------------------------------------------------------
def load_settings():
    """Return school settings, filling in any missing keys with defaults."""
    with _lock:
        stored = _read_json(_path("settings"), {})
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    if isinstance(stored, dict):
        settings.update(stored)
    return settings


def save_settings(settings):
    """Persist the settings dictionary."""
    with _lock:
        _write_json(_path("settings"), settings)


# --------------------------------------------------------------------------
# Whole-database helpers
# --------------------------------------------------------------------------
def is_empty():
    """True when no users exist yet (first start of the app)."""
    return len(load("users")) == 0


def export_all():
    """Return every collection in one dictionary (used for backups)."""
    backup = {name: load(name) for name in COLLECTIONS}
    backup["settings"] = load_settings()
    return backup


def wipe_all():
    """Delete all JSON data files (used by 'Reset demo data')."""
    with _lock:
        for name in COLLECTIONS + ["settings"]:
            path = _path(name)
            if path.exists():
                path.unlink()
        if UPLOAD_DIR.exists():
            shutil.rmtree(UPLOAD_DIR, ignore_errors=True)


# --------------------------------------------------------------------------
# File uploads (lesson materials and assignment attachments)
# --------------------------------------------------------------------------
MAX_UPLOAD_MB = 10
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".zip", ".csv", ".md", ".py",
}


def _safe_filename(filename):
    """Remove anything from a filename that could be dangerous."""
    base = os.path.basename(filename or "file")
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "._- ")
    return cleaned.strip() or "file"


def save_upload(uploaded_file, folder):
    """Save a Streamlit ``UploadedFile`` to ``data/uploads/<folder>/``.

    Returns a small dictionary describing the stored file, or raises
    ``ValueError`` with a friendly message if the file is not allowed.
    """
    name = _safe_filename(uploaded_file.name)
    extension = os.path.splitext(name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type '{extension or 'unknown'}' is not allowed.")
    data = uploaded_file.getvalue()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {MAX_UPLOAD_MB} MB.")
    target_dir = UPLOAD_DIR / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:8]}_{name}"
    with open(target_dir / stored_name, "wb") as file:
        file.write(data)
    return {"name": name, "path": f"{folder}/{stored_name}", "size": len(data)}


def read_upload(relative_path):
    """Return the bytes of an uploaded file, or ``None`` if it is missing."""
    try:
        full_path = (UPLOAD_DIR / relative_path).resolve()
        # Never allow reading outside the uploads folder.
        if UPLOAD_DIR.resolve() not in full_path.parents:
            return None
        with open(full_path, "rb") as file:
            return file.read()
    except OSError:
        return None


def delete_upload(relative_path):
    """Remove an uploaded file if it exists."""
    try:
        full_path = (UPLOAD_DIR / relative_path).resolve()
        if UPLOAD_DIR.resolve() in full_path.parents and full_path.exists():
            full_path.unlink()
    except OSError:
        pass
