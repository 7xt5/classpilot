"""
insights.py - The "smart" features that help teachers act early.

  * Deadline Conflict Detector - spots clusters of deadlines for one class
    across ALL subjects (teachers usually can't see each other's deadlines).
  * Early Support Alerts - combines missing work, low/declining grades and
    attendance into one prioritised list of students who may need help.
  * Search - one search box, results limited to what the user may see.
  * Dashboard helpers - to-do lists for students and teachers.
"""

from datetime import date, datetime, timedelta

from classpilot import coursework, school, storage, tracking, utils


# ==========================================================================
# Deadline Conflict Detector
# ==========================================================================
def class_deadlines(class_id, exclude_id=None):
    """Every assignment and quiz deadline for a class, across all subjects."""
    subject_ids = [s["id"] for s in school.subjects_for_class(class_id)]
    items = []
    for a in coursework.assignments_for_subjects(subject_ids):
        items.append({"id": a["id"], "kind": "Assignment", "title": a["title"],
                      "subject_id": a["subject_id"], "due": utils.parse_dt(a["due"])})
    for q in coursework.quizzes_for_subjects(subject_ids):
        items.append({"id": q["id"], "kind": "Quiz", "title": q["title"],
                      "subject_id": q["subject_id"], "due": utils.parse_dt(q["due"])})
    items = [i for i in items if i["id"] != exclude_id and i["due"]]
    for item in items:
        item["subject"] = school.subject_label(item["subject_id"])
    return sorted(items, key=lambda i: i["due"])


def _peak_load(day, other_days, window):
    """Largest number of deadlines (including ``day``) inside any span of
    ``window`` days that contains ``day``."""
    best = 1
    for start_offset in range(window + 1):
        start = day - timedelta(days=start_offset)
        end = start + timedelta(days=window)
        count = 1 + sum(1 for d in other_days if start <= d <= end)
        best = max(best, count)
    return best


def check_conflicts(class_id, due_iso, exclude_id=None):
    """Check a proposed deadline before saving it.

    Returns a dict with:
      nearby     - deadlines within +/- window days of the proposed date
      load       - peak number of deadlines in any window containing it
      conflict   - True when load reaches the school's limit
      suggestion - the nearest weekday (same time) that avoids the conflict
    """
    settings = storage.load_settings()
    window = int(settings["conflict_window_days"])
    limit = int(settings["conflict_max_deadlines"])
    due = utils.parse_dt(due_iso)
    if not due:
        return {"nearby": [], "load": 0, "conflict": False, "suggestion": None}
    others = class_deadlines(class_id, exclude_id)
    other_days = [i["due"].date() for i in others]
    nearby = [i for i in others if abs((i["due"].date() - due.date()).days) <= window]
    load = _peak_load(due.date(), other_days, window)
    suggestion = None
    if load >= limit:
        for shift in range(1, 22):  # look up to three weeks ahead, then back
            for candidate in (due + timedelta(days=shift), due - timedelta(days=shift)):
                if candidate < datetime.now() or candidate.weekday() >= 5:
                    continue
                if _peak_load(candidate.date(), other_days, window) < limit:
                    suggestion = candidate
                    break
            if suggestion:
                break
    return {"nearby": nearby, "load": load, "conflict": load >= limit, "suggestion": suggestion,
            "window": window, "limit": limit}


def conflict_clusters(class_id, upcoming_only=True):
    """Groups of deadlines that fall too close together for one class."""
    settings = storage.load_settings()
    window = int(settings["conflict_window_days"])
    limit = int(settings["conflict_max_deadlines"])
    items = class_deadlines(class_id)
    if upcoming_only:
        items = [i for i in items if i["due"] >= datetime.now()]
    clusters = []
    for first in items:
        start = first["due"].date()
        group = [i for i in items if start <= i["due"].date() <= start + timedelta(days=window)]
        if len(group) >= limit:
            ids = {i["id"] for i in group}
            # Skip groups already contained in an earlier cluster.
            if not any(ids <= {i["id"] for i in c["items"]} for c in clusters):
                clusters.append({
                    "class_id": class_id, "class": school.class_name(class_id),
                    "start": group[0]["due"], "end": group[-1]["due"], "items": group,
                })
    return clusters


