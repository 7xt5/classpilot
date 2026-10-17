"""
auth.py - Passwords, login, and role-based permissions.

Passwords are NEVER stored in plain text.  We use PBKDF2-HMAC-SHA256 from
Python's standard ``hashlib`` module with a random salt per user and many
iterations, stored in one string:

    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import streamlit as st

from classpilot import storage

ITERATIONS = 200_000
MAX_FAILED_ATTEMPTS = 5          # lock the account after this many bad passwords
LOCKOUT_MINUTES = 5              # ... for this many minutes
ROLES = ["admin", "teacher", "student"]


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(password):
    """Return a salted PBKDF2 hash string for ``password``."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, stored_hash):
    """Check a password against a stored hash string (timing-safe)."""
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False


def password_problems(password):
    """Return a list of reasons why a password is too weak (empty = OK)."""
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if not any(ch.isalpha() for ch in password):
        problems.append("at least one letter")
    if not any(ch.isdigit() for ch in password):
        problems.append("at least one number")
    return problems


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------
def authenticate(username, password):
    """Try to log a user in.

    Returns ``(user, None)`` on success or ``(None, error_message)``.
    Failed attempts are counted and the account is locked temporarily
    after too many failures (protects against password guessing).
    """
    username = (username or "").strip().lower()
    if not username or not password:
        return None, "Please enter both username and password."

    matches = storage.find("users", username=username)
    if not matches:
        return None, "Incorrect username or password."
    user = matches[0]

    if not user.get("active", True):
        return None, "This account is deactivated. Please contact the school admin."

    locked_until = user.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
        minutes = int((datetime.fromisoformat(locked_until) - datetime.now()).total_seconds() // 60) + 1
        return None, f"Too many failed attempts. Try again in {minutes} minute(s)."

    if not verify_password(password, user.get("password_hash", "")):
        failed = user.get("failed_attempts", 0) + 1
        changes = {"failed_attempts": failed}
        if failed >= MAX_FAILED_ATTEMPTS:
            changes["failed_attempts"] = 0
            changes["locked_until"] = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
        storage.update("users", user["id"], changes)
        return None, "Incorrect username or password."

    storage.update("users", user["id"], {
        "failed_attempts": 0,
        "locked_until": None,
        "last_login": datetime.now().isoformat(timespec="seconds"),
    })
    return storage.get("users", user["id"]), None


def change_password(user_id, current_password, new_password, confirm_password):
    """Change a user's own password. Returns an error message or ``None``."""
    user = storage.get("users", user_id)
    if not user:
        return "User not found."
    if not verify_password(current_password, user["password_hash"]):
        return "Your current password is incorrect."
    if new_password != confirm_password:
        return "The new passwords do not match."
    problems = password_problems(new_password)
    if problems:
        return "New password needs " + ", ".join(problems) + "."
    storage.update("users", user_id, {"password_hash": hash_password(new_password)})
    return None


# --------------------------------------------------------------------------
# Session helpers (who is logged in right now?)
# --------------------------------------------------------------------------
def login_session(user):
    """Remember the logged-in user's id in this browser session."""
    st.session_state["user_id"] = user["id"]


def logout():
    """Forget the current user and clear every session value."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def current_user():
    """Return the logged-in user record, freshly loaded from disk.

    Re-loading every time means that if an admin deactivates an account
    or changes a role, it takes effect immediately.
    """
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None
    user = storage.get("users", user_id)
    if not user or not user.get("active", True):
        logout()
        return None
    return user


def require_role(*allowed_roles):
    """Stop the page immediately if the current user lacks permission.

    Every page calls this first, so even a hand-typed URL cannot open a
    page that belongs to another role.
    """
    user = current_user()
    if user is None or user.get("role") not in allowed_roles:
        st.error("🔒 You do not have permission to view this page.")
        st.stop()
    return user
