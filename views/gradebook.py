"""Gradebook - grades by student, subject and assignment, with progress charts."""

import pandas as pd
import streamlit as st

from classpilot import auth, school, storage, tracking, ui, utils


def _student_progress(student_id, subject_ids, key):
    """Line chart of a student's grades over time + table of every item."""
    items = tracking.grade_items_for_student(student_id, subject_ids)
    if not items:
        ui.empty_state("No graded work yet.")
        return items
    chart_rows = [{"Date": utils.parse_dt(i["date"]).date().isoformat(), "Score %": i["percent"],
                   "Subject": i["subject"].split(" · ")[0]} for i in items]
    frame = pd.DataFrame(chart_rows)
    st.line_chart(frame, x="Date", y="Score %", color="Subject" if frame["Subject"].nunique() > 1 else None, height=260)
    trend = tracking.grade_trend(items)
    if trend:
        earlier, recent, change = trend
        if change <= -5:
            st.warning(f"Grades are trending down: {earlier:.0f}% → {recent:.0f}% ({change:+.0f} pts).", icon="📉")
        elif change >= 5:
            st.success(f"Grades are improving: {earlier:.0f}% → {recent:.0f}% ({change:+.0f} pts).", icon="📈")
        else:
            st.info(f"Grades are steady around {recent:.0f}%.", icon="➖")
    return items


def _items_table(items):
    settings = storage.load_settings()
    ui.table([{"Date": utils.fmt_date(i["date"]), "Item": i["title"], "Type": i["kind"], "Subject": i["subject"],
               "Score": f"{i['score']:g} / {i['max']}", "Percent": i["percent"],
               "Grade": utils.letter_grade(i["percent"], settings["grade_scale"]),
               "Late": "Yes" if i["late"] else "", "Feedback": i["feedback"]} for i in reversed(items)],
             {"Percent": ui.pct_column("Percent")})


# ==========================================================================
# Teacher / admin
# ==========================================================================
def teacher_gradebook_page():
    user = auth.require_role("teacher", "admin")
    ui.page_header("Gradebook", "Every grade for a subject in one place. Late penalties are already applied.", "📊")
    subjects = school.all_subjects() if user["role"] == "admin" else school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("No subjects to show yet.")
        return

    subject_id = ui.subject_select(subjects, "gb_subject")
    columns, rows = tracking.gradebook_rows(subject_id)
    if not rows:
        ui.empty_state("This class has no students yet.")
        return

    col1, col2 = st.columns([2, 1])
    query = col1.text_input("Filter students", placeholder="Student name", key="gb_query")
    grade_filter = col2.multiselect("Letter grade", ["A", "B", "C", "D", "F", "—"], key="gb_grade")
    shown = [r for r in rows if (not query or utils.matches(query, r["Student"]))
             and (not grade_filter or r["Grade"] in grade_filter)]

    averages = [r["Average"] for r in rows if r["Average"] is not None]
    graded_cells = sum(1 for r in rows for key, _ in columns if r.get(key) is not None)
    ui.metrics([("Students", len(rows)), ("Class average", utils.fmt_pct(utils.mean(averages))),
                ("Graded items", len(columns)),
                ("Below 60%", sum(1 for a in averages if a < 60), "Students with an average under 60%")])

    labels = dict(columns)
    table_rows = []
    for r in shown:
        row = {"Student": r["Student"]}
        row.update({labels[key]: r.get(key) for key, _ in columns})
        row["Average"], row["Grade"] = r["Average"], r["Grade"]
        table_rows.append(row)
    config = {label: st.column_config.NumberColumn(label, format="%.0f%%") for label in labels.values()}
    config["Average"] = ui.pct_column("Average")
    st.caption(f"Showing {len(table_rows)} of {len(rows)} students · 📝 assignment · ❓ quiz · empty = not graded / missing")
    ui.table(table_rows, config)
    if table_rows:
        st.download_button("Export to CSV", pd.DataFrame(table_rows).to_csv(index=False),
                           file_name=f"gradebook_{school.get_subject(subject_id).get('code') or subject_id}.csv",
                           mime="text/csv", icon="⬇️")

    if columns and graded_cells:
        st.subheader("Class average per item")
        ui.bar_chart([{"Item": label, "Average %": utils.mean([r.get(key) for r in rows]) or 0}
                      for key, label in columns], x="Item", y="Average %", height=280)

    st.subheader("Student progress")
    student_id = st.selectbox("Student", [r["_id"] for r in rows], format_func=school.user_name, key="gb_student")
    col1, col2 = st.columns(2)
    subject_avg = tracking.subject_average(student_id, subject_id)
    col1.metric("Average in this subject", utils.fmt_pct(subject_avg))
    attendance = tracking.attendance_summary(student_id, [subject_id])
    col2.metric("Attendance in this subject", utils.fmt_pct(attendance["percent"]))
    items = _student_progress(student_id, [subject_id], "gb")
    if items:
        _items_table(items)


# ==========================================================================
# Student
# ==========================================================================
def student_grades_page():
    user = auth.require_role("student")
    ui.page_header("My grades", "Your results across every subject.", "📊")
    subjects = school.subjects_for_student(user["id"])
    if not subjects:
        ui.empty_state("You are not enrolled in a class yet.")
        return
    settings = storage.load_settings()
    items = tracking.grade_items_for_student(user["id"])
    overall = utils.mean([i["percent"] for i in items])
    trend = tracking.grade_trend(items)
    ui.metrics([("Overall average", utils.fmt_pct(overall), None,
                 f"{trend[2]:+.1f} pts recently" if trend else None),
                ("Letter grade", utils.letter_grade(overall, settings["grade_scale"])),
                ("Graded items", len(items)),
                ("Late submissions", sum(1 for i in items if i["late"]))])

    st.subheader("By subject")
    subject_rows = []
    for s in subjects:
        avg = tracking.subject_average(user["id"], s["id"])
        subject_rows.append({"Subject": s["name"], "Teacher": school.user_name(s["teacher_id"]),
                             "Average": avg, "Grade": utils.letter_grade(avg, settings["grade_scale"]),
                             "Items": len([i for i in items if i["subject_id"] == s["id"]])})
    col1, col2 = st.columns([3, 2])
    with col1:
        ui.table(subject_rows, {"Average": ui.pct_column("Average")})
    with col2:
        ui.bar_chart([{"Subject": r["Subject"], "Average %": r["Average"] or 0} for r in subject_rows],
                     x="Subject", y="Average %", height=240)

    st.subheader("Progress over time")
    subject_filter = ui.subject_select(subjects, "my_grades_subject", include_all=True)
    subject_ids = [s["id"] for s in subjects] if subject_filter == "all" else [subject_filter]
    shown = _student_progress(user["id"], subject_ids, "mine")
    if shown:
        kind = st.segmented_control("Type", ["All", "Assignment", "Quiz"], default="All", key="my_grades_kind")
        if kind in ("Assignment", "Quiz"):
            shown = [i for i in shown if i["kind"] == kind]
        _items_table(shown)