def teacher_conflicts(teacher_id):
    clusters = []
    for class_id in school.teacher_class_ids(teacher_id):
        clusters.extend(conflict_clusters(class_id))
    return clusters


def daily_load(class_id, days=28):
    """Number of deadlines per day for the next ``days`` days (for a chart)."""
    today = date.today()
    counts = {today + timedelta(days=n): 0 for n in range(days)}
    for item in class_deadlines(class_id):
        day = item["due"].date()
        if day in counts:
            counts[day] += 1
    return [{"date": d.isoformat(), "deadlines": c} for d, c in counts.items()]


# ==========================================================================
# Early Support Alerts
# ==========================================================================
def missing_items(student_id, subject_id):
    """Past-due assignments with no submission and closed quizzes not taken."""
    missing = []
    for a in coursework.assignments_for_subjects([subject_id]):
        if utils.is_past(a["due"]) and not coursework.submission_for(a["id"], student_id):
            missing.append({"kind": "Assignment", "title": a["title"], "due": a["due"]})
    for q in coursework.quizzes_for_subjects([subject_id], published_only=True):
        if utils.is_past(q["due"]) and not coursework.attempts_for(q["id"], student_id):
            missing.append({"kind": "Quiz", "title": q["title"], "due": q["due"]})
    return missing


def support_alerts(subjects):
    """Build a prioritised list of students who may need support.

    Each reason adds "concern points"; more points = higher priority.
    NovaPulse ratings are deliberately NOT used here because students were
    promised that their individual confidence ratings stay private.
    """
    settings = storage.load_settings()
    alerts = []
    for subject in subjects:
        for student in school.class_students(subject["class_id"]):
            reasons, points = [], 0
            missing = missing_items(student["id"], subject["id"])
            if len(missing) >= settings["alert_missing_threshold"]:
                points += 3 if len(missing) >= 2 * settings["alert_missing_threshold"] else 2
                reasons.append(f"{len(missing)} missing item(s)")

            items = tracking.grade_items_for_student(student["id"], [subject["id"]])
            average = utils.mean([i["percent"] for i in items])
            if average is not None and average < settings["alert_low_grade"]:
                points += 2
                reasons.append(f"average {average:.0f}% (below {settings['alert_low_grade']}%)")

            trend = tracking.grade_trend(items)
            if trend and -trend[2] >= settings["alert_decline_points"]:
                points += 2
                reasons.append(f"grades dropped {abs(trend[2]):.0f} pts ({trend[0]:.0f}% → {trend[1]:.0f}%)")

            attendance = tracking.attendance_summary(student["id"], [subject["id"]])
            if attendance["percent"] is not None and attendance["percent"] < settings["alert_attendance"]:
                points += 2 if attendance["percent"] < settings["alert_attendance"] - 15 else 1
                reasons.append(f"attendance {attendance['percent']:.0f}%")

            if reasons:
                alerts.append({
                    "student_id": student["id"],
                    "student": student["full_name"],
                    "subject_id": subject["id"],
                    "subject": school.subject_label(subject),
                    "points": points,
                    "level": "High" if points >= 4 else "Medium" if points >= 2 else "Low",
                    "reasons": reasons,
                    "missing": missing,
                    "average": average,
                    "trend": trend,
                    "attendance": attendance["percent"],
                    "items": items,
                })
    return sorted(alerts, key=lambda a: (-a["points"], a["student"]))


