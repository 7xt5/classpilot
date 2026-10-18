"""
school.py - People and structure: users, classes, subjects, announcements.

Key ideas
  * A **class** is a group of students (e.g. "Grade 9 - A").
  * A **subject** is one course taught to one class by one teacher
    (e.g. "Mathematics" for "Grade 9 - A" taught by Ms. Khan).
    Lessons, assignments, quizzes and attendance all belong to a subject.
  * Every function that changes data validates its input and returns an
    error message (string) instead of crashing.
"""

import re

from classpilot import auth, storage, utils

USERNAME_PATTERN = re.compile(r"^[a-z0-9._]{3,30}$")


# ==========================================================================
# Users
# ==========================================================================
def get_user(user_id):
    return storage.get("users", user_id)


def users_by_role(role, active_only=False):
    """All users with the given role, sorted by name."""
    users = [u for u in storage.load("users") if u["role"] == role]
    if active_only:
        users = [u for u in users if u.get("active", True)]
    return sorted(users, key=lambda u: u["full_name"].lower())


def name_map():
    """Dictionary of user id -> full name (handy for tables)."""
    return {u["id"]: u["full_name"] for u in storage.load("users")}


def user_name(user_id):
    user = get_user(user_id)
    return user["full_name"] if user else "Unknown user"


def _validate_user_fields(username, full_name, email, role, ignore_id=None):
    """Shared validation for creating and editing users."""
    if not USERNAME_PATTERN.match(username):
        return "Username must be 3-30 characters: lowercase letters, numbers, dots or underscores."
    if not full_name:
        return "Full name is required."
    if not utils.is_valid_email(email):
        return "Please enter a valid e-mail address."
    if role not in auth.ROLES:
        return "Please choose a valid role."
    for other in storage.load("users"):
        if other["id"] == ignore_id:
            continue
        if other["username"] == username:
            return f"The username '{username}' is already taken."
        if other.get("email", "").lower() == email.lower():
            return f"The e-mail '{email}' is already used by another account."
    return None


def create_user(username, full_name, email, role, password):
    """Create a new account. Returns ``(user, error)``."""
    username = utils.clean(username, 30).lower()
    full_name = utils.clean(full_name, 80)
    email = utils.clean(email, 120).lower()
    error = _validate_user_fields(username, full_name, email, role)
    if error:
        return None, error
    problems = auth.password_problems(password or "")
    if problems:
        return None, "Password needs " + ", ".join(problems) + "."
    user = {
        "id": storage.new_id("usr"),
        "username": username,
        "full_name": full_name,
        "email": email,
        "role": role,
        "password_hash": auth.hash_password(password),
        "active": True,
        "created_at": utils.now_iso(),
        "last_login": None,
        "failed_attempts": 0,
        "locked_until": None,
    }
    return storage.insert("users", user), None


def register_account(username, full_name, email, role, password, confirm_password, class_name=""):
    """Self-service sign-up for a Student or Teacher account.

    Returns ``(user, None)`` on success or ``(None, error_message)``.
    """
    username = utils.clean(username, 30).lower()
    full_name = utils.clean(full_name, 80)
    email = utils.clean(email, 120).lower()
    role = (role or "").strip().lower()
    if role not in ("student", "teacher"):
        return None, "Please select whether you are a Student or a Teacher."
    if not email and username:
        email = f"{username}@novarix.edu"
    if (password or "") != (confirm_password or ""):
        return None, "Passwords do not match."
    user, error = create_user(username, full_name, email, role, password)
    if error:
        return None, error

    if role == "student" and class_name and class_name != "none":
        target_cls = get_class(class_name)
        if not target_cls:
            clean_cls = utils.clean(class_name, 60)
            target_cls = next((c for c in all_classes() if c["name"].lower() == clean_cls.lower()), None)
            if not target_cls and clean_cls:
                target_cls, _ = create_class(clean_cls, clean_cls.split("-")[0].strip(), "Room 101")
        if target_cls:
            set_student_class(user["id"], target_cls["id"])

    return user, None



def _active_admin_count(excluding_id=None):
    return sum(1 for u in storage.load("users")
               if u["role"] == "admin" and u.get("active", True) and u["id"] != excluding_id)


