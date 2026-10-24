# =============================================================================
# STUDY FILE: 04_coursework_and_quizzes.py (Source: classpilot/coursework.py)
# EXPLANATION: COURSEWORK & AUTO-GRADED QUIZZES: Lesson publishing, assignment submissions, automatic late-penalty calculation, and instant multiple-choice quiz grading.
# =============================================================================

"""
coursework.py - Lessons, assignments, submissions and quizzes.

Permission rules enforced here (not only in the UI):
  * Only the teacher who owns a subject (or an admin) can change its coursework.
  * Only students in the subject's class can submit work or take quizzes.
"""

from datetime import datetime

from classpilot import school, storage, utils


def _can_edit_subject(user, subject_id):
    """Teachers may only edit their own subjects; admins may edit any."""
    if user["role"] == "admin":
        return school.get_subject(subject_id) is not None
    return user["role"] == "teacher" and school.teacher_owns_subject(user["id"], subject_id)


# ==========================================================================
# Lesson Hub
# ==========================================================================
def lessons_for_subjects(subject_ids):
    lessons = [l for l in storage.load("lessons") if l["subject_id"] in subject_ids]
    return sorted(lessons, key=lambda l: (l["topic"].lower(), l["created_at"]))


def parse_resources(text):
    """Turn lines like 'Khan Academy | https://...' into resource dicts.

    Returns ``(resources, error)``.
    """
    resources = []
    for number, line in enumerate((text or "").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            label, url = [part.strip() for part in line.split("|", 1)]
        else:
            label, url = line, line
        if not utils.is_valid_url(url):
            return [], f"Resource line {number} needs a link starting with http:// or https://"
        resources.append({"label": label or url, "url": url})
    return resources, None


def resources_to_text(resources):
    return "\n".join(f"{r['label']} | {r['url']}" for r in resources)


def save_lesson(user, subject_id, topic, title, content, resources_text,
                uploaded_files=None, lesson_id=None):
    """Create a lesson (or update it when ``lesson_id`` is given)."""
    if not _can_edit_subject(user, subject_id):
        return None, "You can only add lessons to your own subjects."
    topic, title = utils.clean(topic, 80), utils.clean(title, 120)
    content = utils.clean(content, 20000)
    if not topic or not title:
        return None, "Topic and title are required."
    resources, error = parse_resources(resources_text)
    if error:
        return None, error

    new_files = []
    for uploaded in uploaded_files or []:
        try:
            new_files.append(storage.save_upload(uploaded, "lessons"))
        except ValueError as exc:
            for item in new_files:  # roll back files saved so far
                storage.delete_upload(item["path"])
            return None, f"{uploaded.name}: {exc}"

    if lesson_id:
        existing = storage.get("lessons", lesson_id)
        if not existing or not _can_edit_subject(user, existing["subject_id"]):
            return None, "Lesson not found."
        lesson = storage.update("lessons", lesson_id, {
            "subject_id": subject_id, "topic": topic, "title": title, "content": content,
            "resources": resources, "files": existing.get("files", []) + new_files,
            "updated_at": utils.now_iso(),
        })
        storage.delete_where("pulse", lambda p: p["lesson_id"] == lesson_id and p["subject_id"] != subject_id)
        return lesson, None

    lesson = {
        "id": storage.new_id("les"),
        "subject_id": subject_id,
        "topic": topic,
        "title": title,
        "content": content,
        "resources": resources,
        "files": new_files,
        "created_by": user["id"],
        "created_at": utils.now_iso(),
        "updated_at": utils.now_iso(),
    }
    return storage.insert("lessons", lesson), None


def remove_lesson_file(user, lesson_id, file_path):
    lesson = storage.get("lessons", lesson_id)
    if not lesson or not _can_edit_subject(user, lesson["subject_id"]):
        return "Lesson not found."
    storage.delete_upload(file_path)
    storage.update("lessons", lesson_id, {
        "files": [f for f in lesson.get("files", []) if f["path"] != file_path]})
    return None


def delete_lesson(user, lesson_id):
    lesson = storage.get("lessons", lesson_id)
    if not lesson or not _can_edit_subject(user, lesson["subject_id"]):
        return "Lesson not found."
    for item in lesson.get("files", []):
        storage.delete_upload(item["path"])
    storage.delete_where("pulse", lambda p: p["lesson_id"] == lesson_id)
    storage.delete("lessons", lesson_id)
    return None


# ==========================================================================
# Assignments
# ==========================================================================
def assignments_for_subjects(subject_ids):
    items = [a for a in storage.load("assignments") if a["subject_id"] in subject_ids]
    return sorted(items, key=lambda a: a["due"])


def save_assignment(user, subject_id, title, description, due_iso, max_points,
                    allow_late=True, late_penalty=10, assignment_id=None):
    """Create or update an assignment. Returns ``(assignment, error)``."""
    if not _can_edit_subject(user, subject_id):
        return None, "You can only manage assignments for your own subjects."
    title, description = utils.clean(title, 120), utils.clean(description, 10000)
    due = utils.parse_dt(due_iso)
    if not title:
        return None, "Title is required."
    if not due:
        return None, "Please choose a valid due date and time."
    try:
        max_points = int(max_points)
        late_penalty = int(late_penalty)
    except (TypeError, ValueError):
        return None, "Points and late penalty must be whole numbers."
    if not 1 <= max_points <= 1000:
        return None, "Maximum points must be between 1 and 1000."
    if not 0 <= late_penalty <= 100:
        return None, "Late penalty must be between 0 and 100 percent."

    fields = {
        "subject_id": subject_id, "title": title, "description": description,
        "due": due.isoformat(timespec="minutes"), "max_points": max_points,
        "allow_late": bool(allow_late), "late_penalty": late_penalty,
    }
    if assignment_id:
        existing = storage.get("assignments", assignment_id)
        if not existing or not _can_edit_subject(user, existing["subject_id"]):
            return None, "Assignment not found."
        if existing["subject_id"] != subject_id and submissions_for_assignment(assignment_id):
            return None, "This assignment already has submissions, so its subject cannot change."
        graded = [s for s in submissions_for_assignment(assignment_id) if s.get("score") is not None]
        if any(s["score"] > max_points for s in graded):
            return None, "Some existing scores are higher than the new maximum points."
        return storage.update("assignments", assignment_id, fields), None

    if due < datetime.now():
        return None, "The due date must be in the future."
    fields.update({
        "id": storage.new_id("asg"),
        "created_by": user["id"],
        "created_at": utils.now_iso(),
    })
    return storage.insert("assignments", fields), None


def delete_assignment(user, assignment_id):
    assignment = storage.get("assignments", assignment_id)
    if not assignment or not _can_edit_subject(user, assignment["subject_id"]):
        return "Assignment not found."
    for sub in submissions_for_assignment(assignment_id):
        if sub.get("file"):
            storage.delete_upload(sub["file"]["path"])
    storage.delete_where("submissions", lambda s: s["assignment_id"] == assignment_id)
    storage.delete("assignments", assignment_id)
    return None


def submissions_for_assignment(assignment_id):
    return storage.find("submissions", assignment_id=assignment_id)


def submission_for(assignment_id, student_id):
    found = storage.find("submissions", assignment_id=assignment_id, student_id=student_id)
    return found[0] if found else None


def is_late(submission, assignment):
    """Late = submitted after the deadline (work graded in class is never late)."""
    if not submission or submission.get("offline"):
        return False
    submitted, due = utils.parse_dt(submission.get("submitted_at")), utils.parse_dt(assignment["due"])
    return bool(submitted and due and submitted > due)


def effective_score(submission, assignment):
    """Score after the late penalty is applied (``None`` if not graded)."""
    if not submission or submission.get("score") is None:
        return None
    score = float(submission["score"])
    if is_late(submission, assignment):
        score *= (100 - assignment.get("late_penalty", 0)) / 100
    return round(score, 2)


def assignment_percent(submission, assignment):
    return utils.percent(effective_score(submission, assignment), assignment["max_points"])


def assignment_status(assignment, student_id, submission="lookup"):
    """One-word status of an assignment for a student."""
    if submission == "lookup":
        submission = submission_for(assignment["id"], student_id)
    if submission:
        if submission.get("score") is not None:
            return "Graded"
        return "Submitted late" if is_late(submission, assignment) else "Submitted"
    return "Missing" if utils.is_past(assignment["due"]) else "Not submitted"


def submit_assignment(student, assignment_id, text, link, uploaded_file=None):
    """Hand in (or re-submit) an assignment. Returns ``(submission, error)``."""
    assignment = storage.get("assignments", assignment_id)
    if not assignment:
        return None, "Assignment not found."
    if student["role"] != "student" or not school.student_in_subject(student["id"], assignment["subject_id"]):
        return None, "You are not enrolled in this subject."
    text, link = utils.clean(text, 20000), utils.clean(link, 500)
    existing = submission_for(assignment_id, student["id"])
    if existing and existing.get("score") is not None:
        return None, "This work has already been graded and can no longer be changed."
    if utils.is_past(assignment["due"]) and not assignment.get("allow_late", True):
        return None, "The deadline has passed and late work is not accepted for this assignment."
    if link and not utils.is_valid_url(link):
        return None, "The link must start with http:// or https://"
    if not text and not link and not uploaded_file and not (existing and existing.get("file")):
        return None, "Please write an answer, add a link, or attach a file."

    file_info = existing.get("file") if existing else None
    if uploaded_file is not None:
        try:
            new_file = storage.save_upload(uploaded_file, "submissions")
        except ValueError as exc:
            return None, str(exc)
        if file_info:
            storage.delete_upload(file_info["path"])
        file_info = new_file

    fields = {
        "text": text, "link": link, "file": file_info,
        "submitted_at": utils.now_iso(), "offline": False,
    }
    if existing:
        fields["revision"] = existing.get("revision", 1) + 1
        return storage.update("submissions", existing["id"], fields), None
    fields.update({
        "id": storage.new_id("smb"),
        "assignment_id": assignment_id,
        "student_id": student["id"],
        "score": None, "feedback": "", "graded_at": None, "revision": 1,
    })
    return storage.insert("submissions", fields), None


def grade_student(teacher, assignment_id, student_id, score, feedback=""):
    """Grade one student's work. If they did not submit online (e.g. paper
    work handed in class) an 'offline' submission record is created."""
    assignment = storage.get("assignments", assignment_id)
    if not assignment or not _can_edit_subject(teacher, assignment["subject_id"]):
        return "Assignment not found."
    if not school.student_in_subject(student_id, assignment["subject_id"]):
        return "This student is not in the class."
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "Score must be a number."
    if not 0 <= score <= assignment["max_points"]:
        return f"Score must be between 0 and {assignment['max_points']}."
    score = int(score) if score == int(score) else round(score, 2)
    feedback = utils.clean(feedback, 5000)
    existing = submission_for(assignment_id, student_id)
    changes = {"score": score, "feedback": feedback, "graded_at": utils.now_iso(),
               "graded_by": teacher["id"]}
    if existing:
        storage.update("submissions", existing["id"], changes)
    else:
        changes.update({
            "id": storage.new_id("smb"), "assignment_id": assignment_id,
            "student_id": student_id, "text": "", "link": "", "file": None,
            "submitted_at": utils.now_iso(), "offline": True, "revision": 1,
        })
        storage.insert("submissions", changes)
    return None


def clear_grade(teacher, assignment_id, student_id):
    """Remove a grade (offline-only records are deleted completely)."""
    assignment = storage.get("assignments", assignment_id)
    if not assignment or not _can_edit_subject(teacher, assignment["subject_id"]):
        return "Assignment not found."
    existing = submission_for(assignment_id, student_id)
    if not existing:
        return None
    if existing.get("offline"):
        storage.delete("submissions", existing["id"])
    else:
        storage.update("submissions", existing["id"], {"score": None, "feedback": "", "graded_at": None})
    return None


def grading_queue(subject_ids):
    """Submitted but not yet graded work, oldest first."""
    assignments = {a["id"]: a for a in assignments_for_subjects(subject_ids)}
    queue = [s for s in storage.load("submissions")
             if s["assignment_id"] in assignments and s.get("score") is None]
    return sorted(queue, key=lambda s: s["submitted_at"]), assignments


# ==========================================================================
# Quizzes (multiple choice, graded automatically)
# ==========================================================================
def quizzes_for_subjects(subject_ids, published_only=False):
    items = [q for q in storage.load("quizzes") if q["subject_id"] in subject_ids]
    if published_only:
        items = [q for q in items if q.get("published")]
    return sorted(items, key=lambda q: q["due"])


def quiz_max_score(quiz):
    return sum(q.get("points", 1) for q in quiz.get("questions", []))


def save_quiz(user, subject_id, title, description, due_iso, attempts_allowed=1,
              show_answers=True, quiz_id=None):
    """Create or update quiz settings (questions are added separately)."""
    if not _can_edit_subject(user, subject_id):
        return None, "You can only manage quizzes for your own subjects."
    title, description = utils.clean(title, 120), utils.clean(description, 2000)
    due = utils.parse_dt(due_iso)
    if not title:
        return None, "Quiz title is required."
    if not due:
        return None, "Please choose a valid closing date and time."
    try:
        attempts_allowed = int(attempts_allowed)
    except (TypeError, ValueError):
        return None, "Attempts must be a whole number."
    if not 1 <= attempts_allowed <= 10:
        return None, "Attempts allowed must be between 1 and 10."
    fields = {
        "subject_id": subject_id, "title": title, "description": description,
        "due": due.isoformat(timespec="minutes"), "attempts_allowed": attempts_allowed,
        "show_answers": bool(show_answers),
    }
    if quiz_id:
        existing = storage.get("quizzes", quiz_id)
        if not existing or not _can_edit_subject(user, existing["subject_id"]):
            return None, "Quiz not found."
        if existing["subject_id"] != subject_id and attempts_for(quiz_id):
            return None, "Students have already taken this quiz, so its subject cannot change."
        return storage.update("quizzes", quiz_id, fields), None
    if due < datetime.now():
        return None, "The closing date must be in the future."
    fields.update({
        "id": storage.new_id("quiz"), "questions": [], "published": False,
        "created_by": user["id"], "created_at": utils.now_iso(),
    })
    return storage.insert("quizzes", fields), None


def add_question(user, quiz_id, text, raw_options, correct_index, points=1):
    """Add a multiple-choice question.

    ``raw_options`` is the list typed by the teacher (blanks are ignored) and
    ``correct_index`` points into that raw list.
    """
    quiz = storage.get("quizzes", quiz_id)
    if not quiz or not _can_edit_subject(user, quiz["subject_id"]):
        return "Quiz not found."
    if attempts_for(quiz_id):
        return "Students have already taken this quiz, so questions are locked."
    text = utils.clean(text, 1000)
    if not text:
        return "Question text is required."
    if not 0 <= correct_index < len(raw_options) or not utils.clean(raw_options[correct_index]):
        return "The correct answer cannot be an empty option."
    correct_text = utils.clean(raw_options[correct_index], 300)
    options = [utils.clean(o, 300) for o in raw_options if utils.clean(o)]
    if len(options) < 2:
        return "Please provide at least two answer options."
    if len({o.lower() for o in options}) != len(options):
        return "Answer options must all be different."
    try:
        points = int(points)
    except (TypeError, ValueError):
        return "Points must be a whole number."
    if not 1 <= points <= 100:
        return "Points must be between 1 and 100."
    question = {
        "id": storage.new_id("q"), "text": text, "options": options,
        "answer": options.index(correct_text), "points": points,
    }
    storage.update("quizzes", quiz_id, {"questions": quiz.get("questions", []) + [question]})
    return None


def delete_question(user, quiz_id, question_id):
    quiz = storage.get("quizzes", quiz_id)
    if not quiz or not _can_edit_subject(user, quiz["subject_id"]):
        return "Quiz not found."
    if attempts_for(quiz_id):
        return "Students have already taken this quiz, so questions are locked."
    remaining = [q for q in quiz.get("questions", []) if q["id"] != question_id]
    changes = {"questions": remaining}
    if not remaining:
        changes["published"] = False  # an empty quiz cannot stay published
    storage.update("quizzes", quiz_id, changes)
    return None


def set_published(user, quiz_id, published):
    quiz = storage.get("quizzes", quiz_id)
    if not quiz or not _can_edit_subject(user, quiz["subject_id"]):
        return "Quiz not found."
    if published and not quiz.get("questions"):
        return "Add at least one question before publishing."
    storage.update("quizzes", quiz_id, {"published": bool(published)})
    return None


def delete_quiz(user, quiz_id):
    quiz = storage.get("quizzes", quiz_id)
    if not quiz or not _can_edit_subject(user, quiz["subject_id"]):
        return "Quiz not found."
    storage.delete_where("quiz_attempts", lambda a: a["quiz_id"] == quiz_id)
    storage.delete("quizzes", quiz_id)
    return None


def attempts_for(quiz_id, student_id=None):
    attempts = storage.find("quiz_attempts", quiz_id=quiz_id)
    if student_id:
        attempts = [a for a in attempts if a["student_id"] == student_id]
    return sorted(attempts, key=lambda a: a["submitted_at"])


def best_attempt(quiz_id, student_id):
    attempts = attempts_for(quiz_id, student_id)
    return max(attempts, key=lambda a: a["score"]) if attempts else None


def grade_answers(quiz, answers):
    """Automatically mark a quiz.

    ``answers`` maps question id -> chosen option index (or ``None``).
    Returns ``(score, max_score, results)`` where results explains each question.
    """
    score, results = 0, []
    for question in quiz.get("questions", []):
        chosen = answers.get(question["id"])
        correct = chosen == question["answer"]
        if correct:
            score += question.get("points", 1)
        results.append({"question_id": question["id"], "chosen": chosen, "correct": correct})
    return score, quiz_max_score(quiz), results


def quiz_status(quiz, student_id):
    attempts = attempts_for(quiz["id"], student_id)
    if attempts:
        return "Completed"
    return "Missed" if utils.is_past(quiz["due"]) else "Open"


def submit_quiz(student, quiz_id, answers):
    """Record a quiz attempt and grade it. Returns ``(attempt, error)``."""
    quiz = storage.get("quizzes", quiz_id)
    if not quiz or not quiz.get("published"):
        return None, "This quiz is not available."
    if student["role"] != "student" or not school.student_in_subject(student["id"], quiz["subject_id"]):
        return None, "You are not enrolled in this subject."
    if utils.is_past(quiz["due"]):
        return None, "This quiz has closed."
    if len(attempts_for(quiz_id, student["id"])) >= quiz.get("attempts_allowed", 1):
        return None, "You have used all your attempts for this quiz."
    unanswered = [q for q in quiz["questions"] if answers.get(q["id"]) is None]
    if unanswered:
        return None, f"Please answer all questions ({len(unanswered)} left)."
    score, max_score, results = grade_answers(quiz, answers)
    attempt = {
        "id": storage.new_id("att"),
        "quiz_id": quiz_id,
        "student_id": student["id"],
        "answers": {qid: idx for qid, idx in answers.items()},
        "score": score,
        "max_score": max_score,
        "percent": utils.percent(score, max_score),
        "submitted_at": utils.now_iso(),
    }
    return storage.insert("quiz_attempts", attempt), None


def quiz_item_analysis(quiz):
    """For each question: how many students got it right (based on each
    student's best attempt). Helps teachers spot confusing questions."""
    best = {}
    for attempt in attempts_for(quiz["id"]):
        current = best.get(attempt["student_id"])
        if not current or attempt["score"] > current["score"]:
            best[attempt["student_id"]] = attempt
    rows = []
    for number, question in enumerate(quiz.get("questions", []), start=1):
        chosen = [a["answers"].get(question["id"]) for a in best.values()]
        right = sum(1 for c in chosen if c == question["answer"])
        wrong = [c for c in chosen if c is not None and c != question["answer"]]
        common_wrong = max(set(wrong), key=wrong.count) if wrong else None
        rows.append({
            "number": number,
            "question": question["text"],
            "correct_answer": question["options"][question["answer"]],
            "responses": len(chosen),
            "percent_correct": utils.percent(right, len(chosen)) if chosen else None,
            "common_wrong": question["options"][common_wrong] if common_wrong is not None
            and common_wrong < len(question["options"]) else "—",
        })
    return rows
