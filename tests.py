"""
tests.py - Automated verification of Novarix's backend and Streamlit views.

Run with:   python tests.py
"""

import os
import tempfile
from datetime import date, timedelta

# Use an isolated temporary data folder before importing classpilot.
TEMP_DIR = tempfile.mkdtemp(prefix="classpilot_test_")
os.environ["NOVARIX_DATA_DIR"] = TEMP_DIR

from streamlit.testing.v1 import AppTest

from classpilot import auth, coursework, insights, school, seed, storage, tracking, utils


def test_backend_workflows():
    print("1. Seeding demo data...")
    seed.seed_demo_data()
    assert not storage.is_empty(), "Database should not be empty after seeding"

    # ---- Authentication & Lockout --------------------------------------
    print("2. Testing authentication & password security...")
    admin, err = auth.authenticate("admin", "Admin@123")
    assert err is None and admin["role"] == "admin"

    bad_user, err = auth.authenticate("admin", "wrong-pass")
    assert bad_user is None and err is not None

    teacher, err = auth.authenticate("sara.khan", "Teacher@123")
    assert err is None and teacher["role"] == "teacher"

    student, err = auth.authenticate("ali.raza", "Student@123")
    assert err is None and student["role"] == "student"

    # ---- Users, Classes, Subjects --------------------------------------
    print("3. Testing school management (users, classes, subjects)...")
    new_stu, err = school.create_user("test.student", "Test Student", "test@riverside.edu", "student", "Pass@1234")
    assert err is None and new_stu["username"] == "test.student"

    # Prevent self-deletion by admin
    assert school.delete_user(admin["id"], admin["id"]) is not None
    assert school.delete_user(admin["id"], new_stu["id"]) is None

    # ---- Announcements & Read Receipts ---------------------------------
    print("4. Testing announcements & read tracking...")
    ann, err = school.create_announcement(admin, "all", "Welcome Note", "School starts at 8am.", pinned=True, priority="Important")
    assert err is None
    assert school.is_unread(ann, student["id"])
    school.mark_read(ann["id"], student["id"])
    updated_ann = storage.get("announcements", ann["id"])
    assert not school.is_unread(updated_ann, student["id"])

    # ---- Lessons & ClassPulse ------------------------------------------
    print("5. Testing Lesson Hub & ClassPulse...")
    t_subjects = school.subjects_for_teacher(teacher["id"])
    subj_9a = next(s for s in t_subjects if "9" in school.class_name(s["class_id"]))
    lesson, err = coursework.save_lesson(
        teacher, subj_9a["id"], "Algebra", "Inequalities",
        "Solve like equations, flip sign when dividing by a negative.",
        "Khan Academy | https://www.khanacademy.org"
    )
    assert err is None and lesson["title"] == "Inequalities"

    err = tracking.set_pulse(student, lesson["id"], 2, "Flipping the sign was tricky")
    assert err is None
    summary = tracking.pulse_summary(subj_9a["id"])
    lesson_pulse = next(r for r in summary if r["lesson_id"] == lesson["id"])
    assert lesson_pulse["average"] == 2.0 and lesson_pulse["flagged"] is True

    # ---- Assignments, Conflict Detector, Submissions & Grading ---------
    print("6. Testing Assignments, Deadline Conflict Detector & Grading...")
    due_iso = utils.combine(date.today() + timedelta(days=5), utils.now().time().replace(hour=23, minute=59))
    conflict_info = insights.check_conflicts(subj_9a["class_id"], due_iso)
    assert "conflict" in conflict_info and conflict_info["load"] >= 1

    asg, err = coursework.save_assignment(teacher, subj_9a["id"], "Inequalities Homework", "Complete Q1-10", due_iso, 25)
    assert err is None

    sub, err = coursework.submit_assignment(student, asg["id"], "Here are my answers 1-10.", "")
    assert err is None and coursework.assignment_status(asg, student["id"]) == "Submitted"

    err = coursework.grade_student(teacher, asg["id"], student["id"], 22, "Great job!")
    assert err is None and coursework.assignment_status(asg, student["id"]) == "Graded"

    # ---- Quizzes & Auto-Grading ----------------------------------------
    print("7. Testing Quiz Builder & Auto-Grading...")
    quiz, err = coursework.save_quiz(teacher, subj_9a["id"], "Inequalities Mini-Quiz", "Quick check", due_iso, attempts_allowed=2)
    assert err is None
    assert coursework.add_question(teacher, quiz["id"], "Solve x + 2 > 5", ["x > 3", "x < 3", "x > 7", ""], 0, points=2) is None
    assert coursework.set_published(teacher, quiz["id"], True) is None

    q_fresh = storage.get("quizzes", quiz["id"])
    qid = q_fresh["questions"][0]["id"]
    attempt, err = coursework.submit_quiz(student, quiz["id"], {qid: 0})
    assert err is None and attempt["score"] == 2 and attempt["percent"] == 100.0

    # ---- Attendance, Gradebook, Alerts & Search ------------------------
    print("8. Testing Attendance, Gradebook, Early Support Alerts & Search...")
    roster = school.class_students(subj_9a["class_id"])
    records = {s["id"]: "Present" for s in roster}
    assert tracking.save_attendance(teacher, subj_9a["id"], date.today(), records) is None

    cols, rows = tracking.gradebook_rows(subj_9a["id"])
    assert len(cols) > 0 and len(rows) == len(roster)

    alerts = insights.support_alerts(t_subjects)
    assert len(alerts) > 0 and alerts[0]["level"] in ("High", "Medium", "Low")

    search_hits = insights.search(teacher, "Pythagoras")
    assert len(search_hits) > 0

    # ---- Teacher Dashboard Customization & NovaAI ---------------------
    print("8b. Testing Teacher-Driven Dashboard & NovaAI Assistant...")
    from classpilot import ai_assistant
    insights.clear_teacher_dashboard(teacher["id"])
    prefs = insights.get_teacher_prefs(teacher["id"])
    assert prefs["widgets"] == []
    assert prefs["added_classes"] == []
    assert prefs["added_assignments"] == []

    # Teacher adds a class to her dashboard
    assert insights.add_teacher_dashboard_class(
        teacher["id"], "Grade 9 - A", "Mathematics", "Room 201", "Mon/Wed 09:00 AM", "Bring calculators"
    ) is None
    # Teacher adds an assignment to check
    assert insights.add_teacher_dashboard_assignment(
        teacher["id"], "Quadratic Equations Problem Set", "Grade 9 - A · Mathematics", 12, "Friday 5 PM", "High", "Check Q4"
    ) is None
    # Teacher adds a custom check item
    assert insights.add_teacher_check_item(
        teacher["id"], "Check 9A Algebra Quiz", "Assignment to Check", "Mathematics · Grade 9 - A"
    ) is None
    # Teacher adds a live widget
    assert insights.add_teacher_widget(teacher["id"], "climate") is None

    prefs = insights.get_teacher_prefs(teacher["id"])
    assert len(prefs["added_classes"]) == 1
    assert len(prefs["added_assignments"]) == 1
    assert len(prefs["check_items"]) == 1
    assert "climate" in prefs["widgets"]

    asg_item_id = prefs["added_assignments"][0]["id"]
    insights.step_teacher_dashboard_assignment(teacher["id"], asg_item_id, 1)
    assert insights.get_teacher_prefs(teacher["id"])["added_assignments"][0]["checked_count"] == 1
    insights.toggle_teacher_dashboard_assignment(teacher["id"], asg_item_id)
    assert insights.get_teacher_prefs(teacher["id"])["added_assignments"][0]["done"] is True

    climate = insights.class_climate_report(t_subjects)
    assert len(climate) == len(t_subjects)
    milestones = insights.student_milestones(student["id"])
    assert len(milestones) >= 1
    spotlight = insights.daily_concept_spotlight(student["id"])
    assert spotlight is not None and "title" in spotlight

    t_reply = ai_assistant.ask_teacher_ai(teacher, "Who is falling behind and needs support?")
    assert "Priority" in t_reply
    s_reply = ai_assistant.ask_student_ai(student, "Explain Pythagoras theorem")
    assert "Pythagoras" in s_reply

    # Test Symbolic Algebra, Calculus & Statistics Solver + Submission Evaluator
    quad_sol, _ = ai_assistant.solve_math_problem("Solve 2x^2 + 5x - 3 = 0")
    assert quad_sol and "0.5" in quad_sol and "-3" in quad_sol
    lin_sol, _ = ai_assistant.solve_math_problem("Solve 5x - 8 = 2x + 10")
    assert lin_sol and "6" in lin_sol
    calc_sol, _ = ai_assistant.solve_math_problem("Derivative of 3x^3 - 6x^2 + 4x - 9")
    assert calc_sol and "9x^2" in calc_sol
    stat_sol, _ = ai_assistant.solve_math_problem("Mean, median, std of 10, 20, 30, 40, 50")
    assert stat_sol and "30" in stat_sol
    bio_reply = ai_assistant.ask_student_ai(student, "Explain photosynthesis vs cellular respiration", mode="Socratic Hint Coach (Guided Thinking)")
    assert "Photosynthesis" in bio_reply
    eval_res = ai_assistant.evaluate_submission_with_ai("Quadratics Set", 30, "1. Identify a=2, b=5, c=-3. 2. Therefore Δ = 49 and x = 0.5 or -3.", "quadratic discriminant")
    assert eval_res["suggested_score"] > 0 and "Recommended Score" in eval_res["summary"]

    cards = ai_assistant.build_study_cards(student)
    assert len(cards) > 0
    plan = ai_assistant.generate_study_plan(student)
    assert len(plan) > 0
    print("   Backend tests passed!")