def update_user(acting_user_id, user_id, full_name, email, role, active):
    """Edit an account. Returns an error message or ``None``."""
    user = get_user(user_id)
    if not user:
        return "User not found."
    full_name = utils.clean(full_name, 80)
    email = utils.clean(email, 120).lower()
    error = _validate_user_fields(user["username"], full_name, email, role, ignore_id=user_id)
    if error:
        return error
    # Safety rules so the school can never lock itself out.
    if user_id == acting_user_id and (role != "admin" or not active):
        return "You cannot remove your own admin access or deactivate yourself."
    if user["role"] == "admin" and (role != "admin" or not active) and _active_admin_count(user_id) == 0:
        return "At least one active admin account must remain."
    if user["role"] == "teacher" and role != "teacher" and subjects_for_teacher(user_id):
        return "This teacher still teaches subjects. Reassign those subjects first."
    if user["role"] == "student" and role != "student" and student_class(user_id):
        return "Remove this student from their class before changing the role."
    storage.update("users", user_id, {
        "full_name": full_name, "email": email, "role": role, "active": bool(active),
    })
    return None


def reset_password(user_id, new_password):
    """Admin action: set a new password for someone else."""
    if not get_user(user_id):
        return "User not found."
    problems = auth.password_problems(new_password or "")
    if problems:
        return "Password needs " + ", ".join(problems) + "."
    storage.update("users", user_id, {
        "password_hash": auth.hash_password(new_password),
        "failed_attempts": 0, "locked_until": None,
    })
    return None


def delete_user(acting_user_id, user_id):
    """Permanently delete an account and the personal records attached to it."""
    user = get_user(user_id)
    if not user:
        return "User not found."
    if user_id == acting_user_id:
        return "You cannot delete your own account."
    if user["role"] == "admin" and _active_admin_count(user_id) == 0:
        return "At least one active admin account must remain."
    if user["role"] == "teacher" and subjects_for_teacher(user_id):
        return "This teacher still teaches subjects. Reassign or delete those subjects first."

    # Remove a student from classes and delete their personal coursework.
    classes = storage.load("classes")
    for cls in classes:
        if user_id in cls.get("student_ids", []):
            cls["student_ids"].remove(user_id)
    storage.save("classes", classes)
    for sub in storage.find("submissions", student_id=user_id):
        if sub.get("file"):
            storage.delete_upload(sub["file"]["path"])
    storage.delete_where("submissions", lambda r: r["student_id"] == user_id)
    storage.delete_where("quiz_attempts", lambda r: r["student_id"] == user_id)
    storage.delete_where("pulse", lambda r: r["student_id"] == user_id)
    sessions = storage.load("attendance")
    for session in sessions:
        session["records"].pop(user_id, None)
    storage.save("attendance", sessions)
    storage.delete("users", user_id)
    return None


# ==========================================================================
# Classes
# ==========================================================================
def get_class(class_id):
    return storage.get("classes", class_id)


def all_classes():
    return sorted(storage.load("classes"), key=lambda c: c["name"].lower())


def class_name(class_id):
    if class_id == "all":
        return "Whole school"
    cls = get_class(class_id)
    return cls["name"] if cls else "Unknown class"


def class_students(class_id, active_only=True):
    """Student records that belong to a class, sorted by name."""
    cls = get_class(class_id)
    if not cls:
        return []
    students = [storage.get("users", sid) for sid in cls.get("student_ids", [])]
    students = [s for s in students if s and (s.get("active", True) or not active_only)]
    return sorted(students, key=lambda s: s["full_name"].lower())


def student_class(student_id):
    """The class a student belongs to (or ``None``)."""
    for cls in storage.load("classes"):
        if student_id in cls.get("student_ids", []):
            return cls
    return None


def _validate_class(name, ignore_id=None):
    if not name:
        return "Class name is required."
    for cls in storage.load("classes"):
        if cls["id"] != ignore_id and cls["name"].lower() == name.lower():
            return f"A class named '{name}' already exists."
    return None


def create_class(name, grade_level, room):
    name = utils.clean(name, 60)
    error = _validate_class(name)
    if error:
        return None, error
    cls = {
        "id": storage.new_id("cls"),
        "name": name,
        "grade_level": utils.clean(grade_level, 20),
        "room": utils.clean(room, 30),
        "student_ids": [],
        "created_at": utils.now_iso(),
    }
    return storage.insert("classes", cls), None


def update_class(class_id, name, grade_level, room):
    if not get_class(class_id):
        return "Class not found."
    name = utils.clean(name, 60)
    error = _validate_class(name, ignore_id=class_id)
    if error:
        return error
    storage.update("classes", class_id, {
        "name": name, "grade_level": utils.clean(grade_level, 20), "room": utils.clean(room, 30),
    })
    return None


def set_class_students(class_id, student_ids):
    """Set the roster of a class. A student can only be in ONE class,
    so they are automatically removed from any other class."""
    if not get_class(class_id):
        return "Class not found."
    valid_ids = {u["id"] for u in users_by_role("student")}
    student_ids = [sid for sid in student_ids if sid in valid_ids]
    classes = storage.load("classes")
    for cls in classes:
        if cls["id"] == class_id:
            cls["student_ids"] = list(dict.fromkeys(student_ids))
        else:
            cls["student_ids"] = [sid for sid in cls.get("student_ids", []) if sid not in student_ids]
    storage.save("classes", classes)
    return None


