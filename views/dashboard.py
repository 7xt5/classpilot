"""Smart dashboards — White & Black Monochrome Edition with 100% Teacher-Driven Workspace."""

from datetime import datetime

import streamlit as st

from classpilot import auth, coursework, insights, school, storage, tracking, ui, utils


def _greeting(user):
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    return f"Good {part}, {user['full_name'].split()[0]}"


def _announcement_feed(user, limit=3):
    """Latest announcements with a quick 'mark as read' button."""
    items = school.announcements_for_user(user)[:limit]
    if not items:
        st.caption("No announcements yet.")
        return
    for item in items:
        unread = school.is_unread(item, user["id"])
        with st.container(border=True):
            tags = " ".join(t for t in [ui.badge("New") if unread else "",
                                        ui.badge("Pinned") if item.get("pinned") else "",
                                        ui.badge(item["priority"]) if item.get("priority", "Normal") != "Normal" else ""] if t)
            st.markdown(f"**{item['title']}** {tags}")
            st.caption(f"{school.user_name(item['author_id'])} · {school.class_name(item['class_id'])} · "
                       f"{utils.fmt_dt(item['created_at'])}")
            st.markdown(item["body"][:220] + ("…" if len(item["body"]) > 220 else ""))
            if unread and st.button("Mark as read", key=f"dash_read_{item['id']}", type="tertiary", icon=":material/check:"):
                school.mark_read(item["id"], user["id"])
                st.rerun()


def _render_student_class_join_panel(user):
    """Allow students to view Admin classes and click 'Join' to send a request to Admin."""
    cls = school.student_class(user["id"])
    all_cls = school.all_classes()
    my_requests = school.user_join_requests(user["id"])
    pending_by_cls = {r["class_id"]: r for r in my_requests if r.get("status") == "pending"}

    with st.container(border=True):
        if cls:
            st.markdown(f"**■ Your Current Class:** **{cls['name']}** ({cls.get('grade_level', '')} · {cls.get('room', '')}) — *Approved by Admin*")
            expand_label = "View All School Classes or Request to Switch Class"
            expanded_default = False
        else:
            st.markdown("**■ Join a Class (Request Sent to School Admin)**")
            st.caption("Click **Join Class** on your class below. Your request will be sent to the Admin, and once accepted you will enter the class.")
            expand_label = "Available School Classes (Click Join)"
            expanded_default = True

        with st.expander(expand_label, expanded=expanded_default):
            if not all_cls:
                st.caption("No classes have been created by the School Admin yet.")
            else:
                cols = st.columns(min(len(all_cls), 3))
                for idx, c in enumerate(all_cls):
                    col = cols[idx % len(cols)]
                    with col.container(border=True):
                        st.markdown(f"**{c['name']}**")
                        st.caption(f"{c.get('grade_level', 'Class')} · {c.get('room', 'Room TBD')} · {len(c.get('student_ids', []))} student(s)")
                        if cls and cls["id"] == c["id"]:
                            st.markdown("**[ ● Joined & Approved ]**")
                        elif c["id"] in pending_by_cls:
                            req = pending_by_cls[c["id"]]
                            st.markdown("**[ ◆ Request Sent — Pending Admin Approval ]**")
                            if st.button("Cancel Request", key=f"stu_cancel_req_{req['id']}", type="secondary", width="stretch"):
                                school.cancel_join_request(req["id"], user["id"])
                                ui.done(f"Cancelled join request for {c['name']}.")
                        else:
                            if st.button(
                                "Join Class",
                                key=f"stu_join_cls_{c['id']}",
                                type="primary",
                                icon=":material/group_add:",
                                width="stretch",
                            ):
                                _, err = school.request_join_class(user["id"], c["id"])
                                ui.report(err, f"Request to join '{c['name']}' sent to Admin for approval!")


