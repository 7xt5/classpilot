"""
tracking.py - Gradebook, attendance and ClassPulse.

Grade rule (simple and transparent for teachers and parents):
  * Every graded assignment and every completed quiz becomes one "grade item"
    with a percentage (late penalties already applied).
  * A subject average is the plain average of those percentages.
"""

from datetime import date

from classpilot import coursework, school, storage, utils

ATTENDANCE_STATUSES = ["Present", "Late", "Absent", "Excused"]

CONFIDENCE_LABELS = {
    1: "😟 1 - I'm lost",
    2: "😕 2 - Unsure",
    3: "😐 3 - Getting there",
    4: "🙂 4 - Confident",
    5: "😎 5 - I could teach it",
}


# ==========================================================================
# Grades
# ==========================================================================
def grade_items_for_student(student_id, subject_ids=None):
    """All graded work for a student, oldest first.

    Each item: date, subject_id, subject, title, kind, score, max, percent, late.
    """
    if subject_ids is None:
        subject_ids = [s["id"] for s in school.subjects_for_student(student_id)]
    items = []
    for assignment in coursework.assignments_for_subjects(subject_ids):
        submission = coursework.submission_for(assignment["id"], student_id)
        if submission and submission.get("score") is not None:
            items.append({
                "date": assignment["due"],
                "subject_id": assignment["subject_id"],
                "subject": school.subject_label(assignment["subject_id"]),
                "title": assignment["title"],
                "kind": "Assignment",
                "score": coursework.effective_score(submission, assignment),
                "max": assignment["max_points"],
                "percent": coursework.assignment_percent(submission, assignment),
                "late": coursework.is_late(submission, assignment),
                "feedback": submission.get("feedback", ""),
            })
    for quiz in coursework.quizzes_for_subjects(subject_ids, published_only=True):
        attempt = coursework.best_attempt(quiz["id"], student_id)
        if attempt:
            items.append({
                "date": quiz["due"],
                "subject_id": quiz["subject_id"],
                "subject": school.subject_label(quiz["subject_id"]),
                "title": quiz["title"],
                "kind": "Quiz",
                "score": attempt["score"],
                "max": attempt["max_score"],
                "percent": attempt["percent"],
                "late": False,
                "feedback": "",
            })
    return sorted(items, key=lambda i: i["date"])


def subject_average(student_id, subject_id):
    return utils.mean([i["percent"] for i in grade_items_for_student(student_id, [subject_id])])


def overall_average(student_id):
    return utils.mean([i["percent"] for i in grade_items_for_student(student_id)])


def grade_trend(items):
    """Compare the older half of grades with the newer half.

    Returns ``(earlier_average, recent_average, change)`` or ``None`` when
    there are fewer than 4 grades (not enough to see a trend).
    """
    percents = [i["percent"] for i in items if i["percent"] is not None]
    if len(percents) < 4:
        return None
    half = len(percents) // 2
    earlier, recent = utils.mean(percents[:half]), utils.mean(percents[half:])
    return earlier, recent, round(recent - earlier, 1)


def gradebook_rows(subject_id):
    """One row per student with every graded item of a subject.

    Returns ``(columns, rows)``: columns is a list of (key, label) pairs and
    each row is a dictionary ready to show in a table.
    """
    subject = school.get_subject(subject_id)
    if not subject:
        return [], []
    settings = storage.load_settings()
    assignments = coursework.assignments_for_subjects([subject_id])
    quizzes = coursework.quizzes_for_subjects([subject_id], published_only=True)
    columns = [(a["id"], f"📝 {a['title']}") for a in assignments]
    columns += [(q["id"], f"❓ {q['title']}") for q in quizzes]
    rows = []
    for student in school.class_students(subject["class_id"]):
        row = {"Student": student["full_name"], "_id": student["id"]}
        for assignment in assignments:
            submission = coursework.submission_for(assignment["id"], student["id"])
            pct = coursework.assignment_percent(submission, assignment)
            row[assignment["id"]] = pct
        for quiz in quizzes:
            attempt = coursework.best_attempt(quiz["id"], student["id"])
            row[quiz["id"]] = attempt["percent"] if attempt else None
        average = subject_average(student["id"], subject_id)
        row["Average"] = average
        row["Grade"] = utils.letter_grade(average, settings["grade_scale"])
        rows.append(row)
    return columns, rows


# ==========================================================================
# Attendance
# ==========================================================================
def get_attendance(subject_id, day):
    found = storage.find("attendance", subject_id=subject_id, date=str(day))
    return found[0] if found else None


def attendance_sessions(subject_id):
    return sorted(storage.find("attendance", subject_id=subject_id), key=lambda s: s["date"])