def set_student_class(student_id, class_id):
    """Enroll a single student in ``class_id`` (removing them from any other class)."""
    cls = get_class(class_id)
    if not cls:
        return "Class not found."
    current_ids = list(cls.get("student_ids", []))
    if student_id not in current_ids:
        current_ids.append(student_id)
    return set_class_students(class_id, current_ids)



def delete_class(class_id):
    if not get_class(class_id):
        return "Class not found."
    if subjects_for_class(class_id):
        return "This class still has subjects. Delete or move those subjects first."
    storage.delete_where("announcements", lambda a: a["class_id"] == class_id)
    storage.delete("classes", class_id)
    return None


# ==========================================================================
# Subjects (a course for one class, taught by one teacher)
# ==========================================================================
def get_subject(subject_id):
    return storage.get("subjects", subject_id)


def all_subjects():
    return sorted(storage.load("subjects"), key=lambda s: (class_name(s["class_id"]), s["name"]))


def subject_label(subject):
    """e.g. 'Mathematics · Grade 9 - A'."""
    if isinstance(subject, str):
        subject = get_subject(subject)
    if not subject:
        return "Unknown subject"
    return f"{subject['name']} · {class_name(subject['class_id'])}"


def subjects_for_teacher(teacher_id):
    return [s for s in all_subjects() if s["teacher_id"] == teacher_id]


def subjects_for_class(class_id):
    return [s for s in all_subjects() if s["class_id"] == class_id]


def subjects_for_student(student_id):
    cls = student_class(student_id)
    return subjects_for_class(cls["id"]) if cls else []


def teacher_class_ids(teacher_id):
    return sorted({s["class_id"] for s in subjects_for_teacher(teacher_id)})


def teacher_students(teacher_id):
    """Every active student taught by this teacher (no duplicates)."""
    seen, students = set(), []
    for class_id in teacher_class_ids(teacher_id):
        for student in class_students(class_id):
            if student["id"] not in seen:
                seen.add(student["id"])
                students.append(student)
    return sorted(students, key=lambda s: s["full_name"].lower())


def teacher_owns_subject(teacher_id, subject_id):
    subject = get_subject(subject_id)
    return bool(subject and subject["teacher_id"] == teacher_id)


def student_in_subject(student_id, subject_id):
    subject = get_subject(subject_id)
    cls = student_class(student_id)
    return bool(subject and cls and subject["class_id"] == cls["id"])


def _validate_subject(name, code, class_id, teacher_id, ignore_id=None):
    if not name:
        return "Subject name is required."
    if not get_class(class_id):
        return "Please choose a valid class."
    teacher = get_user(teacher_id)
    if not teacher or teacher["role"] != "teacher":
        return "Please choose a valid teacher."
    for subj in storage.load("subjects"):
        if subj["id"] == ignore_id:
            continue
        if subj["class_id"] == class_id and subj["name"].lower() == name.lower():
            return f"'{name}' already exists for this class."
        if code and subj.get("code", "").lower() == code.lower():
            return f"The subject code '{code}' is already used."
    return None


def create_subject(name, code, class_id, teacher_id, description=""):
    name, code = utils.clean(name, 60), utils.clean(code, 20).upper()
    error = _validate_subject(name, code, class_id, teacher_id)
    if error:
        return None, error
    subject = {
        "id": storage.new_id("sub"),
        "name": name,
        "code": code,
        "class_id": class_id,
        "teacher_id": teacher_id,
        "description": utils.clean(description, 500),
        "created_at": utils.now_iso(),
    }
    return storage.insert("subjects", subject), None


def update_subject(subject_id, name, code, teacher_id, description=""):
    """Edit a subject. (The class cannot change, because coursework and
    submissions are tied to that class's students.)"""
    subject = get_subject(subject_id)
    if not subject:
        return "Subject not found."
    name, code = utils.clean(name, 60), utils.clean(code, 20).upper()
    error = _validate_subject(name, code, subject["class_id"], teacher_id, ignore_id=subject_id)
    if error:
        return error
    storage.update("subjects", subject_id, {
        "name": name, "code": code, "teacher_id": teacher_id,
        "description": utils.clean(description, 500),
    })
    return None


