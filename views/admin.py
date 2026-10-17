"""Admin pages: users, classes, subjects and school settings."""

import json

import streamlit as st

from classpilot import auth, school, seed, storage, ui, utils


# ==========================================================================
# Users
# ==========================================================================
def users_page():
    admin = auth.require_role("admin")
    ui.page_header("Users", "Create accounts, edit roles, reset passwords and deactivate users.", "👥")
    tab_list, tab_add, tab_bulk = st.tabs(["All users", "➕ Add user", "📥 Bulk import"])

    with tab_list:
        col1, col2, col3 = st.columns([2, 1, 1])
        query = col1.text_input("Search users", placeholder="Name, username or e-mail")
        role_filter = col2.selectbox("Role", ["All", "Admin", "Teacher", "Student"])
        status_filter = col3.selectbox("Status", ["All", "Active", "Inactive"])

        users = sorted(storage.load("users"), key=lambda u: (u["role"], u["full_name"].lower()))
        if query:
            users = [u for u in users if utils.matches(query, u["full_name"], u["username"], u["email"])]
        if role_filter != "All":
            users = [u for u in users if u["role"] == role_filter.lower()]
        if status_filter != "All":
            users = [u for u in users if u.get("active", True) == (status_filter == "Active")]

        rows = []
        for u in users:
            cls = school.student_class(u["id"]) if u["role"] == "student" else None
            rows.append({"Name": u["full_name"], "Username": u["username"], "E-mail": u["email"],
                         "Role": u["role"].title(), "Class": cls["name"] if cls else "",
                         "Status": "Active" if u.get("active", True) else "Inactive",
                         "Last sign-in": utils.fmt_dt(u.get("last_login")) if u.get("last_login") else "Never"})
        st.caption(f"{len(rows)} user(s)")
        ui.table(rows)

        if users:
            st.divider()
            st.subheader("Manage a user")
            selected_id = st.selectbox("Choose a user", [u["id"] for u in users],
                                       format_func=lambda i: f"{school.user_name(i)} ({school.get_user(i)['username']})")
            _manage_user(admin, school.get_user(selected_id))

    with tab_add:
        with st.form("add_user", clear_on_submit=True):
            col1, col2 = st.columns(2)
            full_name = col1.text_input("Full name")
            username = col2.text_input("Username", help="Lowercase letters, numbers, dots or underscores.")
            email = col1.text_input("E-mail")
            role = col2.selectbox("Role", auth.ROLES, index=2, format_func=str.title)
            password = col1.text_input("Temporary password", type="password",
                                       help="At least 8 characters with a letter and a number.")
            class_options = ["none"] + [c["id"] for c in school.all_classes()]
            class_id = col2.selectbox("Class (students only)", class_options,
                                      format_func=lambda c: "— No class —" if c == "none" else school.class_name(c))
            submitted = st.form_submit_button("Create user", type="primary", icon="➕")
        if submitted:
            user, error = school.create_user(username, full_name, email, role, password)
            if not error and role == "student" and class_id != "none":
                cls = school.get_class(class_id)
                error = school.set_class_students(class_id, cls["student_ids"] + [user["id"]])
            ui.report(error, f"Account created for {full_name}.", "👤")

    with tab_bulk:
        st.caption("Paste one user per line: `full name, username, email, role, password`")
        st.code("Noor Ali, noor.ali, noor.ali@riverside.edu, student, Welcome@2026", language=None)
        with st.form("bulk_import"):
            text = st.text_area("Users to import", height=160)
            submitted = st.form_submit_button("Import users", type="primary", icon="📥")
        if submitted:
            created, problems = 0, []
            for number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) != 5:
                    problems.append(f"Line {number}: expected 5 values separated by commas.")
                    continue
                _, error = school.create_user(parts[1], parts[0], parts[2], parts[3].lower(), parts[4])
                if error:
                    problems.append(f"Line {number}: {error}")
                else:
                    created += 1
            if problems:
                st.warning(f"Imported {created} user(s). Some lines were skipped:\n\n" + "\n".join(f"- {p}" for p in problems))
            elif created:
                ui.done(f"Imported {created} user(s).", "📥")
            else:
                st.info("Nothing to import.")