# ==========================================================================
# Student Dashboard (Monochrome White & Black)
# ==========================================================================
def student_dashboard():
    user = auth.require_role("student")
    ui.page_header(_greeting(user), datetime.now().strftime("%A, %d %B %Y"))
    _render_student_class_join_panel(user)


    settings = storage.load_settings()
    todo = insights.student_todo(user["id"])
    missing = [t for t in todo if t["status"] == "Missing"]
    due_week = [t for t in todo if t["status"] != "Missing"
                and (utils.parse_dt(t["due"]) - datetime.now()).days < 7]
    items = tracking.grade_items_for_student(user["id"])
    overall = utils.mean([i["percent"] for i in items])
    trend = tracking.grade_trend(items)
    attendance = tracking.attendance_summary(user["id"], [s["id"] for s in school.subjects_for_student(user["id"])])
    ui.metrics([
        ("Due this week", len(due_week), "Assignments and quizzes due in the next 7 days"),
        ("Missing work", len(missing), "Past the deadline and not handed in"),
        ("Overall average", utils.fmt_pct(overall), None, f"{trend[2]:+.1f} pts recently" if trend else None),
        ("Attendance", utils.fmt_pct(attendance["percent"])),
    ])

    if missing:
        with st.container(border=True):
            st.markdown(f"**[ ▲ Missing Work ]** You have **{len(missing)}** missing item(s). Late work is still accepted for most assignments — hand it in as soon as you can.")
    if attendance["percent"] is not None and attendance["percent"] < settings["alert_attendance"]:
        with st.container(border=True):
            st.markdown(f"**[ ▲ Attendance Alert ]** Your attendance is below the {settings['alert_attendance']}% target.")

    # Creative Milestone Badges
    milestones = insights.student_milestones(user["id"])
    with st.container(border=True):
        st.markdown("**■ YOUR NOVARIX MILESTONES**")
        m_cols = st.columns(len(milestones))
        for col, (b_title, b_desc) in zip(m_cols, milestones):
            col.markdown(f"**{b_title}**")
            col.caption(b_desc)

    left, right = st.columns([3, 2])
    with left:
        st.subheader("■ Your To-Do List")
        if not todo:
            with st.container(border=True):
                st.markdown("**[ ● All Caught Up ]** You have completed all upcoming items.")
        for task in todo[:8]:
            status = "Missing" if task["status"] == "Missing" else task["kind"]
            with st.container(border=True):
                st.markdown(f"{ui.badge(status)} **{task['title']}**  \n"
                            f":gray[{task['subject']} · due {utils.fmt_dt(task['due'])} — {utils.relative_due(task['due'])}]")
        if len(todo) > 8:
            st.caption(f"…and {len(todo) - 8} more on the Assignments and Quizzes pages.")

        st.subheader("■ Recent Grades")
        recent = [i for i in reversed(items)][:5]
        if recent:
            ui.table([{"Item": i["title"], "Subject": i["subject"].split(" · ")[0], "Score": f"{i['score']:g}/{i['max']}",
                       "Percent": i["percent"], "Feedback": i["feedback"]} for i in recent],
                     {"Percent": ui.pct_column("Percent")})
        else:
            st.caption("No grades yet.")

    with right:
        spotlight = insights.daily_concept_spotlight(user["id"])
        if spotlight:
            st.subheader("■ Daily Concept Spotlight")
            with st.container(border=True):
                st.markdown(f"**{spotlight['title']}**  \n:gray[{spotlight['subject']} · {spotlight['topic']}]")
                st.markdown(spotlight["snippet"])
                ui.page_link("assistant", "Ask NovaAI Tutor about this", ":material/smart_toy:")

        st.subheader("■ Announcements")
        _announcement_feed(user)
        st.subheader("■ NovaPulse")
        subject_ids = [s["id"] for s in school.subjects_for_student(user["id"])]
        unrated = [l for l in coursework.lessons_for_subjects(subject_ids) if not tracking.my_pulse(user["id"], l["id"])]
        if unrated:
            with st.container(border=True):
                st.markdown(f"**[ ○ Unrated Lessons ]** You haven't rated **{len(unrated)}** lesson(s) yet. Ratings are private and help your teachers know what to revisit.")
                ui.page_link("lessons", "Rate lessons", ":material/library_books:")
        else:
            with st.container(border=True):
                st.markdown("**[ ● Complete ]** You have rated every lesson. Thank you.")


