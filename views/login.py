"""Login & Sign-Up portal — Technical High-Contrast Edition."""

import streamlit as st

from classpilot import auth, school, storage, ui


def login_page():
    settings = storage.load_settings()
    existing_users = storage.load("users")

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "signup" if not existing_users else "signin"

    left, center, right = st.columns([0.4, 2.2, 0.4])
    with center:
        ui.page_transition(f"AUTH_{st.session_state['auth_mode'].upper()}")
        st.markdown(
            ":green-badge[● AUTH.GATEWAY] "
            ":blue-badge[◆ CRYPTO // PBKDF2-SHA256] "
            ":violet-badge[▲ DB // JSON.PERSIST] "
            f":orange-badge[■ ACCOUNTS // {len(existing_users)}]"
        )

        st.title("■ :green[CLASSPILOT] :blue[OS]")
        st.caption(f"▸ {settings['school_name'].upper()} · TECHNICAL LEARNING MANAGEMENT SYSTEM")
        st.divider()

        mode_col1, mode_col2 = st.columns(2)
        if mode_col1.button(
            "Sign In to Existing Account",
            icon=":material/login:",
            type="primary" if st.session_state["auth_mode"] == "signin" else "secondary",
            width="stretch",
            key="switch_signin",
        ):
            st.session_state["auth_mode"] = "signin"
            st.rerun()
        if mode_col2.button(
            "Create New Account (Sign Up)",
            icon=":material/person_add:",
            type="primary" if st.session_state["auth_mode"] == "signup" else "secondary",
            width="stretch",
            key="switch_signup",
        ):
            st.session_state["auth_mode"] = "signup"
            st.rerun()

        # ==================================================================
        # SIGN UP — Create Account (asks Student or Teacher -> opens Dashboard)
        # ==================================================================
        if st.session_state["auth_mode"] == "signup":
            with st.container(border=True):
                st.markdown(":blue-badge[◆ NEW OPERATOR REGISTRATION] :violet-badge[● INSTANT WORKSPACE PROVISIONING]")
                st.subheader("■ Create Your Account")
                st.caption("Select whether you are a Student or a Teacher — your dashboard and AI workspace will be configured automatically.")

                role_choice = st.radio(
                    "Select Account Role — Are you a Student or a Teacher?",
                    options=["teacher", "student"],
                    format_func=lambda r: (
                        "◆ Teacher — Build my own custom dashboard, classes, assignments to check & AI Copilot"
                        if r == "teacher"
                        else "● Student — Access lessons, submit assignments, take quizzes, track grades & AI Tutor"
                    ),
                    horizontal=False,
                    key="signup_role_radio",
                )

                with st.form("signup_form"):
                    c1, c2 = st.columns(2)
                    full_name = c1.text_input("Full Name", placeholder="e.g. Ayesha Tariq")
                    username = c2.text_input(
                        "Username",
                        placeholder="e.g. ayesha.tariq",
                        help="3–30 characters: lowercase letters, numbers, dots (.) or underscores (_).",
                    )
                    email = st.text_input("Email Address (optional)", placeholder="e.g. ayesha@school.edu")

                    class_input = ""
                    if role_choice == "student":
                        existing_classes = [c["name"] for c in school.all_classes()]
                        if existing_classes:
                            class_input = st.selectbox(
                                "Select Your Class",
                                options=[""] + existing_classes,
                                format_func=lambda v: v if v else "— Select or join later on Dashboard —",
                            )
                        else:
                            class_input = st.text_input(
                                "Your Class / Grade (optional)",
                                placeholder="e.g. Grade 9 - A",
                            )

                    p1, p2 = st.columns(2)
                    password = p1.text_input(
                        "Password",
                        type="password",
                        help="At least 8 characters including a letter and a number.",
                    )
                    confirm_password = p2.text_input("Confirm Password", type="password")

                    remember_signup = st.checkbox(
                        "Remember me (stay signed in automatically)",
                        value=True,
                        help="Keep your account signed in on this browser/device so you don't have to log in every time.",
                    )

                    create_submitted = st.form_submit_button(
                        f"Initialize {role_choice.title()} Account & Launch Dashboard",
                        type="primary",
                        width="stretch",
                        icon=":material/person_add:",
                    )

                if create_submitted:
                    new_user, err = school.register_account(
                        username=username,
                        full_name=full_name,
                        email=email,
                        role=role_choice,
                        password=password,
                        confirm_password=confirm_password,
                        class_name=class_input,
                    )
                    if err:
                        st.error(err, icon=":material/error:")
                    else:
                        auth.login_session(new_user, remember=remember_signup)
                        st.session_state.setdefault("_flash", []).append((
                            f"Account initialized! Welcome to your {role_choice.title()} Dashboard, {new_user['full_name'].split()[0]}.",
                            ":material/check_circle:",
                        ))
                        st.rerun()

        # ==================================================================
        # SIGN IN — Existing Account
        # ==================================================================
        else:
            with st.container(border=True):
                st.markdown(":green-badge[● AUTHENTICATION TERMINAL] :blue-badge[◆ SESSION LOGIN]")
                st.subheader("■ Sign In")
                if not existing_users:
                    st.info("No accounts exist yet. Click **Create New Account (Sign Up)** above to register as a Teacher or Student.", icon=":material/person_add:")
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="Enter your username")
                    password = st.text_input("Password", type="password")
                    remember_signin = st.checkbox(
                        "Remember me (stay signed in automatically)",
                        value=True,
                        help="Keep your account signed in on this browser/device so you don't have to log in every time.",
                    )
                    submitted = st.form_submit_button("Sign In & Launch Workspace", type="primary", width="stretch", icon=":material/login:")
                if submitted:
                    user, error = auth.authenticate(username, password)
                    if error:
                        st.error(error, icon=":material/error:")
                    else:
                        auth.login_session(user, remember=remember_signin)
                        st.session_state.setdefault("_flash", []).append(
                            (f"Session authenticated. Welcome back, {user['full_name'].split()[0]}.", ":material/check_circle:"))
                        st.rerun()
