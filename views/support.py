"""Early Support Alerts and the Deadline Planner (teachers and admins)."""

import pandas as pd
import streamlit as st

from classpilot import auth, insights, school, storage, ui, utils


def _subjects_for(user):
    return school.all_subjects() if user["role"] == "admin" else school.subjects_for_teacher(user["id"])


# ==========================================================================
# Early Support Alerts
# ==========================================================================
def alerts_page():
    user = auth.require_role("teacher", "admin")
    settings = storage.load_settings()
    ui.page_header("Early Support Alerts", "Students who may need help, ranked by concern. Built from missing work, "
                   "low or declining grades and attendance.", "🚩")
    subjects = _subjects_for(user)
    if not subjects:
        ui.empty_state("No subjects to analyse yet.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        subject_filter = ui.subject_select(subjects, "alert_subject", include_all=True)
    level_filter = col2.multiselect("Priority", ["High", "Medium", "Low"], default=["High", "Medium", "Low"],
                                    key="alert_levels")
    chosen = subjects if subject_filter == "all" else [school.get_subject(subject_filter)]
    alerts = [a for a in insights.support_alerts(chosen) if a["level"] in level_filter]

    st.caption(f"Rules: ≥{settings['alert_missing_threshold']} missing items · average < {settings['alert_low_grade']}% · "
               f"drop ≥ {settings['alert_decline_points']} pts · attendance < {settings['alert_attendance']}%. "
               "Admins can change these in Settings.")
    ui.metrics([("Students flagged", len({a['student_id'] for a in alerts})),
                ("High priority", sum(1 for a in alerts if a["level"] == "High")),
                ("Medium", sum(1 for a in alerts if a["level"] == "Medium")),
                ("Low", sum(1 for a in alerts if a["level"] == "Low"))])
    if not alerts:
        st.success("No students currently match the alert rules. 🎉", icon="✅")
        return

    for alert in alerts:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.markdown(f"**{alert['student']}** {ui.badge(alert['level'])}  \n:gray[{alert['subject']}]  \n"
                          + " · ".join(alert["reasons"]))
            col2.metric("Average", utils.fmt_pct(alert["average"]),
                        f"{alert['trend'][2]:+.0f} pts" if alert["trend"] else None)
            col3.metric("Attendance", utils.fmt_pct(alert["attendance"]))
            col4.metric("Missing", len(alert["missing"]))
            with st.expander("Details & suggested actions"):
                if alert["missing"]:
                    st.markdown("**Missing work**")
                    ui.table([{"Type": m["kind"], "Title": m["title"], "Was due": utils.fmt_dt(m["due"])}
                              for m in alert["missing"]])
                if alert["items"]:
                    st.markdown("**Recent grades**")
                    st.line_chart(pd.DataFrame([{"Date": utils.parse_dt(i["date"]).date().isoformat(),
                                                 "Score %": i["percent"]} for i in alert["items"]]),
                                  x="Date", y="Score %", height=200)
                st.markdown("**Suggested next steps**")
                steps = []
                if alert["missing"]:
                    steps.append("Agree a catch-up plan for the missing work (you can still grade paper work in the gradebook).")
                if alert["trend"] and alert["trend"][2] < 0:
                    steps.append("Check in privately — a sudden drop often has a reason outside the classroom.")
                if alert["average"] is not None and alert["average"] < settings["alert_low_grade"]:
                    steps.append("Offer targeted practice or a help session on the weakest topics.")
                if alert["attendance"] is not None and alert["attendance"] < settings["alert_attendance"]:
                    steps.append("Contact home or the pastoral team about attendance.")
                for step in steps:
                    st.markdown(f"- {step}")
                student = school.get_user(alert["student_id"])
                st.caption(f"Contact: {student['email']}")


# ==========================================================================
# Deadline Planner
# ==========================================================================
def deadline_planner_page():
    user = auth.require_role("teacher", "admin")
    settings = storage.load_settings()
    ui.page_header("Deadline Planner", "See every class's workload across ALL subjects and spot deadline pile-ups "
                   "before students do.", "🗓️")
    class_ids = ([c["id"] for c in school.all_classes()] if user["role"] == "admin"
                 else school.teacher_class_ids(user["id"]))
    if not class_ids:
        ui.empty_state("No classes to plan for yet.")
        return

    clusters = [c for cid in class_ids for c in insights.conflict_clusters(cid)]
    if clusters:
        st.error(f"{len(clusters)} upcoming deadline cluster(s) found: {settings['conflict_max_deadlines']}+ deadlines "
                 f"within {settings['conflict_window_days']} days.", icon="⚠️")
        for cluster in clusters:
            with st.container(border=True):
                st.markdown(f"**{cluster['class']}** · {cluster['start'].strftime('%a %d %b')} → "
                            f"{cluster['end'].strftime('%a %d %b')} · {len(cluster['items'])} deadlines")
                ui.table([{"Due": utils.fmt_dt(i["due"]), "Type": i["kind"], "Title": i["title"],
                           "Subject": i["subject"].split(" · ")[0],
                           "Teacher": school.user_name(school.get_subject(i["subject_id"])["teacher_id"]),
                           "Yours": "✔" if school.get_subject(i["subject_id"])["teacher_id"] == user["id"] else ""}
                          for i in cluster["items"]])
                st.caption("Tip: move one of your own deadlines from the Assignments or Quiz Builder page — "
                           "the editor suggests a calmer date.")
    else:
        st.success("No deadline clusters in the upcoming weeks. 👍", icon="✅")

    st.subheader("Workload calendar")
    class_id = st.selectbox("Class", class_ids, format_func=school.class_name, key="planner_class")
    days = st.segmented_control("Range", [14, 28, 42], default=28, format_func=lambda d: f"{d // 7} weeks",
                                key="planner_days") or 28
    load = insights.daily_load(class_id, days)
    frame = pd.DataFrame(load)
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%a %d %b")
    st.bar_chart(frame, x="date", y="deadlines", height=260, sort=False)

    upcoming = [i for i in insights.class_deadlines(class_id) if not utils.is_past(i["due"])]
    st.markdown(f"**Upcoming deadlines for {school.class_name(class_id)}**")
    ui.table([{"Due": utils.fmt_dt(i["due"]), "When": utils.relative_due(i["due"]), "Type": i["kind"],
               "Title": i["title"], "Subject": i["subject"].split(" · ")[0]} for i in upcoming])

    st.subheader("Try a date")
    st.caption("Check a possible deadline before you set it.")
    default_day, default_time = ui.default_due(7)
    st.session_state.setdefault("planner_try_date", default_day)
    st.session_state.setdefault("planner_try_time", default_time)
    col1, col2 = st.columns(2)
    day = col1.date_input("Date", key="planner_try_date", format="DD/MM/YYYY")
    clock = col2.time_input("Time", key="planner_try_time", step=900)
    ui.deadline_check_panel(class_id, utils.combine(day, clock), "planner_try_date", "planner_try_time")
