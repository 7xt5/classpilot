"""Announcements page - post updates and track who has read them."""

import streamlit as st

from classpilot import auth, school, ui, utils


def _post_form(user):
    """Form for admins (whole school or any class) and teachers (their classes)."""
    if user["role"] == "admin":
        targets = ["all"] + [c["id"] for c in school.all_classes()]
    else:
        targets = school.teacher_class_ids(user["id"])
    if not targets:
        st.info("You need to teach at least one class before posting announcements.")
        return
    with st.expander("✏️ Post a new announcement", expanded=False):
        with st.form("new_announcement", clear_on_submit=True):
            class_id = st.selectbox("Audience", targets, format_func=school.class_name)
            title = st.text_input("Title", max_chars=120)
            body = st.text_area("Message", height=140, max_chars=4000)
            col1, col2 = st.columns(2)
            priority = col1.selectbox("Priority", ["Normal", "Important", "Urgent"])
            pinned = col2.checkbox("📌 Pin to top", help="Pinned posts stay at the top of everyone's list.")
            submitted = st.form_submit_button("Post announcement", type="primary", icon="📢")
        if submitted:
            _, error = school.create_announcement(user, class_id, title, body, pinned, priority)
            ui.report(error, "Announcement posted.", "📢")


def _read_receipts(announcement):
    """Show who has / hasn't read a post (only for its author or admins)."""
    audience = school.announcement_audience(announcement)
    read = [p for p in audience if p["id"] in announcement.get("read_by", [])]
    unread = [p for p in audience if p["id"] not in announcement.get("read_by", [])]
    if not audience:
        st.caption("No audience yet.")
        return
    st.progress(len(read) / len(audience), text=f"Read by {len(read)} of {len(audience)}")
    if unread:
        st.caption("Not read yet: " + ", ".join(p["full_name"] for p in unread))


def announcements_page():
    user = auth.require_role("admin", "teacher", "student")
    ui.page_header("Announcements", "Class-specific updates with read tracking.", "📢")

    if user["role"] in ("admin", "teacher"):
        _post_form(user)

    items = school.announcements_for_user(user)
    unread_total = sum(1 for a in items if school.is_unread(a, user["id"]))

    # ---- Filters -----------------------------------------------------------
    col1, col2, col3, col4 = st.columns([2, 1.3, 1.3, 1])
    query = col1.text_input("Search announcements", placeholder="Search title or message")
    class_options = ["any"] + sorted({a["class_id"] for a in items}, key=school.class_name)
    class_filter = col2.selectbox("Audience", class_options,
                                  format_func=lambda c: "All audiences" if c == "any" else school.class_name(c))
    show = col3.selectbox("Show", ["All", "Unread only", "Pinned only", "Posted by me"])
    with col4:
        st.write("")
        st.write("")
        if st.button("Mark all read", disabled=unread_total == 0, width="stretch", icon="✔️"):
            school.mark_all_read(user)
            ui.done("All announcements marked as read.")

    if query:
        items = [a for a in items if utils.matches(query, a["title"], a["body"])]
    if class_filter != "any":
        items = [a for a in items if a["class_id"] == class_filter]
    if show == "Unread only":
        items = [a for a in items if school.is_unread(a, user["id"])]
    elif show == "Pinned only":
        items = [a for a in items if a.get("pinned")]
    elif show == "Posted by me":
        items = [a for a in items if a["author_id"] == user["id"]]

    st.caption(f"{len(items)} announcement(s) · {unread_total} unread")
    if not items:
        ui.empty_state("No announcements match your filters.")
        return

    # ---- List ------------------------------------------------------------
    for item in items:
        unread = school.is_unread(item, user["id"])
        with st.container(border=True):
            badges = []
            if unread:
                badges.append(ui.badge("New"))
            if item.get("pinned"):
                badges.append(ui.badge("Pinned"))
            if item.get("priority", "Normal") != "Normal":
                badges.append(ui.badge(item["priority"]))
            st.markdown(f"### {item['title']}  \n" + " ".join(badges))
            st.caption(f"{school.user_name(item['author_id'])} → {school.class_name(item['class_id'])} · "
                       f"{utils.fmt_dt(item['created_at'])}")
            st.markdown(item["body"])

            buttons = st.columns([1, 1, 1, 3])
            if item["author_id"] != user["id"]:
                if unread:
                    if buttons[0].button("Mark as read", key=f"read_{item['id']}", icon="✔️"):
                        school.mark_read(item["id"], user["id"])
                        st.rerun()
                elif buttons[0].button("Mark unread", key=f"unread_{item['id']}", icon="↩️"):
                    school.mark_unread(item["id"], user["id"])
                    st.rerun()
            if school.can_manage_announcement(user, item):
                if buttons[1].button("Unpin" if item.get("pinned") else "Pin", key=f"pin_{item['id']}", icon="📌"):
                    ui.report(school.toggle_pin(user, item["id"]), "Pin updated.", "📌")
                with buttons[2]:
                    if ui.confirm_button("Delete", f"del_ann_{item['id']}", "Delete this announcement for everyone?"):
                        ui.report(school.delete_announcement(user, item["id"]), "Announcement deleted.", "🗑️")
                with st.expander("👁️ Read receipts"):
                    _read_receipts(item)