def _manage_user(admin, user):
    """Edit form, password reset and delete for one user."""
    col1, col2 = st.columns(2)
    with col1.container(border=True):
        st.markdown("**Edit details**")
        with st.form(f"edit_{user['id']}"):
            full_name = st.text_input("Full name", user["full_name"])
            email = st.text_input("E-mail", user["email"])
            role = st.selectbox("Role", auth.ROLES, index=auth.ROLES.index(user["role"]), format_func=str.title)
            active = st.checkbox("Account active", user.get("active", True))
            saved = st.form_submit_button("Save changes", type="primary")
        if saved:
            ui.report(school.update_user(admin["id"], user["id"], full_name, email, role, active), "User updated.")
    with col2.container(border=True):
        st.markdown("**Reset password**")
        with st.form(f"reset_{user['id']}", clear_on_submit=True):
            new_password = st.text_input("New password", type="password")
            reset = st.form_submit_button("Reset password", icon="🔑")
        if reset:
            ui.report(school.reset_password(user["id"], new_password),
                      f"Password reset for {user['full_name']}. The account is also unlocked.", "🔑")
        st.markdown("**Danger zone**")
        if ui.confirm_button("Delete user", f"del_user_{user['id']}",
                             f"Permanently delete {user['full_name']} and their submissions, quiz attempts and attendance?"):
            ui.report(school.delete_user(admin["id"], user["id"]), "User deleted.", "🗑️")