# ==========================================================================
# Teacher Dashboard — 100% Teacher-Dependent Workspace
# Whatever the teacher adds (classes, assignments to check, tasks, widgets)
# is what appears on her dashboard.
# ==========================================================================
def _teacher_builder_panel(user, school_subjects, prefs, is_empty):
    """Top studio where the teacher adds classes, assignments to check, tasks, or widgets."""
    with st.expander("■ + BUILD & ADD TO MY DASHBOARD (Add Classes, Assignments to Check, Tasks & Widgets)", expanded=is_empty):
        st.caption("Your dashboard is 100% controlled by you — whatever you add below will immediately appear on your dashboard.")
        tab_cls, tab_asg, tab_task, tab_wid = st.tabs([
            "+ Add a Class",
            "+ Add Assignment to Check",
            "+ Add Task / Note",
            "+ Add Live Widget / Settings",
        ])

        # --- TAB 1: Join an Admin Class or Add Approved Class to Dashboard ---
        with tab_cls:
            c_left, c_right = st.columns([3, 2])
            with c_left:
                st.markdown("**Request to Join an Admin School Class**")
                st.caption("Select a class owned by the School Admin and enter the Subject you teach. Once the Admin accepts your request, the class & subject will be added to your workspace.")
                all_admin_classes = school.all_classes()
                if not all_admin_classes:
                    st.caption("No classes have been created by the Admin yet.")
                else:
                    with st.form("t_dash_add_class_form", clear_on_submit=True):
                        f1, f2 = st.columns(2)
                        picked_cls_id = f1.selectbox(
                            "Select Admin Class",
                            options=[c["id"] for c in all_admin_classes],
                            format_func=school.class_name,
                        )
                        subj_name = f2.text_input("Subject You Teach", placeholder="e.g. Mathematics")
                        if st.form_submit_button("Join Class (Send Request to Admin)", type="primary", icon=":material/group_add:", width="stretch"):
                            _, err = school.request_join_class(
                                user["id"], picked_cls_id, subject_name=subj_name or "General Studies"
                            )
                            ui.report(err, f"Join request for '{school.class_name(picked_cls_id)}' sent to Admin for approval.")

            with c_right:
                st.markdown("**Add Approved Subject to Dashboard**")
                if not school_subjects:
                    st.caption("Once the Admin accepts your class join request, your approved subjects will appear here and on your dashboard automatically.")
                else:
                    with st.form("t_dash_quick_subject_form", clear_on_submit=True):
                        picked_subj_id = st.selectbox(
                            "Select Approved Subject",
                            options=[s["id"] for s in school_subjects],
                            format_func=school.subject_label,
                        )
                        q_sched = st.text_input("Schedule / Time (optional)", placeholder="e.g. Tue / Thu · 10:30 AM")
                        q_notes = st.text_input("Notes (optional)", placeholder="e.g. Check lab books")
                        if st.form_submit_button("Add Approved Class to Dashboard", icon=":material/add:", width="stretch"):
                            err = insights.add_teacher_dashboard_class(
                                user["id"], "", "", "", q_sched, q_notes,
                                subject_id=picked_subj_id, register_in_school=False,
                            )
                            ui.report(err, "Added class to your dashboard.")

        # --- TAB 2: Add Assignment to Check ---
        with tab_asg:
            a_left, a_right = st.columns([3, 2])
            with a_left:
                st.markdown("**Add an Assignment to Check**")
                with st.form("t_dash_add_assignment_form", clear_on_submit=True):
                    a_title = st.text_input("Assignment Title to Check", placeholder="e.g. Quadratic Equations Problem Set")
                    default_classes = [f"{c['class_name']} · {c['subject_name']}" for c in prefs.get("added_classes", [])]
                    default_classes += [school.subject_label(s) for s in school_subjects if school.subject_label(s) not in default_classes]
                    a_class = st.text_input(
                        "Class / Subject",
                        value=default_classes[0] if default_classes else "",
                        placeholder="e.g. Grade 9 - A · Mathematics",
                    )
                    af1, af2 = st.columns(2)
                    a_count = af1.number_input("Submissions / Papers to Check", min_value=0, max_value=500, value=10, step=1)
                    a_prio = af2.selectbox("Priority", ["Normal", "High", "Urgent"])
                    af4, af5 = st.columns(2)
                    a_due = af4.text_input("Check By / Deadline Note", placeholder="e.g. Friday 5:00 PM")
                    a_notes = af5.text_input("Grading Notes (optional)", placeholder="e.g. Check Q4 working steps")
                    if st.form_submit_button("Add Assignment to Check", type="primary", icon=":material/add:", width="stretch"):
                        err = insights.add_teacher_dashboard_assignment(
                            user["id"], a_title, a_class, int(a_count), a_due, a_prio, a_notes
                        )
                        ui.report(err, f"Added '{a_title}' to your Assignments to Check.")

            with a_right:
                st.markdown("**Or Pick from Existing LMS Assignments**")
                all_asgs = coursework.assignments_for_subjects([s["id"] for s in school_subjects])
                if not all_asgs:
                    st.caption("No LMS assignments created yet. Use the form on the left to add any assignment to check.")
                else:
                    with st.form("t_dash_pick_lms_asg", clear_on_submit=True):
                        picked_asg_id = st.selectbox(
                            "Existing Assignment",
                            options=[a["id"] for a in all_asgs],
                            format_func=lambda aid: f"{storage.get('assignments', aid)['title']} ({school.subject_label(storage.get('assignments', aid)['subject_id'])})",
                        )
                        picked_prio = st.selectbox("Priority", ["Normal", "High", "Urgent"], key="pick_asg_prio")
                        picked_note = st.text_input("Note (optional)", placeholder="e.g. Grade late submissions")
                        if st.form_submit_button("Add LMS Assignment to Check", icon=":material/add:", width="stretch"):
                            err = insights.add_teacher_dashboard_assignment(
                                user["id"], priority=picked_prio, notes=picked_note, assignment_id=picked_asg_id
                            )
                            ui.report(err, "Assignment added to your dashboard to check.")

        # --- TAB 3: Add Task / Note / Reminder ---
        with tab_task:
            st.markdown("**Add a Teaching Task, Lesson Prep Note, or Reminder**")
            with st.form("add_check_item_form", clear_on_submit=True):
                t1, t2, t3 = st.columns([2.5, 1.3, 1.5])
                new_title = t1.text_input("Task or Note", placeholder="e.g. Prepare Friday Lab Quiz or Call Yusuf's parent")
                category = t2.selectbox("Category", ["Assignment to Check", "Class to Check", "Lesson Prep", "Student Follow-up", "Note"])
                target_opts = ["General"] + [f"{c['class_name']} · {c['subject_name']}" for c in prefs.get("added_classes", [])] + [school.subject_label(s) for s in school_subjects]
                target_opts = list(dict.fromkeys(target_opts))
                target = t3.selectbox("Class / Subject", target_opts)
                if st.form_submit_button("Add Task / Note to Dashboard", type="primary", icon=":material/add:", width="stretch"):
                    err = insights.add_teacher_check_item(user["id"], new_title, category, "" if target == "General" else target)
                    ui.report(err, "Added to your dashboard.")

        # --- TAB 4: Add Live Widget / Settings ---
        with tab_wid:
            w_left, w_right = st.columns([3, 2])
            with w_left:
                st.markdown("**Optional: Add Live LMS Analytics Widgets to Dashboard**")
                with st.form("teacher_widget_prefs"):
                    chosen_widgets = st.multiselect(
                        "Select Live Widgets to Display on Your Dashboard",
                        options=list(insights.TEACHER_WIDGETS.keys()),
                        default=[w for w in prefs.get("widgets", []) if w in insights.TEACHER_WIDGETS],
                        format_func=lambda k: insights.TEACHER_WIDGETS[k],
                    )
                    focus_note = st.text_input(
                        "Personal Dashboard Banner / Focus Note",
                        value=prefs.get("focus_note", ""),
                        placeholder="e.g. Week 6 Focus: Check Grade 9-A Quadratics & Lab Reports",
                    )
                    if st.form_submit_button("Save Widgets & Banner", type="primary", icon=":material/check:", width="stretch"):
                        insights.save_teacher_prefs(user["id"], {
                            "widgets": chosen_widgets,
                            "focus_note": utils.clean(focus_note, 200),
                        })
                        ui.done("Dashboard widgets and banner updated.")
            with w_right:
                st.markdown("**Reset Dashboard**")
                st.caption("Want to wipe your dashboard completely blank and start fresh?")
                if st.button("Clear All Dashboard Items", key="clear_all_teacher_dash", icon=":material/delete:", width="stretch"):
                    insights.clear_teacher_dashboard(user["id"])
                    ui.done("Dashboard cleared. Add whatever you need above.")