def save_attendance(teacher, subject_id, day, records):
    """Save (or overwrite) attendance for one subject on one day.

    ``records`` maps student id -> status. Returns an error or ``None``.
    """
    subject = school.get_subject(subject_id)
    if not subject:
        return "Subject not found."
    if teacher["role"] != "admin" and not school.teacher_owns_subject(teacher["id"], subject_id):
        return "You can only take attendance for your own subjects."
    if day > date.today():
        return "Attendance cannot be recorded for a future date."
    roster = {s["id"] for s in school.class_students(subject["class_id"])}
    clean_records = {}
    for student_id, status in records.items():
        if student_id not in roster:
            continue
        if status not in ATTENDANCE_STATUSES:
            return f"Invalid attendance status: {status}"
        clean_records[student_id] = status
    if not clean_records:
        return "There are no students to record."
    existing = get_attendance(subject_id, day)
    if existing:
        storage.update("attendance", existing["id"], {
            "records": clean_records, "taken_by": teacher["id"], "updated_at": utils.now_iso()})
    else:
        storage.insert("attendance", {
            "id": storage.new_id("atd"), "subject_id": subject_id, "date": str(day),
            "records": clean_records, "taken_by": teacher["id"], "updated_at": utils.now_iso(),
        })
    return None


def attendance_summary(student_id, subject_ids=None):
    """Counts of each status and the attendance percentage.

    Present and Late count as attended. Excused days are left out of the
    calculation completely, so they never hurt a student's percentage.
    """
    counts = {status: 0 for status in ATTENDANCE_STATUSES}
    for session in storage.load("attendance"):
        if subject_ids is not None and session["subject_id"] not in subject_ids:
            continue
        status = session["records"].get(student_id)
        if status in counts:
            counts[status] += 1
    attended = counts["Present"] + counts["Late"]
    possible = attended + counts["Absent"]
    counts["sessions"] = possible + counts["Excused"]
    counts["percent"] = utils.percent(attended, possible) if possible else None
    return counts


def attendance_by_date(subject_id):
    """Percentage of the class attending each recorded day (for charts)."""
    result = []
    for session in attendance_sessions(subject_id):
        statuses = [s for s in session["records"].values() if s != "Excused"]
        attended = sum(1 for s in statuses if s in ("Present", "Late"))
        result.append({"date": session["date"], "percent": utils.percent(attended, len(statuses)) or 0})
    return result


# ==========================================================================
# ClassPulse - private confidence ratings per lesson
# ==========================================================================
def my_pulse(student_id, lesson_id):
    found = storage.find("pulse", student_id=student_id, lesson_id=lesson_id)
    return found[0] if found else None


def set_pulse(student, lesson_id, rating, note=""):
    """Save a student's confidence (1-5) for a lesson. Only aggregated
    results are ever shown to teachers, so students can be honest."""
    lesson = storage.get("lessons", lesson_id)
    if not lesson:
        return "Lesson not found."
    if student["role"] != "student" or not school.student_in_subject(student["id"], lesson["subject_id"]):
        return "You are not enrolled in this subject."
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return "Please choose a rating."
    if rating not in CONFIDENCE_LABELS:
        return "Rating must be between 1 and 5."
    note = utils.clean(note, 300)
    existing = my_pulse(student["id"], lesson_id)
    if existing:
        storage.update("pulse", existing["id"], {"rating": rating, "note": note, "updated_at": utils.now_iso()})
    else:
        storage.insert("pulse", {
            "id": storage.new_id("pls"), "lesson_id": lesson_id, "subject_id": lesson["subject_id"],
            "student_id": student["id"], "rating": rating, "note": note, "updated_at": utils.now_iso(),
        })
    return None


def pulse_summary(subject_id):
    """Class-wide confidence for every lesson of a subject.

    Names are never included - teachers see averages, the spread of ratings
    and anonymous notes (shuffled into alphabetical order).
    """
    settings = storage.load_settings()
    subject = school.get_subject(subject_id)
    if not subject:
        return []
    class_size = len(school.class_students(subject["class_id"]))
    ratings = storage.find("pulse", subject_id=subject_id)
    rows = []
    for lesson in coursework.lessons_for_subjects([subject_id]):
        lesson_ratings = [r for r in ratings if r["lesson_id"] == lesson["id"]]
        values = [r["rating"] for r in lesson_ratings]
        distribution = {level: values.count(level) for level in range(1, 6)}
        average = utils.mean(values)
        low_share = utils.percent(distribution[1] + distribution[2], len(values)) if values else None
        flagged = bool(values) and (average < settings["pulse_low_threshold"] or (low_share or 0) >= 40)
        rows.append({
            "lesson_id": lesson["id"],
            "topic": lesson["topic"],
            "lesson": lesson["title"],
            "responses": len(values),
            "class_size": class_size,
            "response_rate": utils.percent(len(values), class_size) if class_size else None,
            "average": average,
            "distribution": distribution,
            "low_share": low_share,
            "flagged": flagged,
            "notes": sorted(r["note"] for r in lesson_ratings if r.get("note")),
        })
    return rows