# ==========================================================================
# Dashboard helpers
# ==========================================================================
def student_todo(student_id):
    """Assignments and quizzes the student still needs to do (soonest first)."""
    subject_ids = [s["id"] for s in school.subjects_for_student(student_id)]
    todo = []
    for a in coursework.assignments_for_subjects(subject_ids):
        status = coursework.assignment_status(a, student_id)
        if status in ("Not submitted", "Missing") and (status == "Not submitted" or a.get("allow_late", True)):
            todo.append({"kind": "Assignment", "id": a["id"], "title": a["title"], "due": a["due"],
                         "subject": school.subject_label(a["subject_id"]), "status": status})
    for q in coursework.quizzes_for_subjects(subject_ids, published_only=True):
        if coursework.quiz_status(q, student_id) == "Open":
            todo.append({"kind": "Quiz", "id": q["id"], "title": q["title"], "due": q["due"],
                         "subject": school.subject_label(q["subject_id"]), "status": "Open"})
    return sorted(todo, key=lambda t: t["due"])


def attendance_not_taken_today(teacher_id):
    """Subjects without an attendance record for today (weekdays only)."""
    if date.today().weekday() >= 5:
        return []
    return [s for s in school.subjects_for_teacher(teacher_id)
            if not tracking.get_attendance(s["id"], date.today())]


# ==========================================================================
# Search (results are limited to what each role may see)
# ==========================================================================
def search(user, query):
    """Return a dict of category -> list of result rows."""
    query = utils.clean(query, 100)
    results = {}
    if len(query) < 2:
        return results
    role = user["role"]

    if role == "admin":
        subjects = school.all_subjects()
        results["People"] = [
            {"Name": u["full_name"], "Username": u["username"], "Role": u["role"].title(),
             "E-mail": u["email"], "Status": "Active" if u.get("active", True) else "Inactive"}
            for u in storage.load("users") if utils.matches(query, u["full_name"], u["username"], u["email"])]
        results["Classes"] = [
            {"Class": c["name"], "Grade": c.get("grade_level", ""), "Room": c.get("room", ""),
             "Students": len(c.get("student_ids", []))}
            for c in school.all_classes() if utils.matches(query, c["name"], c.get("grade_level"), c.get("room"))]
    elif role == "teacher":
        subjects = school.subjects_for_teacher(user["id"])
        results["Students"] = []
        for s in school.teacher_students(user["id"]):
            if utils.matches(query, s["full_name"], s["username"], s["email"]):
                cls = school.student_class(s["id"])
                results["Students"].append({
                    "Name": s["full_name"], "Class": cls["name"] if cls else "—",
                    "Overall average": utils.fmt_pct(tracking.overall_average(s["id"])), "E-mail": s["email"]})
        results["Classes"] = [
            {"Class": school.class_name(cid), "Students": len(school.class_students(cid))}
            for cid in school.teacher_class_ids(user["id"]) if utils.matches(query, school.class_name(cid))]
    else:
        subjects = school.subjects_for_student(user["id"])

    subject_ids = [s["id"] for s in subjects]
    results["Subjects"] = [
        {"Subject": school.subject_label(s), "Code": s.get("code", ""), "Teacher": school.user_name(s["teacher_id"])}
        for s in subjects if utils.matches(query, s["name"], s.get("code"), school.class_name(s["class_id"]))]
    results["Assignments"] = [
        {"Title": a["title"], "Subject": school.subject_label(a["subject_id"]), "Due": utils.fmt_dt(a["due"]),
         "Points": a["max_points"]}
        for a in coursework.assignments_for_subjects(subject_ids) if utils.matches(query, a["title"], a["description"])]
    results["Quizzes"] = [
        {"Title": q["title"], "Subject": school.subject_label(q["subject_id"]), "Closes": utils.fmt_dt(q["due"])}
        for q in coursework.quizzes_for_subjects(subject_ids, published_only=(role == "student"))
        if utils.matches(query, q["title"], q.get("description"))]
    results["Lessons & resources"] = [
        {"Lesson": l["title"], "Topic": l["topic"], "Subject": school.subject_label(l["subject_id"]),
         "Resources": ", ".join(r["label"] for r in l.get("resources", [])) or "—"}
        for l in coursework.lessons_for_subjects(subject_ids)
        if utils.matches(query, l["title"], l["topic"], l["content"],
                         *[r["label"] for r in l.get("resources", [])],
                         *[f["name"] for f in l.get("files", [])])]

    # Grades: students search their own grades; teachers search their classes.
    if role == "student":
        results["My grades"] = [
            {"Item": i["title"], "Type": i["kind"], "Subject": i["subject"], "Score": f"{i['score']:g} / {i['max']}",
             "Percent": utils.fmt_pct(i["percent"])}
            for i in tracking.grade_items_for_student(user["id"]) if utils.matches(query, i["title"], i["subject"])]
    elif role == "teacher":
        grade_rows = []
        assignments = coursework.assignments_for_subjects(subject_ids)
        names = school.name_map()
        for a in assignments:
            for sub in coursework.submissions_for_assignment(a["id"]):
                student = names.get(sub["student_id"], "")
                if sub.get("score") is not None and utils.matches(query, student, a["title"]):
                    grade_rows.append({"Student": student, "Assignment": a["title"],
                                       "Subject": school.subject_label(a["subject_id"]),
                                       "Percent": utils.fmt_pct(coursework.assignment_percent(sub, a))})
        results["Grades"] = grade_rows

    return {category: rows for category, rows in results.items() if rows}