def _render_added_classes(user, added_classes):
    """Render the exact classes the teacher added to her dashboard."""
    st.subheader(f"■ My Dashboard Classes ({len(added_classes)})")
    cols = st.columns(min(len(added_classes), 3))
    for idx, cls_item in enumerate(added_classes):
        col = cols[idx % len(cols)]
        with col.container(border=True):
            top_l, top_r = st.columns([4, 1])
            top_l.markdown(f"**{cls_item['class_name']} · {cls_item['subject_name']}**")
            if top_r.button("✕", key=f"rm_dcls_{cls_item['id']}", help="Remove class from dashboard"):
                insights.remove_teacher_dashboard_class(user["id"], cls_item["id"])
                st.rerun()

            meta = [m for m in [cls_item.get("room"), cls_item.get("schedule")] if m]
            if meta:
                st.caption(" · ".join(meta))

            # If linked to a real LMS subject, show live counts
            subj = school.get_subject(cls_item.get("subject_id")) if cls_item.get("subject_id") else None
            if subj:
                stu_count = len(school.class_students(subj["class_id"]))
                open_asgs = len([a for a in coursework.assignments_for_subjects([subj["id"]]) if not utils.is_past(a["due"])])
                ungraded, _ = coursework.grading_queue([subj["id"]])
                st.markdown(f":gray[Students: **{stu_count}** · Open Assignments: **{open_asgs}** · Ungraded: **{len(ungraded)}**]")

            if cls_item.get("notes"):
                st.markdown(f"*{cls_item['notes']}*")


def _render_added_assignments(user, school_subjects, prefs):
    """Render the exact 'Assignments to Check' that the teacher added or pinned."""
    added_asgs = list(prefs.get("added_assignments", []))

    # Also include any pinned_assignment_ids if the teacher pinned them
    subject_ids = [s["id"] for s in school_subjects]
    all_lms_asgs = {a["id"]: a for a in coursework.assignments_for_subjects(subject_ids)}
    already_linked_ids = {item.get("assignment_id") for item in added_asgs if item.get("assignment_id")}
    for pid in prefs.get("pinned_assignment_ids", []):
        if pid in all_lms_asgs and pid not in already_linked_ids:
            asg = all_lms_asgs[pid]
            subs = coursework.submissions_for_assignment(pid)
            added_asgs.append({
                "id": f"pin_{pid}",
                "title": asg["title"],
                "class_subject": school.subject_label(asg["subject_id"]),
                "assignment_id": pid,
                "total_to_check": len(subs),
                "checked_count": len([s for s in subs if s.get("score") is not None]),
                "due_note": f"Due {utils.fmt_dt(asg['due'])}",
                "priority": "Normal",
                "notes": "",
                "done": False,
                "_pinned_only": True,
            })

    pending_count = sum(1 for a in added_asgs if not a.get("done"))
    st.subheader(f"■ Assignments to Check ({pending_count} to check / {len(added_asgs)} total)")

    for item in added_asgs:
        is_done = item.get("done", False)
        status_label = "Checked" if is_done else "To Check"
        prio = item.get("priority", "Normal")
        total = item.get("total_to_check", 0)
        checked = item.get("checked_count", 0)

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3.5, 1.3, 1.2, 0.7])
            title_md = f"~~{item['title']}~~" if is_done else f"**{item['title']}**"
            prio_badge = f" {ui.badge(prio)}" if prio != "Normal" else ""
            c1.markdown(f"{ui.badge(status_label)}{prio_badge} {title_md}")
            meta_parts = [item.get("class_subject", "")]
            if item.get("due_note"):
                meta_parts.append(item["due_note"])
            if total > 0:
                meta_parts.append(f"Checked: {checked}/{total}")
            c1.caption(" · ".join(p for p in meta_parts if p))
            if item.get("notes"):
                c1.markdown(f":gray[{item['notes']}]")

            if not item.get("_pinned_only"):
                if total > 0 and not is_done:
                    if c2.button("+1 Checked", key=f"step_dasg_{item['id']}", width="stretch"):
                        insights.step_teacher_dashboard_assignment(user["id"], item["id"], 1)
                        st.rerun()
                else:
                    c2.write("")

                toggle_lbl = "Reopen" if is_done else "Mark Checked"
                if c3.button(toggle_lbl, key=f"tog_dasg_{item['id']}", width="stretch",
                             type="secondary" if is_done else "primary"):
                    insights.toggle_teacher_dashboard_assignment(user["id"], item["id"])
                    st.rerun()

                if c4.button("✕", key=f"rm_dasg_{item['id']}", help="Remove from dashboard"):
                    insights.remove_teacher_dashboard_assignment(user["id"], item["id"])
                    st.rerun()
            else:
                if c4.button("✕", key=f"rm_pin_{item['assignment_id']}", help="Unpin assignment"):
                    rem = [x for x in prefs.get("pinned_assignment_ids", []) if x != item["assignment_id"]]
                    insights.set_pinned_assignments(user["id"], rem)
                    st.rerun()


