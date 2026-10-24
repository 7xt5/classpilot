"""Landing Overview & Sign-Up / Sign-In Portal — Clean Dark Blue Edition."""

import streamlit as st

from classpilot import auth, school, storage, ui


def _render_landing_page(settings, existing_users):
    """Short, bold, clean front page explaining Novarix before Sign Up / Log In."""
    ui.page_transition("LANDING_OVERVIEW")
    logo = ui.logo_path()

    # Top Header Bar with custom Novarix logo and direct button to Sign Up / Log In
    if logo:
        logo_col, top_l, top_r = st.columns([0.4, 2.4, 1.0])
        with logo_col:
            st.image(logo, width="stretch")
    else:
        top_l, top_r = st.columns([2.6, 1.1])
    with top_l:
        st.title("Novarix")
        st.markdown("**Smart Classroom & AI Learning Workspace**")
    with top_r:
        st.write("")
        if st.button(
            "Sign Up / Log In",
            icon=":material/login:",
            type="primary",
            width="stretch",
            key="landing_top_auth_btn",
        ):
            st.session_state["show_auth_portal"] = True
            st.rerun()

    st.divider()

    # Clean, Bold Hero Card
    with st.container(border=True):
        st.header("Teach Smarter. Learn Faster.")
        st.markdown(
            "**One clean workspace to manage classes, submit coursework, track grades, and solve problems with AI.**"
        )
        cta1, cta2, _ = st.columns([1.2, 1.2, 1.6])
        if cta1.button(
            "Get Started (Sign Up)",
            icon=":material/person_add:",
            type="primary",
            width="stretch",
            key="hero_signup_btn",
        ):
            st.session_state["auth_mode"] = "signup"
            st.session_state["show_auth_portal"] = True
            st.rerun()
        if cta2.button(
            "Log In",
            icon=":material/login:",
            type="secondary",
            width="stretch",
            key="hero_signin_btn",
        ):
            st.session_state["auth_mode"] = "signin"
            st.session_state["show_auth_portal"] = True
            st.rerun()

    st.write("")

    # 2x2 Short, Bold Feature Grid
    row1_l, row1_r = st.columns(2)
    with row1_l:
        with st.container(border=True):
            st.subheader("Custom Teacher Studio")
            st.markdown("**Build your own dashboard. Add classes, track assignments to check, and grade work in one place.**")
    with row1_r:
        with st.container(border=True):
            st.subheader("Student Learning Hub")
            st.markdown("**Join your class, study lessons, submit assignments, take quizzes, and track your live grades.**")

    row2_l, row2_r = st.columns(2)
    with row2_l:
        with st.container(border=True):
            st.subheader("Built-In NovaAI Assistant")
            st.markdown("**Step-by-step math & science solver, Socratic study tutor, and instant AI rubric grader.**")
    with row2_r:
        with st.container(border=True):
            st.subheader("Live Classroom Signals")
            st.markdown("**Take attendance in seconds, check lesson confidence, and prevent deadline pile-ups.**")

    st.write("")
    with st.container(border=True):
        bot_l, bot_r = st.columns([2.4, 1.2])
        with bot_l:
            st.subheader("Ready to open your workspace?")
            st.markdown("**Sign up as a Student or a Teacher in seconds.**")
        with bot_r:
            st.write("")
            if st.button(
                "Continue to Sign Up / Log In",
                icon=":material/arrow_forward:",
                type="primary",
                width="stretch",
                key="bottom_go_auth_btn",
            ):
                st.session_state["show_auth_portal"] = True
                st.rerun()


