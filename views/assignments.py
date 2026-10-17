"""Assignments - create, detect deadline conflicts, collect work and grade it."""

import pandas as pd
import streamlit as st

from classpilot import auth, coursework, insights, school, storage, ui, utils


# ==========================================================================
# Teacher: create / edit
# ==========================================================================
def _new_assignment(user, subjects):
    """Create form WITHOUT st.form, so the deadline check updates live as the
    teacher changes the date."""
    settings = storage.load_settings()
    default_day, default_time = ui.default_due(7)
    st.session_state.setdefault("na_date", default_day)
    st.session_state.setdefault("na_time", default_time)
    st.session_state.setdefault("na_penalty", int(settings["default_late_penalty"]))

    left, right = st.columns([3, 2])
    with left:
        subject_id = ui.subject_select(subjects, "na_subject")
        title = st.text_input("Title", key="na_title", max_chars=120)
        description = st.text_area("Instructions", key="na_description", height=150)
        col1, col2, col3 = st.columns(3)
        due_day = col1.date_input("Due date", key="na_date", format="DD/MM/YYYY")
        due_time = col2.time_input("Due time", key="na_time", step=900)
        points = col3.number_input("Max points", 1, 1000, 20, key="na_points")
        col1, col2 = st.columns(2)
        allow_late = col1.checkbox("Accept late work", True, key="na_late")
        penalty = col2.number_input("Late penalty (%)", 0, 100, key="na_penalty", disabled=not allow_late)
    with right:
        st.markdown("**🗓️ Deadline Conflict Detector**")
        st.caption("Checks every subject this class takes — not just yours.")
        subject = school.get_subject(subject_id)
        result = ui.deadline_check_panel(subject["class_id"], utils.combine(due_day, due_time), "na_date", "na_time")

    override = True
    if result["conflict"]:
        override = st.checkbox("I understand the workload risk and still want this deadline.", key="na_override")
    if st.button("Create assignment", type="primary", icon="📝", disabled=not override):
        _, error = coursework.save_assignment(user, subject_id, title, description, utils.combine(due_day, due_time),
                                              points, allow_late, penalty if allow_late else 0)
        if error:
            st.error(error, icon="⚠️")
        else:
            for key in ("na_title", "na_description", "na_date", "na_time", "na_points", "na_override", "na_penalty"):
                st.session_state.pop(key, None)
            ui.done(f"Assignment '{title}' created.", "📝")


def _edit_assignment(user, subjects, assignment):
    subject_ids = [s["id"] for s in subjects]
    due = utils.parse_dt(assignment["due"])
    with st.form(f"edit_asg_{assignment['id']}"):
        subject_id = st.selectbox("Subject", subject_ids, index=subject_ids.index(assignment["subject_id"]),
                                  format_func=school.subject_label)
        title = st.text_input("Title", assignment["title"])
        description = st.text_area("Instructions", assignment["description"], height=120)
        col1, col2, col3 = st.columns(3)
        due_day = col1.date_input("Due date", due.date(), format="DD/MM/YYYY")
        due_time = col2.time_input("Due time", due.time(), step=900)
        points = col3.number_input("Max points", 1, 1000, int(assignment["max_points"]))
        col1, col2 = st.columns(2)
        allow_late = col1.checkbox("Accept late work", assignment.get("allow_late", True))
        penalty = col2.number_input("Late penalty (%)", 0, 100, int(assignment.get("late_penalty", 0)))
        saved = st.form_submit_button("Save changes", type="primary")
    if saved:
        _, error = coursework.save_assignment(user, subject_id, title, description, utils.combine(due_day, due_time),
                                              points, allow_late, penalty, assignment_id=assignment["id"])
        if not error:
            conflict = insights.check_conflicts(school.get_subject(subject_id)["class_id"],
                                                utils.combine(due_day, due_time), assignment["id"])
            if conflict["conflict"]:
                ui.flash(f"Saved, but note: {conflict['load']} deadlines fall close together for this class.", "⚠️")
        ui.report(error, "Assignment updated.")
    if ui.confirm_button("Delete assignment", f"del_asg_{assignment['id']}",
                         "Delete this assignment and every submission and grade attached to it?"):
        ui.report(coursework.delete_assignment(user, assignment["id"]), "Assignment deleted.", "🗑️")


