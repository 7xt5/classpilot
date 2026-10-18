"""NovaPulse - class-wide confidence per lesson (students stay anonymous)."""

import streamlit as st

from classpilot import auth, school, storage, tracking, ui, utils


def teacher_pulse_page():
    user = auth.require_role("teacher")
    ui.page_header("NovaPulse", "How confident does the class feel about each lesson? "
                   "Students rate privately (1-5); you only ever see totals.", "💓")
    subjects = school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("You are not assigned to any subjects yet.")
        return
    settings = storage.load_settings()
    subject_id = ui.subject_select(subjects, "pulse_subject")
    rows = tracking.pulse_summary(subject_id)
    if not rows:
        ui.empty_state("This subject has no lessons yet. Add lessons in the Lesson Hub.")
        return

    rated = [r for r in rows if r["responses"]]
    flagged = [r for r in rows if r["flagged"]]
    ui.metrics([("Lessons", len(rows)),
                ("Average confidence", f"{utils.mean([r['average'] for r in rated]):.1f} / 5" if rated else "—"),
                ("Response rate", utils.fmt_pct(utils.mean([r["response_rate"] for r in rows]))),
                ("Lessons needing review", len(flagged), f"Average below {settings['pulse_low_threshold']} "
                                                         "or 40%+ of students at 1-2")])

    if flagged:
        names = ", ".join(f"**{r['lesson']}**" for r in flagged)
        st.error(f"Consider re-teaching or adding support for: {names}", icon="🚩")
    elif rated:
        st.success("No lessons are flagged — the class feels reasonably confident.", icon="💪")

    if rated:
        st.subheader("Confidence by lesson")
        chart = []
        for r in rated:
            for level in range(1, 6):
                chart.append({"Lesson": r["lesson"], "Rating": f"{level} - {tracking.CONFIDENCE_LABELS[level].split(' - ')[1]}",
                              "Students": r["distribution"][level]})
        ui.bar_chart(chart, x="Lesson", y="Students", color="Rating", horizontal=True, height=60 + 45 * len(rated))
        st.caption("Each bar shows how many students chose each rating. Red/orange-heavy bars = confusing lessons.")

    st.subheader("Lesson details")
    table = [{"Topic": r["topic"], "Lesson": r["lesson"], "Average": r["average"],
              "Responses": f"{r['responses']}/{r['class_size']}", "Low (1-2)": utils.fmt_pct(r["low_share"]),
              "Status": "🚩 Review" if r["flagged"] else ("✅ OK" if r["responses"] else "No ratings")}
             for r in sorted(rows, key=lambda r: (r["average"] is None, r["average"] or 0))]
    ui.table(table, {"Average": st.column_config.ProgressColumn("Average", min_value=0, max_value=5, format="%.1f")})

    with_notes = [r for r in rows if r["notes"]]
    if with_notes:
        st.subheader("💬 Anonymous comments")
        for r in with_notes:
            with st.expander(f"{r['lesson']} · {len(r['notes'])} comment(s)"):
                for note in r["notes"]:
                    st.markdown(f"> {note}")