def _render_added_tasks(user, items):
    """Render custom tasks, class-to-check items, or notes added by the teacher."""
    done_count = sum(1 for i in items if i.get("done"))
    st.subheader(f"■ My Tasks & Notes ({done_count}/{len(items)} completed)")
    for item in items:
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.6, 4.6, 0.8])
            is_done = item.get("done", False)
            if c1.button("●" if is_done else "○", key=f"chk_tog_{item['id']}", help="Toggle completed"):
                insights.toggle_teacher_check_item(user["id"], item["id"])
                st.rerun()
            title_md = f"~~{item['title']}~~" if is_done else f"**{item['title']}**"
            target_str = item.get("target", "")
            c2.markdown(f"{ui.badge(item.get('category', 'Task'))} {title_md}" + (f"  \n:gray[{target_str}]" if target_str else ""))
            if c3.button("✕", key=f"chk_del_{item['id']}", help="Remove item"):
                insights.delete_teacher_check_item(user["id"], item["id"])
                st.rerun()


def _widget_header(user, widget_key, title):
    """Header for an optional live widget with an inline Remove button."""
    h_left, h_right = st.columns([5, 1])
    h_left.subheader(title)
    if h_right.button("✕ Remove", key=f"rm_wid_{widget_key}", help="Remove this widget from your dashboard"):
        insights.remove_teacher_widget(user["id"], widget_key)
        st.rerun()


def _render_teacher_class_join_panel(user, school_subjects):
    """Allow teachers to see all Admin classes and click 'Join' to send a request to Admin."""
    all_cls = school.all_classes()
    my_requests = school.user_join_requests(user["id"])
    pending_reqs = [r for r in my_requests if r.get("status") == "pending"]
    approved_cls_ids = set(school.teacher_class_ids(user["id"]))

    with st.container(border=True):
        st.markdown("**■ Join a School Class (Request Sent to School Admin)**")
        st.caption(
            "All school classes are managed by the Admin. Enter the Subject you teach and click **Join Class** on any class below — "
            "once the Admin accepts your request, you will enter the class and can post lessons, assignments, quizzes, and grades."
        )
        subj_input_col, _ = st.columns([2, 2])
        default_subj = subj_input_col.text_input(
            "Subject You Teach (for joining a class)",
            value="Mathematics",
            placeholder="e.g. Mathematics, Physics, English",
            key="teacher_join_subj_input",
        )

        if not all_cls:
            st.caption("No classes have been created by the School Admin yet.")
        else:
            cols = st.columns(min(len(all_cls), 3))
            for idx, c in enumerate(all_cls):
                col = cols[idx % len(cols)]
                with col.container(border=True):
                    st.markdown(f"**{c['name']}**")
                    st.caption(f"{c.get('grade_level', 'Class')} · {c.get('room', 'Room TBD')} · {len(c.get('student_ids', []))} student(s)")
                    my_subjs_in_cls = [s["name"] for s in school_subjects if s["class_id"] == c["id"]]
                    cls_pending = [r for r in pending_reqs if r["class_id"] == c["id"]]

                    if my_subjs_in_cls:
                        st.markdown(f"**[ ● Approved: {', '.join(my_subjs_in_cls)} ]**")
                    elif c["id"] in approved_cls_ids:
                        st.markdown("**[ ● Approved in Class ]**")

                    for req in cls_pending:
                        st.markdown(f"**[ ◆ Pending Approval: {req.get('subject_name') or 'General'} ]**")
                        if st.button("Cancel Request", key=f"t_cancel_req_{req['id']}", type="secondary", width="stretch"):
                            school.cancel_join_request(req["id"], user["id"])
                            ui.done(f"Cancelled request for {c['name']}.")

                    if not cls_pending:
                        if st.button(
                            "Join Class",
                            key=f"t_join_cls_btn_{c['id']}",
                            type="primary" if not my_subjs_in_cls else "secondary",
                            icon=":material/group_add:",
                            width="stretch",
                        ):
                            _, err = school.request_join_class(
                                user["id"], c["id"], subject_name=default_subj or "General Studies"
                            )
                            ui.report(err, f"Request to join '{c['name']}' ({default_subj or 'General Studies'}) sent to Admin!")