# ==========================================================================
# Teacher-Driven Dashboard Workspace (persisted in teacher_prefs.json)
# ==========================================================================
TEACHER_WIDGETS = {
    "metrics": "■ Live Summary Metrics (To Grade, Support, Conflicts, Pulse)",
    "climate": "■ Class Climate & Mood Report",
    "priorities": "■ Today's Smart Priorities",
    "deadlines": "■ Upcoming Deadlines Table",
    "averages": "■ Class Averages Bar Chart",
    "announcements": "■ Announcements Feed",
}

# Nothing is pre-forced onto the teacher's dashboard — only what the teacher adds appears.
DEFAULT_TEACHER_WIDGETS = []


def get_teacher_prefs(teacher_id):
    """Load (or initialize) a teacher's custom dashboard configuration.

    The dashboard is 100% dependent on what the teacher adds:
      - added_classes: classes/subjects the teacher added to her dashboard
      - added_assignments: assignments to check that the teacher added
      - check_items: custom tasks / notes / reminders the teacher added
      - widgets: optional live LMS widgets the teacher chose to add
    """
    found = storage.find("teacher_prefs", teacher_id=teacher_id)
    if found:
        prefs = found[0]
        prefs.setdefault("widgets", [])
        prefs.setdefault("added_classes", [])
        prefs.setdefault("added_assignments", [])
        prefs.setdefault("pinned_assignment_ids", [])
        prefs.setdefault("focus_note", "")
        prefs.setdefault("check_items", [])
        return prefs

    prefs = {
        "id": storage.new_id("tpf"),
        "teacher_id": teacher_id,
        "widgets": [],
        "added_classes": [],
        "added_assignments": [],
        "pinned_assignment_ids": [],
        "focus_note": "",
        "check_items": [],
    }
    return storage.insert("teacher_prefs", prefs)


def save_teacher_prefs(teacher_id, changes):
    """Update a teacher's dashboard configuration in JSON."""
    prefs = get_teacher_prefs(teacher_id)
    return storage.update("teacher_prefs", prefs["id"], changes)