def test_streamlit_views():
    print("9. Testing Streamlit UI across all roles and pages...")
    seed.seed_demo_data()
    users = {u["role"]: u for u in storage.load("users") if u["username"] in ("admin", "sara.khan", "ali.raza")}

    # Test login screen first
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["_fast_test_mode"] = True
    at.run()
    assert not at.exception, f"Login page raised exception: {at.exception}"

    from views import (admin, announcements, assignments, assistant, attendance, dashboard,
                       gradebook, lessons, profile, pulse, quizzes, search, support)

    role_views = {
        "admin": [
            dashboard.admin_dashboard, assistant.teacher_assistant_page,
            admin.users_page, admin.classes_page, admin.subjects_page,
            admin.settings_page, support.alerts_page, support.deadline_planner_page,
            gradebook.teacher_gradebook_page, announcements.announcements_page,
            search.search_page, profile.profile_page,
        ],
        "teacher": [
            dashboard.teacher_dashboard, assistant.teacher_assistant_page,
            lessons.teacher_lessons_page, assignments.teacher_assignments_page,
            quizzes.teacher_quizzes_page, attendance.teacher_attendance_page,
            gradebook.teacher_gradebook_page, pulse.teacher_pulse_page,
            support.alerts_page, support.deadline_planner_page,
            announcements.announcements_page, search.search_page, profile.profile_page,
        ],
        "student": [
            dashboard.student_dashboard, assistant.student_assistant_page,
            lessons.student_lessons_page, assignments.student_assignments_page,
            quizzes.student_quizzes_page, gradebook.student_grades_page,
            attendance.student_attendance_page, announcements.announcements_page,
            search.search_page, profile.profile_page,
        ],
    }

    for role, view_funcs in role_views.items():
        user = users[role]
        # Verify app.py default entry for this role
        at_main = AppTest.from_file("app.py", default_timeout=30)
        at_main.session_state["user_id"] = user["id"]
        at_main.session_state["_fast_test_mode"] = True
        at_main.run()
        assert not at_main.exception, f"{role} app.py failed: {at_main.exception}"

        for func in view_funcs:
            script = f"import sys; sys.path.insert(0, '.'); from {func.__module__} import {func.__name__}; {func.__name__}()"
            at_view = AppTest.from_string(script, default_timeout=30)
            at_view.session_state["user_id"] = user["id"]
            at_view.session_state["_fast_test_mode"] = True
            at_view.run()
            assert not at_view.exception, f"{role} view '{func.__name__}' raised exception: {at_view.exception}"
        print(f"   All {len(view_funcs)} views for '{role}' rendered cleanly!")

    # Also test teacher_dashboard when teacher has added classes, assignments, tasks, and widgets
    t_user = users["teacher"]
    insights.add_teacher_dashboard_class(t_user["id"], "Grade 9 - A", "Mathematics", "Room 101", "Mon 9 AM", "Notes")
    insights.add_teacher_dashboard_assignment(t_user["id"], "Algebra Check", "Grade 9 - A · Mathematics", 10, "Friday", "High", "Check all")
    insights.add_teacher_check_item(t_user["id"], "Prep Lesson", "Lesson Prep", "Grade 9 - A")
    insights.add_teacher_widget(t_user["id"], "climate")
    at_t_pop = AppTest.from_string("import sys; sys.path.insert(0, '.'); from views.dashboard import teacher_dashboard; teacher_dashboard()", default_timeout=30)
    at_t_pop.session_state["user_id"] = t_user["id"]
    at_t_pop.session_state["_fast_test_mode"] = True
    at_t_pop.run()
    assert not at_t_pop.exception, f"Populated teacher_dashboard failed: {at_t_pop.exception}"

    # Test self-registration (Sign Up as Teacher and Sign Up as Student)
    new_t, err_t = school.register_account("new.teacher", "New Teacher", "", "teacher", "Teach@123", "Teach@123")
    assert err_t is None and new_t["role"] == "teacher"
    new_s, err_s = school.register_account("new.student", "New Student", "", "student", "Stud@1234", "Stud@1234", "Grade 9 - A")
    assert err_s is None and new_s["role"] == "student"

    # Wipe all demo/test users (sara.khan, ali.raza, etc.) so the app starts on a clean Sign-Up slate
    seed.reset_to_clean_slate()


if __name__ == "__main__":
    test_backend_workflows()
    test_streamlit_views()
    print("\nALL TESTS PASSED SUCCESSFULLY!")