def teacher_dashboard():
    user = auth.require_role("teacher")
    prefs = insights.get_teacher_prefs(user["id"])
    subtitle = prefs.get("focus_note") or datetime.now().strftime("%A, %d %B %Y")
    ui.page_header(_greeting(user), subtitle)

    school_subjects = school.subjects_for_teacher(user["id"])
    added_classes = prefs.get("added_classes", [])
    added_assignments = prefs.get("added_assignments", [])
    pinned_ids = prefs.get("pinned_assignment_ids", [])
    check_items = prefs.get("check_items", [])
    active_widgets = [w for w in prefs.get("widgets", []) if w in insights.TEACHER_WIDGETS]

    is_empty = not (added_classes or added_assignments or pinned_ids or check_items or active_widgets)

    # 1. Join an Admin Class (Request sent to Admin)
    _render_teacher_class_join_panel(user, school_subjects)

    # 2. Teacher Dashboard Builder
    _teacher_builder_panel(user, school_subjects, prefs, is_empty)

    if is_empty:
        with st.container(border=True):
            st.markdown("### ■ YOUR DASHBOARD IS READY FOR YOUR SETUP")
            st.markdown(
                "This dashboard is **100% dependent on what you add**. Nothing is placed here automatically.\n\n"
                "- Open **+ Add a Class** above to add the classes and subjects you want on your dashboard.\n"
                "- Open **+ Add Assignment to Check** above to list assignments or homework sets you need to check.\n"
                "- Open **+ Add Task / Note** or **+ Add Live Widget** to add reminders or live class analytics."
            )
        return

    # Summary strip reflecting ONLY what the teacher has added to her dashboard
    unchecked_asgs = sum(1 for a in added_assignments if not a.get("done"))
    open_tasks = sum(1 for t in check_items if not t.get("done"))
    ui.metrics([
        ("My Added Classes", len(added_classes), "Classes you added to your dashboard"),
        ("Assignments to Check", unchecked_asgs, f"{len(added_assignments)} total added"),
        ("Pending Tasks / Notes", open_tasks, f"{len(check_items)} total added"),
        ("Active Live Widgets", len(active_widgets), "Optional live widgets you enabled"),
    ])

    # 1. Teacher-Added Classes
    if added_classes:
        _render_added_classes(user, added_classes)

    # 2. Teacher-Added Assignments to Check
    if added_assignments or pinned_ids:
        _render_added_assignments(user, school_subjects, prefs)

    # 3. Teacher-Added Tasks / Notes
    if check_items:
        _render_added_tasks(user, check_items)

    # 4. Optional Live LMS Widgets (ONLY rendered if the teacher explicitly added them)
    if active_widgets:
        subject_ids = [s["id"] for s in school_subjects]
        queue, _ = coursework.grading_queue(subject_ids) if subject_ids else ([], [])
        alerts = insights.support_alerts(school_subjects) if school_subjects else []
        conflicts = insights.teacher_conflicts(user["id"]) if school_subjects else []
        no_register = insights.attendance_not_taken_today(user["id"]) if school_subjects else []
        flagged_lessons = [(s, r) for s in school_subjects for r in tracking.pulse_summary(s["id"]) if r["flagged"]]

        if "metrics" in active_widgets:
            _widget_header(user, "metrics", "■ Live LMS Summary Metrics")
            ui.metrics([
                ("To grade in LMS", len(queue), "Submissions waiting for a grade"),
                ("Students to support", len({a["student_id"] for a in alerts}), "From Early Support Alerts"),
                ("Deadline clusters", len(conflicts), "Upcoming pile-ups across your classes"),
                ("Confusing lessons", len(flagged_lessons), "Flagged by NovaPulse"),
            ])

        if "climate" in active_widgets:
            _widget_header(user, "climate", "■ Class Climate & Mood Report")
            if not school_subjects:
                ui.empty_state("Add a class/subject to view its Class Climate report.")
            else:
                reports = insights.class_climate_report(school_subjects)
                c_cols = st.columns(len(reports))
                for col, rep in zip(c_cols, reports):
                    with col.container(border=True):
                        st.markdown(f"**{rep['weather']}**  \n**{rep['subject']}**")
                        st.caption(rep["summary"])
                        st.markdown(
                            f":gray[Avg: **{rep['average']}** · Attendance: **{rep['attendance']}** · "
                            f"Pulse: **{rep['pulse']}** · To check: **{rep['to_grade']}**]"
                        )

        if "priorities" in active_widgets:
            _widget_header(user, "priorities", "■ Today's Smart Priorities")
            priorities = 0
            if no_register:
                priorities += 1
                with st.container(border=True):
                    st.markdown("**[ ▲ Attendance Not Taken ]** " + ", ".join(school.subject_label(s) for s in no_register))
            if queue:
                priorities += 1
                oldest = queue[0]
                days = (datetime.now() - utils.parse_dt(oldest["submitted_at"])).days
                with st.container(border=True):
                    st.markdown(f"**[ ◆ Grading Queue ]** {len(queue)} submission(s) waiting — oldest has waited {days} day(s).")
            high = [a for a in alerts if a["level"] == "High"]
            if high:
                priorities += 1
                with st.container(border=True):
                    st.markdown("**[ ▲ High-Priority Support ]** " + "; ".join(
                        f"**{a['student']}** ({a['subject'].split(' · ')[0]}: {', '.join(a['reasons'])})" for a in high[:3]
                    ))
            for cluster in conflicts[:2]:
                priorities += 1
                with st.container(border=True):
                    st.markdown(
                        f"**[ ▲ Deadline Cluster ]** **{cluster['class']}** has {len(cluster['items'])} deadlines between "
                        f"{cluster['start'].strftime('%a %d %b')} and {cluster['end'].strftime('%a %d %b')}: "
                        + ", ".join(i["title"] for i in cluster["items"])
                    )
            for subject, row in flagged_lessons[:2]:
                priorities += 1
                with st.container(border=True):
                    st.markdown(
                        f"**[ ◆ NovaPulse Flag ]** **{row['lesson']}** ({subject['name']}) has low confidence "
                        f"(avg {row['average']:.1f}/5 from {row['responses']} students)."
                    )
            if not priorities:
                with st.container(border=True):
                    st.markdown("**[ ● Clear ]** Nothing urgent across your subjects.")

        if "deadlines" in active_widgets:
            _widget_header(user, "deadlines", "■ Upcoming Deadlines")
            upcoming = [a for a in coursework.assignments_for_subjects(subject_ids) if not utils.is_past(a["due"])]
            upcoming += [q for q in coursework.quizzes_for_subjects(subject_ids, published_only=True) if not utils.is_past(q["due"])]
            upcoming.sort(key=lambda x: x["due"])
            rows = []
            for item in upcoming[:8]:
                class_size = len(school.class_students(school.get_subject(item["subject_id"])["class_id"]))
                if "max_points" in item:
                    done = len([s for s in coursework.submissions_for_assignment(item["id"]) if not s.get("offline")])
                    kind = "Assignment"
                else:
                    done = len({a["student_id"] for a in coursework.attempts_for(item["id"])})
                    kind = "Quiz"
                rows.append({"Title": item["title"], "Type": kind, "Subject": school.subject_label(item["subject_id"]),
                             "Due": utils.relative_due(item["due"]), "Completed": utils.percent(done, class_size) or 0})
            ui.table(rows, {"Completed": ui.pct_column("Completed")})

        if "averages" in active_widgets:
            _widget_header(user, "averages", "■ Class Averages")
            averages = []
            for s in school_subjects:
                values = [tracking.subject_average(st_["id"], s["id"]) for st_ in school.class_students(s["class_id"])]
                averages.append({"Subject": school.subject_label(s), "Average %": utils.mean(values) or 0})
            ui.bar_chart(averages, x="Subject", y="Average %", height=240)

        if "announcements" in active_widgets:
            _widget_header(user, "announcements", "■ Announcements")
            _announcement_feed(user)