def add_teacher_dashboard_class(teacher_id, class_name, subject_name, room="", schedule="", notes="",
                                subject_id=None, register_in_school=True):
    """Add a class/subject card directly to the teacher's dashboard."""
    class_name = utils.clean(class_name, 80)
    subject_name = utils.clean(subject_name, 80)
    room = utils.clean(room, 40)
    schedule = utils.clean(schedule, 80)
    notes = utils.clean(notes, 200)

    if subject_id:
        subj = school.get_subject(subject_id)
        if subj:
            cls = school.get_class(subj["class_id"])
            class_name = class_name or (cls["name"] if cls else "Class")
            subject_name = subject_name or subj["name"]
            room = room or (cls.get("room", "") if cls else "")

    if not class_name or not subject_name:
        return "Please enter both a Class name and a Subject name."

    if register_in_school and not subject_id:
        existing_cls = next((c for c in school.all_classes() if c["name"].lower() == class_name.lower()), None)
        if not existing_cls:
            existing_cls, _ = school.create_class(class_name, class_name.split("-")[0].strip(), room or "Room TBD")
        if existing_cls:
            existing_subj = next(
                (s for s in school.subjects_for_class(existing_cls["id"])
                 if s["name"].lower() == subject_name.lower()),
                None,
            )
            if not existing_subj:
                code = "".join(w[0] for w in subject_name.split()[:3]).upper() + existing_cls["name"][:2].upper()
                existing_subj, _ = school.create_subject(
                    subject_name, code, existing_cls["id"], teacher_id, notes or f"{subject_name} ({class_name})"
                )
            if existing_subj:
                subject_id = existing_subj["id"]

    prefs = get_teacher_prefs(teacher_id)
    classes = prefs.get("added_classes", [])
    classes.append({
        "id": storage.new_id("dcls"),
        "class_name": class_name,
        "subject_name": subject_name,
        "subject_id": subject_id,
        "room": room,
        "schedule": schedule,
        "notes": notes,
        "created_at": utils.now_iso(),
    })
    storage.update("teacher_prefs", prefs["id"], {"added_classes": classes})
    return None


def remove_teacher_dashboard_class(teacher_id, item_id):
    """Remove a class card from the teacher's dashboard."""
    prefs = get_teacher_prefs(teacher_id)
    classes = [c for c in prefs.get("added_classes", []) if c["id"] != item_id]
    storage.update("teacher_prefs", prefs["id"], {"added_classes": classes})


def add_teacher_dashboard_assignment(teacher_id, title="", class_subject="", total_to_check=0,
                                     due_note="", priority="Normal", notes="", assignment_id=None):
    """Add an 'Assignment to Check' card to the teacher's dashboard."""
    title = utils.clean(title, 140)
    class_subject = utils.clean(class_subject, 100)
    due_note = utils.clean(due_note, 80)
    notes = utils.clean(notes, 200)

    if assignment_id:
        asg = storage.get("assignments", assignment_id)
        if asg:
            title = title or asg["title"]
            class_subject = class_subject or school.subject_label(asg["subject_id"])
            due_note = due_note or f"Due {utils.fmt_dt(asg['due'])}"
            if not total_to_check:
                subs = coursework.submissions_for_assignment(assignment_id)
                ungraded = [s for s in subs if not s.get("offline") and s.get("score") is None]
                total_to_check = len(ungraded) or len(subs)

    if not title:
        return "Please enter an assignment title to check."

    prefs = get_teacher_prefs(teacher_id)
    items = prefs.get("added_assignments", [])
    items.append({
        "id": storage.new_id("dasg"),
        "title": title,
        "class_subject": class_subject or "General",
        "assignment_id": assignment_id,
        "total_to_check": max(0, int(total_to_check or 0)),
        "checked_count": 0,
        "due_note": due_note,
        "priority": priority if priority in ("Normal", "High", "Urgent") else "Normal",
        "notes": notes,
        "done": False,
        "created_at": utils.now_iso(),
    })
    storage.update("teacher_prefs", prefs["id"], {"added_assignments": items})
    return None


def toggle_teacher_dashboard_assignment(teacher_id, item_id):
    """Flip an added assignment between 'To Check' and 'Checked'."""
    prefs = get_teacher_prefs(teacher_id)
    items = prefs.get("added_assignments", [])
    for item in items:
        if item["id"] == item_id:
            item["done"] = not item.get("done", False)
            if item["done"] and item.get("total_to_check", 0) > 0:
                item["checked_count"] = item["total_to_check"]
    storage.update("teacher_prefs", prefs["id"], {"added_assignments": items})