def login_page():
    settings = storage.load_settings()
    existing_users = storage.load("users")

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "signup" if not existing_users else "signin"
    if "show_auth_portal" not in st.session_state:
        st.session_state["show_auth_portal"] = False

    # Step 1: Show the Overview / About Landing Page first until the user clicks to Sign Up / Log In
    if not st.session_state["show_auth_portal"]:
        _render_landing_page(settings, existing_users)
        return

    # Step 2: Sign Up / Log In Page
    left, center, right = st.columns([0.4, 2.2, 0.4])
    with center:
        ui.page_transition(f"AUTH_{st.session_state['auth_mode'].upper()}")

        back_col, _ = st.columns([1.1, 2.4])
        with back_col:
            if st.button("Back to Overview", icon=":material/arrow_back:", type="secondary", width="stretch", key="back_to_landing_btn"):
                st.session_state["show_auth_portal"] = False
                st.rerun()

        logo = ui.logo_path()
        if logo:
            lg_col, tx_col = st.columns([0.45, 2.55])
            with lg_col:
                st.image(logo, width="stretch")
            with tx_col:
                st.title("Novarix Account Portal")
                st.markdown("**Sign in or create a new Student or Teacher account**")
        else:
            st.title("Novarix Account Portal")
            st.markdown("**Sign in or create a new Student or Teacher account**")
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
                st.subheader("Create Your Account")
                st.markdown("**Select whether you are a Student or a Teacher.**")

                role_choice = st.radio(
                    "Account Role",
                    options=["teacher", "student"],
                    format_func=lambda r: (
                        "Teacher — Custom dashboard, classes, assignments to check & NovaAI Copilot"
                        if r == "teacher"
                        else "Student — Lessons, assignments, quizzes, grades & NovaAI Tutor"
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

                    existing_classes = [c["name"] for c in school.all_classes()]
                    class_input = ""
                    subject_input = ""
                    if existing_classes:
                        if role_choice == "teacher":
                            tc1, tc2 = st.columns(2)
                            class_input = tc1.selectbox(
                                "Request to Join Class (optional)",
                                options=[""] + existing_classes,
                                format_func=lambda v: v if v else "— Join later on Dashboard —",
                            )
                            subject_input = tc2.text_input(
                                "Subject You Teach (if requesting class)",
                                placeholder="e.g. Mathematics",
                            )
                        else:
                            class_input = st.selectbox(
                                "Request to Join Class (sent to Admin for approval)",
                                options=[""] + existing_classes,
                                format_func=lambda v: v if v else "— Join later on Dashboard —",
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
                        f"Create {role_choice.title()} Account & Open Dashboard",
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
                        subject_name=subject_input,
                    )
                    if err:
                        st.error(err, icon=":material/error:")
                    else:
                        auth.login_session(new_user, remember=remember_signup)
                        join_msg = (
                            f" Your join request for '{class_input}' has been sent to the Admin."
                            if class_input
                            else ""
                        )
                        st.session_state.setdefault("_flash", []).append((
                            f"Account created! Welcome to your {role_choice.title()} Dashboard, {new_user['full_name'].split()[0]}.{join_msg}",
                            ":material/check_circle:",
                        ))
                        st.rerun()

        # ==================================================================
        # SIGN IN — Existing Account (including the 1 School Admin Account)
        # ==================================================================
        else:
            with st.container(border=True):
                st.subheader("Sign In")
                with st.form("login_form"):
                    username = st.text_input("Username", placeholder="Enter your username (or 'admin')")
                    password = st.text_input("Password", type="password")
                    remember_signin = st.checkbox(
                        "Remember me (stay signed in automatically)",
                        value=True,
                        help="Keep your account signed in on this browser/device so you don't have to log in every time.",
                    )
                    submitted = st.form_submit_button("Sign In & Open Dashboard", type="primary", width="stretch", icon=":material/login:")
                if submitted:
                    user, error = auth.authenticate(username, password)
                    if error:
                        st.error(error, icon=":material/error:")
                    else:
                        auth.login_session(user, remember=remember_signin)
                        st.session_state.setdefault("_flash", []).append(
                            (f"Welcome back, {user['full_name'].split()[0]}.", ":material/check_circle:"))
                        st.rerun()

            with st.container(border=True):
                st.markdown("**School Admin Account (Manages All Classes & Join Requests)**")
                st.caption("Username: `admin` · Password: `Admin@123`")
                if st.button(
                    "Quick Sign In as School Admin",
                    icon=":material/admin_panel_settings:",
                    type="secondary",
                    width="stretch",
                    key="quick_admin_login_btn",
                ):
                    admin_user, error = auth.authenticate("admin", "Admin@123")
                    if error:
                        st.error(error, icon=":material/error:")
                    else:
                        auth.login_session(admin_user, remember=True)
                        st.session_state.setdefault("_flash", []).append(
                            ("Signed in as School Admin.", ":material/check_circle:")
                        )
                        st.rerun()