# ==========================================================================
# Admin Dashboard — Single Admin Owns All Classes & Approves Join Requests
# ==========================================================================
def render_admin_requests_and_classes(key_prefix="adm_dash"):
    """Shared Admin control center for accepting/declining Teacher & Student join requests
    and adding/removing classes."""
    pending = school.pending_join_requests()
    classes = school.all_classes()

    # 1. Pending Class Join Requests (Teachers & Students)
    st.subheader(f"■ Class Join Requests ({len(pending)} Pending)")
    if not pending:
        with st.container(border=True):
            st.markdown("**[ ● No Pending Requests ]** When a Teacher or Student clicks **Join Class**, their request appears here for your approval.")
    else:
        for req in pending:
            requester = school.get_user(req["user_id"])
            target_cls = school.get_class(req["class_id"])
            if not requester or not target_cls:
                continue
            role_tag = "TEACHER" if requester["role"] == "teacher" else "STUDENT"
            subj_note = f" · Subject: **{req['subject_name']}**" if req.get("subject_name") else ""
            with st.container(border=True):
                c_info, c_acc, c_dec = st.columns([3.4, 1.1, 0.9])
                c_info.markdown(
                    f"**[ {role_tag} ]** **{requester['full_name']}** (`{requester['username']}`) "
                    f"wants to join **{target_cls['name']}**{subj_note}"
                )
                c_info.caption(f"Requested {utils.fmt_dt(req['created_at'])}")
                if c_acc.button(
                    "Accept",
                    key=f"{key_prefix}_acc_{req['id']}",
                    type="primary",
                    icon=":material/check_circle:",
                    width="stretch",
                ):
                    err = school.approve_join_request(req["id"])
                    ui.report(err, f"Accepted {requester['full_name']} ({role_tag.title()}) into {target_cls['name']}.")
                if c_dec.button(
                    "Decline",
                    key=f"{key_prefix}_dec_{req['id']}",
                    type="secondary",
                    icon=":material/cancel:",
                    width="stretch",
                ):
                    err = school.reject_join_request(req["id"])
                    ui.report(err, f"Declined request from {requester['full_name']}.")

    # 2. Admin Class Manager — Add or Remove Classes
    st.subheader(f"■ Manage My Classes ({len(classes)} Total)")
    add_col, list_col = st.columns([1.4, 2.6])
    with add_col:
        with st.container(border=True):
            st.markdown("**+ Add a New Class**")
            with st.form(f"{key_prefix}_create_class_form", clear_on_submit=True):
                new_cls_name = st.text_input("Class Name", placeholder="e.g. Grade 9 - A")
                new_cls_grade = st.text_input("Grade Level", placeholder="e.g. Grade 9")
                new_cls_room = st.text_input("Room", placeholder="e.g. Room 104")
                if st.form_submit_button("Add Class", type="primary", icon=":material/add:", width="stretch"):
                    _, err = school.create_class(new_cls_name, new_cls_grade, new_cls_room)
                    ui.report(err, f"Class '{new_cls_name}' added.")

    with list_col:
        if not classes:
            with st.container(border=True):
                st.caption("No classes exist yet. Use **+ Add a New Class** on the left to create classes.")
        else:
            for cls in classes:
                cls_teachers = school.class_teachers(cls["id"])
                cls_students = school.class_students(cls["id"])
                cls_subjects = school.subjects_for_class(cls["id"])
                with st.container(border=True):
                    top_l, top_r = st.columns([3.5, 1.1])
                    top_l.markdown(f"**{cls['name']}** ({cls.get('grade_level', 'Grade')} · {cls.get('room', 'Room')})")
                    if top_r.button(
                        "Remove Class",
                        key=f"{key_prefix}_rm_cls_{cls['id']}",
                        type="secondary",
                        icon=":material/delete:",
                        width="stretch",
                    ):
                        err = school.delete_class(cls["id"])
                        ui.report(err, f"Removed class '{cls['name']}'.")
                    t_names = ", ".join(t["full_name"] for t in cls_teachers) or "None yet"
                    s_names = ", ".join(s["full_name"] for s in cls_students) or "None yet"
                    subj_names = ", ".join(f"{s['name']} ({school.user_name(s['teacher_id'])})" for s in cls_subjects) or "None yet"
                    st.caption(
                        f"Teachers ({len(cls_teachers)}): {t_names}  \n"
                        f"Subjects ({len(cls_subjects)}): {subj_names}  \n"
                        f"Students ({len(cls_students)}): {s_names}"
                    )