def step_teacher_dashboard_assignment(teacher_id, item_id, delta=1):
    """Increment the number of checked submissions on an added assignment."""
    prefs = get_teacher_prefs(teacher_id)
    items = prefs.get("added_assignments", [])
    for item in items:
        if item["id"] == item_id:
            total = item.get("total_to_check", 0)
            new_val = max(0, item.get("checked_count", 0) + delta)
            if total > 0:
                new_val = min(total, new_val)
                item["done"] = new_val >= total
            item["checked_count"] = new_val
    storage.update("teacher_prefs", prefs["id"], {"added_assignments": items})


def remove_teacher_dashboard_assignment(teacher_id, item_id):
    """Remove an assignment-to-check item from the teacher's dashboard."""
    prefs = get_teacher_prefs(teacher_id)
    items = [i for i in prefs.get("added_assignments", []) if i["id"] != item_id]
    storage.update("teacher_prefs", prefs["id"], {"added_assignments": items})


def add_teacher_check_item(teacher_id, title, category="Assignment to Check", target=""):
    """Add a custom 'Class to Check', 'Assignment to Check', or task note to the teacher's dashboard."""
    title = utils.clean(title, 140)
    if not title:
        return "Please enter a task description."
    prefs = get_teacher_prefs(teacher_id)
    items = prefs.get("check_items", [])
    valid_cats = ("Assignment to Check", "Class to Check", "Lesson Prep", "Student Follow-up", "Note")
    items.append({
        "id": storage.new_id("chk"),
        "title": title,
        "category": category if category in valid_cats else "Assignment to Check",
        "target": utils.clean(target, 80),
        "done": False,
        "created_at": utils.now_iso(),
    })
    storage.update("teacher_prefs", prefs["id"], {"check_items": items})
    return None


def toggle_teacher_check_item(teacher_id, item_id):
    """Flip the done/undone state of a dashboard check item."""
    prefs = get_teacher_prefs(teacher_id)
    items = prefs.get("check_items", [])
    for item in items:
        if item["id"] == item_id:
            item["done"] = not item.get("done", False)
    storage.update("teacher_prefs", prefs["id"], {"check_items": items})


def delete_teacher_check_item(teacher_id, item_id):
    """Remove a check item from the teacher's dashboard."""
    prefs = get_teacher_prefs(teacher_id)
    items = [i for i in prefs.get("check_items", []) if i["id"] != item_id]
    storage.update("teacher_prefs", prefs["id"], {"check_items": items})


def set_pinned_assignments(teacher_id, assignment_ids):
    """Save which specific assignments the teacher wants pinned to their dashboard."""
    prefs = get_teacher_prefs(teacher_id)
    storage.update("teacher_prefs", prefs["id"], {"pinned_assignment_ids": list(dict.fromkeys(assignment_ids))})


def add_teacher_widget(teacher_id, widget_key):
    """Explicitly add a live LMS widget block to the teacher's dashboard."""
    if widget_key not in TEACHER_WIDGETS:
        return "Invalid widget."
    prefs = get_teacher_prefs(teacher_id)
    widgets = list(dict.fromkeys(prefs.get("widgets", []) + [widget_key]))
    storage.update("teacher_prefs", prefs["id"], {"widgets": widgets})
    return None


def remove_teacher_widget(teacher_id, widget_key):
    """Remove a live LMS widget block from the teacher's dashboard."""
    prefs = get_teacher_prefs(teacher_id)
    widgets = [w for w in prefs.get("widgets", []) if w != widget_key]
    storage.update("teacher_prefs", prefs["id"], {"widgets": widgets})


def clear_teacher_dashboard(teacher_id):
    """Clear all items from the teacher's dashboard so she can start fresh."""
    prefs = get_teacher_prefs(teacher_id)
    storage.update("teacher_prefs", prefs["id"], {
        "widgets": [],
        "added_classes": [],
        "added_assignments": [],
        "pinned_assignment_ids": [],
        "check_items": [],
        "focus_note": "",
    })


