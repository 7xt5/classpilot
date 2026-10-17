"""Attendance - take the register and see attendance percentages."""

from datetime import date

import pandas as pd
import streamlit as st

from classpilot import auth, school, storage, tracking, ui, utils


def teacher_attendance_page():
    user = auth.require_role("teacher")
    ui.page_header("Attendance", "Take the register in seconds. Present and Late count as attended; Excused is ignored.", "✅")
    subjects = school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("You are not assigned to any subjects yet.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        subject_id = ui.subject_select(subjects, "att_subject")
    day = col2.date_input("Date", date.today(), max_value=date.today(), format="DD/MM/YYYY", key="att_date")
    subject = school.get_subject(subject_id)
    students = school.class_students(subject["class_id"])

    tab_take, tab_report, tab_history = st.tabs(["📝 Take attendance", "📊 Report", "🗂️ History"])

    with tab_take:
        if not students:
            ui.empty_state("This class has no students.")
        else:
            existing = tracking.get_attendance(subject_id, day)
            if existing:
                st.info(f"Attendance for {utils.fmt_date(day)} was already saved — changes will update it.", icon="ℹ️")
            elif day.weekday() >= 5:
                st.warning("That date is a weekend.", icon="📅")
            records = existing["records"] if existing else {}
            form_key = f"att_{subject_id}_{day}"
            # "Mark everyone present" simply resets the widgets to Present.
            if st.button("Mark everyone present", icon="✅", key=f"{form_key}_all"):
                for s in students:
                    st.session_state[f"{form_key}_{s['id']}"] = "Present"
            with st.form(form_key):
                chosen = {}
                for s in students:
                    widget_key = f"{form_key}_{s['id']}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = records.get(s["id"], "Present")
                    chosen[s["id"]] = st.segmented_control(
                        s["full_name"], tracking.ATTENDANCE_STATUSES, key=widget_key, required=True)
                saved = st.form_submit_button("Save attendance", type="primary", icon="💾")
            if saved:
                error = tracking.save_attendance(user, subject_id, day, chosen)
                if not error:
                    absent = [school.user_name(i) for i, s in chosen.items() if s == "Absent"]
                    message = f"Attendance saved for {utils.fmt_date(day)}."
                    if absent:
                        message += f" Absent: {', '.join(absent)}."
                ui.report(error, message if not error else "", "✅")

    with tab_report:
        sessions = tracking.attendance_sessions(subject_id)
        if not sessions:
            ui.empty_state("No attendance has been recorded for this subject yet.")
        else:
            settings = storage.load_settings()
            rows = []
            for s in students:
                summary = tracking.attendance_summary(s["id"], [subject_id])
                rows.append({"Student": s["full_name"], "Present": summary["Present"], "Late": summary["Late"],
                             "Absent": summary["Absent"], "Excused": summary["Excused"],
                             "Attendance": summary["percent"],
                             "Flag": "⚠️ Below target" if summary["percent"] is not None
                             and summary["percent"] < settings["alert_attendance"] else ""})
            percents = [r["Attendance"] for r in rows if r["Attendance"] is not None]
            ui.metrics([("Sessions recorded", len(sessions)), ("Class attendance", utils.fmt_pct(utils.mean(percents))),
                        (f"Below {settings['alert_attendance']}%", sum(1 for r in rows if r["Flag"]))])
            ui.table(rows, {"Attendance": ui.pct_column("Attendance")})
            st.markdown("**Class attendance by day**")
            ui.line_chart(tracking.attendance_by_date(subject_id), x="date", y="percent", height=240)

    with tab_history:
        sessions = tracking.attendance_sessions(subject_id)
        if not sessions:
            ui.empty_state("No history yet.")
        else:
            names = {s["id"]: s["full_name"] for s in students}
            table = {}
            for session in sessions[-15:]:
                label = utils.parse_dt(session["date"]).strftime("%d %b")
                for student_id, status in session["records"].items():
                    if student_id in names:
                        table.setdefault(names[student_id], {})[label] = status[0]
            st.caption("Last 15 sessions · P = Present, L = Late, A = Absent, E = Excused")
            frame = pd.DataFrame.from_dict(table, orient="index").fillna("–")
            frame.index.name = "Student"
            st.dataframe(frame, width="stretch")


def student_attendance_page():
    user = auth.require_role("student")
    ui.page_header("My attendance", "Present and Late count as attended. Excused days don't count against you.", "✅")
    subjects = school.subjects_for_student(user["id"])
    if not subjects:
        ui.empty_state("You are not enrolled in a class yet.")
        return
    settings = storage.load_settings()
    overall = tracking.attendance_summary(user["id"], [s["id"] for s in subjects])
    ui.metrics([("Overall attendance", utils.fmt_pct(overall["percent"])), ("Present", overall["Present"]),
                ("Late", overall["Late"]), ("Absent", overall["Absent"]), ("Excused", overall["Excused"])])
    if overall["percent"] is not None and overall["percent"] < settings["alert_attendance"]:
        st.warning(f"Your attendance is below the school target of {settings['alert_attendance']}%.", icon="⚠️")

    rows = []
    for s in subjects:
        summary = tracking.attendance_summary(user["id"], [s["id"]])
        rows.append({"Subject": s["name"], "Sessions": summary["sessions"], "Present": summary["Present"],
                     "Late": summary["Late"], "Absent": summary["Absent"], "Excused": summary["Excused"],
                     "Attendance": summary["percent"]})
    ui.table(rows, {"Attendance": ui.pct_column("Attendance")})

    st.subheader("Recent records")
    history = []
    for session in storage.load("attendance"):
        status = session["records"].get(user["id"])
        if status and session["subject_id"] in {s["id"] for s in subjects}:
            history.append({"Date": session["date"], "Subject": school.get_subject(session["subject_id"])["name"],
                            "Status": status})
    history.sort(key=lambda r: r["Date"], reverse=True)
    status_filter = st.multiselect("Show statuses", tracking.ATTENDANCE_STATUSES, default=tracking.ATTENDANCE_STATUSES)
    history = [dict(h, Date=utils.fmt_date(h["Date"])) for h in history if h["Status"] in status_filter]
    ui.table(history[:60])