def admin_dashboard():
    user = auth.require_role("admin")
    settings = storage.load_settings()
    ui.page_header(_greeting(user), f"{settings['school_name']} · Admin Class & Request Manager")

    students = school.users_by_role("student", True)
    teachers = school.users_by_role("teacher", True)
    classes = school.all_classes()
    subjects = school.all_subjects()
    pending_reqs = school.pending_join_requests()
    all_ids = [s["id"] for s in subjects]
    attendance = utils.mean([tracking.attendance_summary(s["id"], all_ids)["percent"] for s in students])
    averages = [tracking.overall_average(s["id"]) for s in students]
    ui.metrics([
        ("Pending Requests", len(pending_reqs), "Teacher & Student join requests"),
        ("My Classes", len(classes), "All school classes"),
        ("Teachers", len(teachers)),
        ("Students", len(students)),
        ("Subjects", len(subjects)),
        ("School average", utils.fmt_pct(utils.mean(averages))),
    ])

    # Primary Admin Controls: Join Requests + Add/Remove Classes
    render_admin_requests_and_classes(key_prefix="adm_dash")

    st.divider()

    left, right = st.columns(2)
    with left:
        st.subheader("■ Class Performance Overview")
        rows = []
        for cls in classes:
            ids = [s["id"] for s in school.subjects_for_class(cls["id"])]
            members = school.class_students(cls["id"])
            rows.append({"Class": cls["name"], "Students": len(members), "Subjects": len(ids),
                         "Average": utils.mean([tracking.overall_average(m["id"]) for m in members]),
                         "Attendance": utils.mean([tracking.attendance_summary(m["id"], ids)["percent"] for m in members])})
        ui.table(rows, {"Average": ui.pct_column("Average"), "Attendance": ui.pct_column("Attendance")})

        st.subheader("■ Students Needing Support")
        alerts = insights.support_alerts(subjects)
        if alerts:
            ui.table([{"Student": a["student"], "Subject": a["subject"], "Priority": a["level"],
                       "Reasons": "; ".join(a["reasons"])} for a in alerts[:8]])
        else:
            with st.container(border=True):
                st.markdown("**[ ● Clear ]** No students flagged.")
    with right:
        st.subheader("■ Deadline Clusters")
        clusters = [c for cls in classes for c in insights.conflict_clusters(cls["id"])]
        if clusters:
            for c in clusters:
                with st.container(border=True):
                    st.markdown(f"**[ ▲ {c['class']} ]** {len(c['items'])} deadlines {c['start'].strftime('%d %b')}–"
                                f"{c['end'].strftime('%d %b')}")
        else:
            with st.container(border=True):
                st.markdown("**[ ● Clear ]** No upcoming clusters.")
        st.subheader("■ Latest Announcements")
        _announcement_feed(user)