# ==========================================================================
# Creative Features: Class Climate Report & Student Milestones
# ==========================================================================
def class_climate_report(subjects):
    """Synthesize NovaPulse confidence, attendance, and grades into a creative
    monochrome Class Climate forecast for each subject."""
    reports = []
    for s in subjects:
        students = school.class_students(s["class_id"])
        pulse_rows = [r for r in tracking.pulse_summary(s["id"]) if r["responses"]]
        avg_pulse = utils.mean([r["average"] for r in pulse_rows])
        avg_grade = utils.mean([tracking.subject_average(stu["id"], s["id"]) for stu in students])
        avg_att = utils.mean([tracking.attendance_summary(stu["id"], [s["id"]])["percent"] for stu in students])
        ungraded, _ = coursework.grading_queue([s["id"]])

        if (avg_pulse is not None and avg_pulse < 2.6) or (avg_grade is not None and avg_grade < 65) or (avg_att is not None and avg_att < 82):
            weather = "▲ Storm Watch"
            summary = "Needs review — check low-confidence lessons or missing work."
        elif (avg_pulse is not None and avg_pulse < 3.4) or len(ungraded) >= 3:
            weather = "◐ Partly Cloudy"
            summary = "Steady overall, with a few topics or submissions to check."
        else:
            weather = "● Clear Skies"
            summary = "High confidence, strong attendance, and on-track grades."

        reports.append({
            "subject_id": s["id"],
            "subject": school.subject_label(s),
            "weather": weather,
            "summary": summary,
            "pulse": f"{avg_pulse:.1f}/5" if avg_pulse else "—",
            "average": utils.fmt_pct(avg_grade),
            "attendance": utils.fmt_pct(avg_att),
            "to_grade": len(ungraded),
        })
    return reports


def student_milestones(student_id):
    """Creative achievement badges earned from the student's real LMS activity."""
    subjects = school.subjects_for_student(student_id)
    subject_ids = [s["id"] for s in subjects]
    items = tracking.grade_items_for_student(student_id, subject_ids)
    overall = utils.mean([i["percent"] for i in items])
    att = tracking.attendance_summary(student_id, subject_ids)
    pulse_votes = storage.find("pulse", student_id=student_id)

    on_time_subs = [
        sub for sub in storage.find("submissions", student_id=student_id)
        if not sub.get("offline") and storage.get("assignments", sub["assignment_id"])
        and not coursework.is_late(sub, storage.get("assignments", sub["assignment_id"]))
    ]
    quiz_aces = [i for i in items if i["kind"] == "Quiz" and (i["percent"] or 0) >= 85]

    badges = []
    if len(on_time_subs) >= 2:
        badges.append(("★ On-Time Streak", f"{len(on_time_subs)} assignments turned in before the deadline"))
    if quiz_aces:
        badges.append(("◆ Quiz Ace", f"Scored 85%+ on {len(quiz_aces)} quiz(zes)"))
    if len(pulse_votes) >= 3:
        badges.append(("● Pulse Contributor", f"Rated {len(pulse_votes)} lessons to help guide class reviews"))
    if overall is not None and overall >= 85:
        badges.append(("▲ Honor Roll", f"Maintaining a {overall:.1f}% overall average"))
    if att["percent"] is not None and att["percent"] >= 90:
        badges.append(("■ Attendance Star", f"{att['percent']:.0f}% attendance rate across subjects"))
    if not badges:
        badges.append(("○ Rising Scholar", "Complete your next assignment or rate a lesson to unlock badges!"))
    return badges


def daily_concept_spotlight(student_id):
    """Pick one bite-sized lesson spotlight for the student's dashboard."""
    subjects = school.subjects_for_student(student_id)
    lessons = coursework.lessons_for_subjects([s["id"] for s in subjects])
    if not lessons:
        return None
    idx = datetime.now().timetuple().tm_yday % len(lessons)
    les = lessons[idx]
    return {
        "title": les["title"],
        "topic": les["topic"],
        "subject": school.subject_label(les["subject_id"]),
        "snippet": les["content"][:280] + ("…" if len(les["content"]) > 280 else ""),
    }