# ==========================================================================
# Classes
# ==========================================================================
def classes_page():
    auth.require_role("admin")
    ui.page_header("Classes", "Create classes and manage which students belong to each one.", "🏫")

    classes = school.all_classes()
    rows = [{"Class": c["name"], "Grade": c.get("grade_level", ""), "Room": c.get("room", ""),
             "Students": len(school.class_students(c["id"])),
             "Subjects": ", ".join(s["name"] for s in school.subjects_for_class(c["id"])) or "—"} for c in classes]
    ui.table(rows)

    tab_roster, tab_edit, tab_add = st.tabs(["👥 Roster", "✏️ Edit class", "➕ New class"])
    with tab_add:
        with st.form("add_class", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            name = col1.text_input("Class name", placeholder="Grade 9 - B")
            grade = col2.text_input("Grade level", placeholder="Grade 9")
            room = col3.text_input("Room", placeholder="Room 105")
            submitted = st.form_submit_button("Create class", type="primary", icon="➕")
        if submitted:
            _, error = school.create_class(name, grade, room)
            ui.report(error, f"Class '{name}' created.", "🏫")

    if not classes:
        with tab_roster:
            ui.empty_state("Create a class first.")
        return

    with tab_roster:
        class_id = st.selectbox("Class", [c["id"] for c in classes], format_func=school.class_name, key="roster_class")
        cls = school.get_class(class_id)
        students = school.users_by_role("student")
        unassigned = [s["id"] for s in students if not school.student_class(s["id"])]
        st.caption(f"{len(unassigned)} student(s) are not in any class yet. "
                   "Adding a student who is in another class moves them here.")
        with st.form(f"roster_{class_id}"):
            chosen = st.multiselect(
                "Students in this class", [s["id"] for s in students], default=cls["student_ids"],
                format_func=lambda i: school.user_name(i) + ("" if i in cls["student_ids"] or i in unassigned
                                                             else f" (in {school.student_class(i)['name']})"))
            saved = st.form_submit_button("Save roster", type="primary", icon="💾")
        if saved:
            ui.report(school.set_class_students(class_id, chosen), "Roster saved.", "👥")

    with tab_edit:
        class_id = st.selectbox("Class", [c["id"] for c in classes], format_func=school.class_name, key="edit_class")
        cls = school.get_class(class_id)
        with st.form(f"edit_class_{class_id}"):
            col1, col2, col3 = st.columns(3)
            name = col1.text_input("Class name", cls["name"])
            grade = col2.text_input("Grade level", cls.get("grade_level", ""))
            room = col3.text_input("Room", cls.get("room", ""))
            saved = st.form_submit_button("Save changes", type="primary")
        if saved:
            ui.report(school.update_class(class_id, name, grade, room), "Class updated.")
        if ui.confirm_button("Delete class", f"del_class_{class_id}",
                             "Delete this class? Its announcements are removed and students become unassigned."):
            ui.report(school.delete_class(class_id), "Class deleted.", "🗑️")


# ==========================================================================
# Subjects
# ==========================================================================
def subjects_page():
    auth.require_role("admin")
    ui.page_header("Subjects", "A subject is one course for one class, taught by one teacher.", "📚")

    classes = school.all_classes()
    teachers = school.users_by_role("teacher", active_only=True)
    subjects = school.all_subjects()

    class_filter = st.selectbox("Filter by class", ["all"] + [c["id"] for c in classes],
                                format_func=lambda c: "All classes" if c == "all" else school.class_name(c))
    shown = subjects if class_filter == "all" else [s for s in subjects if s["class_id"] == class_filter]
    ui.table([{"Subject": s["name"], "Code": s.get("code", ""), "Class": school.class_name(s["class_id"]),
               "Teacher": school.user_name(s["teacher_id"]),
               "Lessons": len(storage.find("lessons", subject_id=s["id"])),
               "Assignments": len(storage.find("assignments", subject_id=s["id"])),
               "Quizzes": len(storage.find("quizzes", subject_id=s["id"]))} for s in shown])

    tab_add, tab_edit = st.tabs(["➕ New subject", "✏️ Edit subject"])
    with tab_add:
        if not classes or not teachers:
            st.info("You need at least one class and one active teacher before creating subjects.")
        else:
            with st.form("add_subject", clear_on_submit=True):
                col1, col2 = st.columns(2)
                name = col1.text_input("Subject name", placeholder="Chemistry")
                code = col2.text_input("Code (optional)", placeholder="CHEM9A")
                class_id = col1.selectbox("Class", [c["id"] for c in classes], format_func=school.class_name)
                teacher_id = col2.selectbox("Teacher", [t["id"] for t in teachers], format_func=school.user_name)
                description = st.text_area("Description", height=80)
                submitted = st.form_submit_button("Create subject", type="primary", icon="➕")
            if submitted:
                _, error = school.create_subject(name, code, class_id, teacher_id, description)
                ui.report(error, f"Subject '{name}' created.", "📚")

    with tab_edit:
        if not subjects:
            ui.empty_state("No subjects yet.")
            return
        subject_id = st.selectbox("Subject", [s["id"] for s in subjects], format_func=school.subject_label)
        subject = school.get_subject(subject_id)
        teacher_ids = [t["id"] for t in teachers]
        if subject["teacher_id"] not in teacher_ids:
            teacher_ids.append(subject["teacher_id"])
        with st.form(f"edit_subject_{subject_id}"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Subject name", subject["name"])
            code = col2.text_input("Code", subject.get("code", ""))
            teacher_id = col1.selectbox("Teacher", teacher_ids, index=teacher_ids.index(subject["teacher_id"]),
                                        format_func=school.user_name)
            col2.text_input("Class", school.class_name(subject["class_id"]), disabled=True,
                            help="The class can't change because coursework is linked to its students.")
            description = st.text_area("Description", subject.get("description", ""), height=80)
            saved = st.form_submit_button("Save changes", type="primary")
        if saved:
            ui.report(school.update_subject(subject_id, name, code, teacher_id, description), "Subject updated.")
        if ui.confirm_button("Delete subject", f"del_subject_{subject_id}",
                             "Delete this subject AND all its lessons, assignments, submissions, quizzes and attendance?"):
            ui.report(school.delete_subject(subject_id), "Subject deleted.", "🗑️")


# ==========================================================================
# Settings
# ==========================================================================
def settings_page():
    auth.require_role("admin")
    ui.page_header("Settings", "School details and the thresholds behind ClassPilot's smart features.", "⚙️")
    settings = storage.load_settings()

    with st.form("settings_form"):
        st.subheader("🏫 School")
        col1, col2 = st.columns(2)
        school_name = col1.text_input("School name", settings["school_name"])
        year = col2.text_input("Academic year", settings["academic_year"])

        st.subheader("🗓️ Deadline Conflict Detector")
        col1, col2 = st.columns(2)
        window = col1.number_input("Window (days either side)", 1, 7, int(settings["conflict_window_days"]))
        max_deadlines = col2.number_input("Warn when this many deadlines fall in the window", 2, 10,
                                          int(settings["conflict_max_deadlines"]))

        st.subheader("🚩 Early Support Alerts")
        col1, col2, col3, col4 = st.columns(4)
        missing = col1.number_input("Missing items", 1, 10, int(settings["alert_missing_threshold"]))
        low_grade = col2.number_input("Low average (%)", 0, 100, int(settings["alert_low_grade"]))
        low_attendance = col3.number_input("Low attendance (%)", 0, 100, int(settings["alert_attendance"]))
        decline = col4.number_input("Grade drop (points)", 1, 50, int(settings["alert_decline_points"]))

        st.subheader("💓 ClassPulse & assignments")
        col1, col2 = st.columns(2)
        pulse_low = col1.slider("Flag lessons with average confidence below", 1.0, 5.0,
                                float(settings["pulse_low_threshold"]), 0.1)
        penalty = col2.number_input("Default late penalty (%)", 0, 100, int(settings["default_late_penalty"]))

        st.subheader("🔤 Grade scale (minimum % for each letter)")
        scale_cols = st.columns(len(settings["grade_scale"]))
        new_scale = []
        for column, band in zip(scale_cols, settings["grade_scale"]):
            minimum = column.number_input(band["letter"], 0, 100, int(band["min"]), key=f"scale_{band['letter']}")
            new_scale.append({"letter": band["letter"], "min": minimum})
        saved = st.form_submit_button("Save settings", type="primary", icon="💾")

    if saved:
        mins = [b["min"] for b in new_scale]
        if not utils.clean(school_name):
            st.error("School name is required.")
        elif mins != sorted(mins, reverse=True) or len(set(mins)) != len(mins):
            st.error("Grade scale minimums must go strictly down from A to F.")
        else:
            settings.update({
                "school_name": utils.clean(school_name, 100), "academic_year": utils.clean(year, 30),
                "conflict_window_days": int(window), "conflict_max_deadlines": int(max_deadlines),
                "alert_missing_threshold": int(missing), "alert_low_grade": int(low_grade),
                "alert_attendance": int(low_attendance), "alert_decline_points": int(decline),
                "pulse_low_threshold": round(float(pulse_low), 1), "default_late_penalty": int(penalty),
                "grade_scale": new_scale,
            })
            storage.save_settings(settings)
            ui.done("Settings saved.", "⚙️")

    st.divider()
    st.subheader("💾 Data")
    col1, col2 = st.columns(2)
    with col1.container(border=True):
        st.markdown("**Backup**")
        st.caption("Download every collection as one JSON file.")
        st.download_button("Download backup", json.dumps(storage.export_all(), indent=2),
                           file_name="classpilot_backup.json", mime="application/json", icon="⬇️")
    with col2.container(border=True):
        st.markdown("**Reset demo data**")
        st.caption("Erases everything and recreates the demo school. You will be signed out.")
        if ui.confirm_button("Reset demo data", "reset_demo", "This deletes ALL data, including your changes. Continue?"):
            seed.seed_demo_data()
            auth.logout()
            st.rerun()
