"""My account page - profile details and password change (all roles)."""

import streamlit as st

from classpilot import auth, school, tracking, ui, utils


def profile_page():
    user = auth.require_role("admin", "teacher", "student")
    ui.page_header("My account", "Your profile and security settings.", "👤")

    left, right = st.columns(2)
    with left.container(border=True):
        st.subheader("Profile")
        st.markdown(f"**Name:** {user['full_name']}")
        st.markdown(f"**Username:** `{user['username']}`")
        st.markdown(f"**E-mail:** {user['email']}")
        st.markdown(f"**Role:** {ui.badge(user['role'].title())}")
        st.markdown(f"**Last sign-in:** {utils.fmt_dt(user.get('last_login'))}")
        if user["role"] == "student":
            cls = school.student_class(user["id"])
            st.markdown(f"**Class:** {cls['name'] if cls else 'Not assigned'}")
            st.markdown(f"**Overall average:** {utils.fmt_pct(tracking.overall_average(user['id']))}")
        if user["role"] == "teacher":
            subjects = school.subjects_for_teacher(user["id"])
            st.markdown("**Teaching:** " + (", ".join(school.subject_label(s) for s in subjects) or "No subjects yet"))
        st.caption("To change your name or e-mail, please contact the school admin.")

    with right.container(border=True):
        st.subheader("Change password")
        with st.form("change_password", clear_on_submit=True):
            current = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password",
                                help="At least 8 characters, including a letter and a number.")
            confirm = st.text_input("Confirm new password", type="password")
            submitted = st.form_submit_button("Update password", type="primary", icon="🔑")
        if submitted:
            ui.report(auth.change_password(user["id"], current, new, confirm), "Password updated.", "🔑")