def delete_subject(subject_id):
    """Delete a subject and ALL of its coursework (lessons, assignments, ...)."""
    if not get_subject(subject_id):
        return "Subject not found."
    assignment_ids = {a["id"] for a in storage.find("assignments", subject_id=subject_id)}
    quiz_ids = {q["id"] for q in storage.find("quizzes", subject_id=subject_id)}
    for sub in storage.load("submissions"):
        if sub["assignment_id"] in assignment_ids and sub.get("file"):
            storage.delete_upload(sub["file"]["path"])
    for lesson in storage.find("lessons", subject_id=subject_id):
        for item in lesson.get("files", []):
            storage.delete_upload(item["path"])
    storage.delete_where("submissions", lambda r: r["assignment_id"] in assignment_ids)
    storage.delete_where("quiz_attempts", lambda r: r["quiz_id"] in quiz_ids)
    for name in ("assignments", "quizzes", "lessons", "attendance", "pulse"):
        storage.delete_where(name, lambda r: r.get("subject_id") == subject_id)
    storage.delete("subjects", subject_id)
    return None


# ==========================================================================
# Announcements (with read / unread tracking)
# ==========================================================================
def announcements_for_user(user):
    """Announcements this user is allowed to see, pinned first, newest first."""
    items = storage.load("announcements")
    if user["role"] == "student":
        cls = student_class(user["id"])
        allowed = {"all"} | ({cls["id"]} if cls else set())
        items = [a for a in items if a["class_id"] in allowed]
    elif user["role"] == "teacher":
        allowed = {"all"} | set(teacher_class_ids(user["id"]))
        items = [a for a in items if a["class_id"] in allowed or a["author_id"] == user["id"]]
    items.sort(key=lambda a: a["created_at"], reverse=True)
    items.sort(key=lambda a: not a.get("pinned", False))
    return items


def is_unread(announcement, user_id):
    return user_id not in announcement.get("read_by", []) and announcement["author_id"] != user_id


def unread_count(user):
    return sum(1 for a in announcements_for_user(user) if is_unread(a, user["id"]))


def mark_read(announcement_id, user_id):
    announcement = storage.get("announcements", announcement_id)
    if announcement and user_id not in announcement.get("read_by", []):
        storage.update("announcements", announcement_id,
                       {"read_by": announcement.get("read_by", []) + [user_id]})


def mark_unread(announcement_id, user_id):
    announcement = storage.get("announcements", announcement_id)
    if announcement and user_id in announcement.get("read_by", []):
        storage.update("announcements", announcement_id,
                       {"read_by": [u for u in announcement["read_by"] if u != user_id]})


def mark_all_read(user):
    items = storage.load("announcements")
    visible = {a["id"] for a in announcements_for_user(user)}
    for item in items:
        if item["id"] in visible and user["id"] not in item.get("read_by", []):
            item.setdefault("read_by", []).append(user["id"])
    storage.save("announcements", items)


def announcement_audience(announcement):
    """Users who are expected to read an announcement (for read tracking)."""
    if announcement["class_id"] == "all":
        people = users_by_role("student", True) + users_by_role("teacher", True)
    else:
        people = class_students(announcement["class_id"])
    return [p for p in people if p["id"] != announcement["author_id"]]


def can_post_to(user, class_id):
    if user["role"] == "admin":
        return class_id == "all" or get_class(class_id) is not None
    if user["role"] == "teacher":
        return class_id in teacher_class_ids(user["id"])
    return False


def create_announcement(user, class_id, title, body, pinned=False, priority="Normal"):
    title, body = utils.clean(title, 120), utils.clean(body, 4000)
    if not can_post_to(user, class_id):
        return None, "You cannot post announcements to this class."
    if not title or not body:
        return None, "Both a title and a message are required."
    if priority not in ("Normal", "Important", "Urgent"):
        priority = "Normal"
    announcement = {
        "id": storage.new_id("ann"),
        "class_id": class_id,
        "title": title,
        "body": body,
        "author_id": user["id"],
        "created_at": utils.now_iso(),
        "pinned": bool(pinned),
        "priority": priority,
        "read_by": [],
    }
    return storage.insert("announcements", announcement), None


def can_manage_announcement(user, announcement):
    return user["role"] == "admin" or announcement["author_id"] == user["id"]


def toggle_pin(user, announcement_id):
    announcement = storage.get("announcements", announcement_id)
    if not announcement or not can_manage_announcement(user, announcement):
        return "You cannot change this announcement."
    storage.update("announcements", announcement_id, {"pinned": not announcement.get("pinned")})
    return None


def delete_announcement(user, announcement_id):
    announcement = storage.get("announcements", announcement_id)
    if not announcement or not can_manage_announcement(user, announcement):
        return "You cannot delete this announcement."
    storage.delete("announcements", announcement_id)
    return None
