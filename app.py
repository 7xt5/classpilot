"""
app.py - Novarix entry point.

Run with:   python run.py
        or: python -m streamlit run app.py
"""

import streamlit as st

from classpilot import auth, school, seed, storage, ui
from views import (admin, announcements, assignments, assistant, attendance, dashboard,
                   gradebook, lessons, login, profile, pulse, quizzes, search, support)

st.set_page_config(
    page_title="Novarix",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def build_pages(user):
    """Return the navigation structure (section -> pages) for a role."""
    role = user["role"]
    unread = school.unread_count(user)
    news_title = f"Announcements ({unread} new)" if unread else "Announcements"

    registry = {}
    st.session_state["_pages"] = registry

    def page(func, title, icon, path, default=False):
        registry[path] = st.Page(func, title=title, icon=icon, url_path=path, default=default)
        return registry[path]

    common = [
        page(announcements.announcements_page, news_title, ":material/campaign:", "announcements"),
        page(search.search_page, "Search", ":material/search:", "search"),
        page(profile.profile_page, "My account", ":material/person:", "account"),
    ]
    if role == "admin":
        pending_count = len(school.pending_join_requests())
        cls_nav_title = f"Classes ({pending_count} pending)" if pending_count else "Classes"
        return {
            "Overview": [
                page(dashboard.admin_dashboard, "Dashboard", ":material/dashboard:", "dashboard", True),
                page(assistant.teacher_assistant_page, "NovaAI Copilot", ":material/smart_toy:", "assistant"),
            ],
            "School setup": [
                page(admin.classes_page, cls_nav_title, ":material/domain:", "classes"),
                page(admin.users_page, "Users", ":material/group:", "users"),
                page(admin.subjects_page, "Subjects", ":material/menu_book:", "subjects"),
                page(admin.settings_page, "Settings", ":material/settings:", "settings"),
            ],
            "Insights": [
                page(support.alerts_page, "Early Support Alerts", ":material/flag:", "alerts"),
                page(support.deadline_planner_page, "Deadline Planner", ":material/event:", "deadlines"),
                page(gradebook.teacher_gradebook_page, "Gradebook", ":material/bar_chart:", "gradebook"),
            ],
            "General": common,
        }
    if role == "teacher":
        return {
            "Overview": [
                page(dashboard.teacher_dashboard, "Dashboard", ":material/dashboard:", "dashboard", True),
                page(assistant.teacher_assistant_page, "NovaAI Copilot", ":material/smart_toy:", "assistant"),
            ],
            "Teaching": [
                page(lessons.teacher_lessons_page, "Lesson Hub", ":material/library_books:", "lessons"),
                page(assignments.teacher_assignments_page, "Assignments", ":material/assignment:", "assignments"),
                page(quizzes.teacher_quizzes_page, "Quiz Builder", ":material/quiz:", "quizzes"),
                page(attendance.teacher_attendance_page, "Attendance", ":material/fact_check:", "attendance"),
                page(gradebook.teacher_gradebook_page, "Gradebook", ":material/bar_chart:", "gradebook"),
            ],
            "Insights": [
                page(pulse.teacher_pulse_page, "NovaPulse", ":material/monitor_heart:", "classpulse"),
                page(support.alerts_page, "Early Support Alerts", ":material/flag:", "alerts"),
                page(support.deadline_planner_page, "Deadline Planner", ":material/event:", "deadlines"),
            ],
            "General": common,
        }
    return {
        "Overview": [
            page(dashboard.student_dashboard, "Dashboard", ":material/dashboard:", "dashboard", True),
            page(assistant.student_assistant_page, "NovaAI Tutor", ":material/smart_toy:", "assistant"),
        ],
        "Learning": [
            page(lessons.student_lessons_page, "Lessons", ":material/library_books:", "lessons"),
            page(assignments.student_assignments_page, "Assignments", ":material/assignment:", "assignments"),
            page(quizzes.student_quizzes_page, "Quizzes", ":material/quiz:", "quizzes"),
            page(gradebook.student_grades_page, "My grades", ":material/bar_chart:", "grades"),
            page(attendance.student_attendance_page, "My attendance", ":material/fact_check:", "attendance"),
        ],
        "General": common,
    }


def sidebar(user):
    """Clean sidebar with custom Novarix logo, active user profile, and logout."""
    settings = storage.load_settings()
    logo = ui.logo_path()
    with st.sidebar:
        if logo:
            c_logo, c_txt = st.columns([0.9, 2.3])
            with c_logo:
                st.image(logo, width="stretch")
            with c_txt:
                st.markdown("### NOVARIX")
                st.caption(f"{settings['school_name']}")
        else:
            st.markdown("## NOVARIX")
            st.caption(f"{settings['school_name']} · {settings['academic_year']}")
        with st.container(border=True):
            st.markdown(
                f"**{user['full_name']}** ({user['role'].title()})  \n"
                f"`@{user['username']}`"
            )
            if user["role"] == "student":
                cls = school.student_class(user["id"])
                st.caption(f"Class: {cls['name']}" if cls else "Class: Unassigned")
        if st.button("Disconnect / Log out", icon=":material/logout:", width="stretch"):
            auth.logout()
            st.rerun()



def main():
    try:
        seed.ensure_data()
    except OSError as exc:
        st.error(f"Novarix could not create its data folder: {exc}", icon=":material/error:")
        st.stop()

    ui.show_flash()
    user = auth.current_user()
    if user is None:
        st.navigation([st.Page(login.login_page, title="Sign in / Sign up", icon=":material/person_add:")], position="hidden").run()
        return

    sidebar(user)
    st.navigation(build_pages(user)).run()


main()