# ==========================================================================
# Teacher: grading
# ==========================================================================
def _grade_assignment(user, assignment):
    """Roster with statuses, quick bulk grading and individual feedback."""
    subject = school.get_subject(assignment["subject_id"])
    students = school.class_students(subject["class_id"])
    if not students:
        ui.empty_state("This class has no students.")
        return
    rows = []
    for student in students:
        sub = coursework.submission_for(assignment["id"], student["id"])
        rows.append({
            "_id": student["id"],
            "Student": student["full_name"],
            "Status": coursework.assignment_status(assignment, student["id"], sub),
            "Submitted": utils.fmt_dt(sub["submitted_at"]) if sub and not sub.get("offline") else "—",
            "Score": float(sub["score"]) if sub and sub.get("score") is not None else None,
            "Feedback": sub.get("feedback", "") if sub else "",
        })
    counts = pd.Series([r["Status"] for r in rows]).value_counts().to_dict()
    late_count = sum(1 for s in students
                     if coursework.is_late(coursework.submission_for(assignment["id"], s["id"]), assignment))
    ui.metrics([("Turned in", sum(counts.get(s, 0) for s in ("Submitted", "Submitted late", "Graded"))),
                ("Graded", counts.get("Graded", 0)),
                ("Late", late_count),
                ("Missing", counts.get("Missing", 0))])

    st.markdown("**⚡ Quick grading** — type scores and feedback, then press *Save grades*.")
    st.caption(f"Scores are out of {assignment['max_points']}. Late work automatically loses "
               f"{assignment.get('late_penalty', 0)}% when averages are calculated. Clear a score to remove the grade.")
    frame = pd.DataFrame(rows)
    edited = st.data_editor(
        frame, hide_index=True, key=f"grades_{assignment['id']}", width="stretch",
        column_order=["Student", "Status", "Submitted", "Score", "Feedback"],
        disabled=["Student", "Status", "Submitted"],
        column_config={
            "Score": st.column_config.NumberColumn("Score", min_value=0, max_value=assignment["max_points"], step=0.5),
            "Feedback": st.column_config.TextColumn("Feedback", max_chars=5000, width="large"),
        })
    if st.button("Save grades", type="primary", icon="💾", key=f"save_grades_{assignment['id']}"):
        errors, changed = [], 0
        for original, new in zip(rows, edited.to_dict("records")):
            score = new["Score"]
            score = None if score is None or pd.isna(score) else score
            feedback = new["Feedback"] if isinstance(new["Feedback"], str) else ""
            if score == original["Score"] and feedback == original["Feedback"]:
                continue
            if score is None:
                error = coursework.clear_grade(user, assignment["id"], original["_id"])
            else:
                error = coursework.grade_student(user, assignment["id"], original["_id"], score, feedback)
            if error:
                errors.append(f"{original['Student']}: {error}")
            else:
                changed += 1
        if errors:
            st.error("Some grades were not saved:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            ui.done(f"Saved {changed} grade(s)." if changed else "No changes to save.", "💾")

    st.markdown("**📄 Submitted work**")
    submitted = [(s, coursework.submission_for(assignment["id"], s["id"])) for s in students]
    submitted = [(s, sub) for s, sub in submitted if sub and not sub.get("offline")]
    if not submitted:
        st.caption("No online submissions yet.")
    for student, sub in submitted:
        status = coursework.assignment_status(assignment, student["id"], sub)
        with st.expander(f"{student['full_name']} — {status} · {utils.fmt_dt(sub['submitted_at'])}"
                         + (f" · revision {sub['revision']}" if sub.get("revision", 1) > 1 else "")):
            if coursework.is_late(sub, assignment):
                st.warning(f"Submitted late — {assignment.get('late_penalty', 0)}% penalty applies.", icon="⏰")
            if sub.get("text"):
                st.markdown(sub["text"])
            if sub.get("link"):
                st.markdown(f"🔗 [{sub['link']}]({sub['link']})")
            if sub.get("file"):
                ui.file_download(sub["file"], key=f"dl_{sub['id']}")
            with st.form(f"grade_one_{sub['id']}"):
                col1, col2 = st.columns([1, 3])
                score = col1.number_input(f"Score / {assignment['max_points']}", 0.0, float(assignment["max_points"]),
                                          float(sub["score"]) if sub.get("score") is not None else 0.0, 0.5)
                feedback = col2.text_area("Feedback", sub.get("feedback", ""), height=80)
                saved = st.form_submit_button("Save grade & feedback", type="primary")
            if saved:
                ui.report(coursework.grade_student(user, assignment["id"], student["id"], score, feedback),
                          f"Graded {student['full_name']}.")


def teacher_assignments_page():
    user = auth.require_role("teacher")
    ui.page_header("Assignments", "Set work, spot deadline clashes and grade submissions.", "📝")
    subjects = school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("You are not assigned to any subjects yet.")
        return
    subject_ids = [s["id"] for s in subjects]
    queue, _ = coursework.grading_queue(subject_ids)

    tab_list, tab_grade, tab_new = st.tabs(["📋 All assignments", f"✍️ Grade work ({len(queue)} waiting)", "➕ New assignment"])

    with tab_new:
        _new_assignment(user, subjects)

    with tab_list:
        col1, col2, col3 = st.columns([1.4, 1, 1.4])
        with col1:
            subject_filter = ui.subject_select(subjects, "asg_subject_filter", include_all=True)
        when = col2.selectbox("Show", ["All", "Upcoming", "Past due"], key="asg_when")
        query = col3.text_input("Search", key="asg_query", placeholder="Title or instructions")
        items = coursework.assignments_for_subjects(subject_ids if subject_filter == "all" else [subject_filter])
        if when == "Upcoming":
            items = [a for a in items if not utils.is_past(a["due"])]
        elif when == "Past due":
            items = [a for a in items if utils.is_past(a["due"])]
        if query:
            items = [a for a in items if utils.matches(query, a["title"], a["description"])]

        rows = []
        for a in items:
            class_size = len(school.class_students(school.get_subject(a["subject_id"])["class_id"]))
            subs = coursework.submissions_for_assignment(a["id"])
            online = [s for s in subs if not s.get("offline")]
            rows.append({"Title": a["title"], "Subject": school.subject_label(a["subject_id"]),
                         "Due": utils.fmt_dt(a["due"]), "When": utils.relative_due(a["due"]),
                         "Points": a["max_points"],
                         "Turned in": utils.percent(len(online), class_size) or 0,
                         "Graded": f"{sum(1 for s in subs if s.get('score') is not None)}/{class_size}",
                         "Late": sum(1 for s in online if coursework.is_late(s, a))})
        st.caption(f"{len(rows)} assignment(s)")
        ui.table(rows, {"Turned in": ui.pct_column("Turned in")})

        if items:
            st.divider()
            chosen = st.selectbox("Open an assignment to edit it", [a["id"] for a in items],
                                  format_func=lambda i: f"{storage.get('assignments', i)['title']} · "
                                                        f"{school.subject_label(storage.get('assignments', i)['subject_id'])}",
                                  key="asg_edit_pick")
            assignment = storage.get("assignments", chosen)
            with st.container(border=True):
                _edit_assignment(user, subjects, assignment)

    with tab_grade:
        if queue:
            st.info(f"{len(queue)} submission(s) are waiting to be graded (oldest first below).", icon="✍️")
            names = school.name_map()
            ui.table([{"Student": names.get(s["student_id"], "?"),
                       "Assignment": storage.get("assignments", s["assignment_id"])["title"],
                       "Submitted": utils.fmt_dt(s["submitted_at"]),
                       "Late": "Yes" if coursework.is_late(s, storage.get("assignments", s["assignment_id"])) else ""}
                      for s in queue[:10]])
        else:
            st.success("You're all caught up — nothing waiting to be graded.", icon="🎉")
        all_items = coursework.assignments_for_subjects(subject_ids)
        if not all_items:
            ui.empty_state("No assignments yet.")
            return
        waiting = {s["assignment_id"] for s in queue}
        default = next((i for i, a in enumerate(all_items) if a["id"] in waiting), 0)
        chosen = st.selectbox(
            "Assignment to grade", [a["id"] for a in all_items], index=default, key="grade_pick",
            format_func=lambda i: ("🔴 " if i in waiting else "") + storage.get("assignments", i)["title"] + " · "
            + school.subject_label(storage.get("assignments", i)["subject_id"]))
        _grade_assignment(user, storage.get("assignments", chosen))


# ==========================================================================
# Student
# ==========================================================================
def _submission_form(user, assignment, submission):
    graded = submission and submission.get("score") is not None
    if graded:
        return
    closed = utils.is_past(assignment["due"]) and not assignment.get("allow_late", True)
    if closed:
        st.error("The deadline has passed and this assignment no longer accepts work.", icon="🔒")
        return
    if utils.is_past(assignment["due"]):
        st.warning(f"This is past the deadline — it will be marked late "
                   f"({assignment.get('late_penalty', 0)}% penalty).", icon="⏰")
    with st.form(f"submit_{assignment['id']}"):
        text = st.text_area("Your answer", submission.get("text", "") if submission else "", height=150)
        link = st.text_input("Link (Google Doc, video, website...)", submission.get("link", "") if submission else "")
        upload = st.file_uploader("Attach a file (max 10 MB)" + (" — replaces your current file" if submission and submission.get("file") else ""),
                                  key=f"up_{assignment['id']}")
        label = "Resubmit" if submission else "Turn in"
        sent = st.form_submit_button(label, type="primary", icon="📤")
    if sent:
        _, error = coursework.submit_assignment(user, assignment["id"], text, link, upload)
        ui.report(error, "Work turned in!" if not submission else "Submission updated.", "📤")


def student_assignments_page():
    user = auth.require_role("student")
    ui.page_header("Assignments", "Everything you need to hand in, with feedback from your teachers.", "📝")
    subjects = school.subjects_for_student(user["id"])
    if not subjects:
        ui.empty_state("You are not enrolled in a class yet.")
        return
    col1, col2, col3 = st.columns([1.4, 1, 1.4])
    with col1:
        subject_filter = ui.subject_select(subjects, "s_asg_subject", include_all=True)
    status_filter = col2.selectbox("Status", ["All", "To do", "Missing", "Submitted", "Graded"], key="s_asg_status")
    query = col3.text_input("Search", key="s_asg_query", placeholder="Assignment title")
    items = coursework.assignments_for_subjects([s["id"] for s in subjects] if subject_filter == "all" else [subject_filter])
    if query:
        items = [a for a in items if utils.matches(query, a["title"], a["description"])]

    entries = []
    for a in items:
        sub = coursework.submission_for(a["id"], user["id"])
        status = coursework.assignment_status(a, user["id"], sub)
        group = {"Not submitted": "To do", "Missing": "Missing", "Submitted": "Submitted",
                 "Submitted late": "Submitted", "Graded": "Graded"}[status]
        if status_filter == "All" or status_filter == group:
            entries.append((a, sub, status))

    # To-do first (soonest due), then everything else (most recent first).
    entries.sort(key=lambda e: (e[2] not in ("Missing", "Not submitted"), e[0]["due"]))
    st.caption(f"{len(entries)} assignment(s)")
    if not entries:
        ui.empty_state("No assignments match your filters.")
    for a, sub, status in entries:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            col1.markdown(f"**{a['title']}** {ui.badge(status)}  \n:gray[{school.subject_label(a['subject_id'])} · "
                          f"due {utils.fmt_dt(a['due'])} ({utils.relative_due(a['due'])}) · {a['max_points']} pts]")
            if status == "Graded":
                pct = coursework.assignment_percent(sub, a)
                col2.metric("Score", f"{coursework.effective_score(sub, a):g}/{a['max_points']}", utils.fmt_pct(pct),
                            delta_color="off")
            with st.expander("Open"):
                st.markdown(a["description"] or "_No instructions provided._")
                if sub:
                    st.markdown("**Your submission**")
                    st.caption(f"Turned in {utils.fmt_dt(sub['submitted_at'])}"
                               + (" · late" if coursework.is_late(sub, a) else "")
                               + (" · graded in class" if sub.get("offline") else ""))
                    if sub.get("text"):
                        st.markdown(sub["text"])
                    if sub.get("link"):
                        st.markdown(f"🔗 [{sub['link']}]({sub['link']})")
                    if sub.get("file"):
                        ui.file_download(sub["file"], key=f"mine_{sub['id']}")
                if status == "Graded":
                    if coursework.is_late(sub, a):
                        st.caption(f"Raw score {sub['score']:g} with a {a.get('late_penalty', 0)}% late penalty.")
                    if sub.get("feedback"):
                        st.info(f"**Teacher feedback:** {sub['feedback']}", icon="💬")
                _submission_form(user, a, sub)
