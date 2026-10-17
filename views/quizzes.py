"""Quizzes - build multiple-choice quizzes, auto-grade them and review results."""

import streamlit as st

from classpilot import auth, coursework, school, storage, ui, utils


def _quiz_label(quiz_id):
    quiz = storage.get("quizzes", quiz_id)
    state = "Published" if quiz.get("published") else "Draft"
    return f"{quiz['title']} · {school.subject_label(quiz['subject_id'])} ({state})"


# ==========================================================================
# Teacher
# ==========================================================================
def _new_quiz(user, subjects):
    """Create quiz settings; the deadline is checked live for conflicts."""
    default_day, default_time = ui.default_due(7)
    st.session_state.setdefault("nq_date", default_day)
    st.session_state.setdefault("nq_time", default_time)
    left, right = st.columns([3, 2])
    with left:
        subject_id = ui.subject_select(subjects, "nq_subject")
        title = st.text_input("Quiz title", key="nq_title", max_chars=120)
        description = st.text_area("Instructions for students", key="nq_description", height=90)
        col1, col2, col3 = st.columns(3)
        due_day = col1.date_input("Closes on", key="nq_date", format="DD/MM/YYYY")
        due_time = col2.time_input("Closing time", key="nq_time", step=900)
        attempts = col3.number_input("Attempts allowed", 1, 10, 1, key="nq_attempts")
        show_answers = st.checkbox("Show correct answers to students after they submit", True, key="nq_show")
    with right:
        st.markdown("**🗓️ Deadline Conflict Detector**")
        subject = school.get_subject(subject_id)
        ui.deadline_check_panel(subject["class_id"], utils.combine(due_day, due_time), "nq_date", "nq_time")
    if st.button("Create quiz & add questions", type="primary", icon="❓"):
        quiz, error = coursework.save_quiz(user, subject_id, title, description, utils.combine(due_day, due_time),
                                           attempts, show_answers)
        if error:
            st.error(error, icon="⚠️")
        else:
            for key in ("nq_title", "nq_description", "nq_date", "nq_time", "nq_attempts"):
                st.session_state.pop(key, None)
            st.session_state["builder_pick"] = quiz["id"]
            ui.done("Quiz created as a draft. Add questions in the 'Build & edit' tab, then publish.", "❓")


def _question_builder(user, quiz):
    locked = bool(coursework.attempts_for(quiz["id"]))
    st.markdown(f"**Questions** · {len(quiz['questions'])} question(s), {coursework.quiz_max_score(quiz)} point(s)")
    if locked:
        st.info("Students have already taken this quiz, so questions are locked to keep grading fair.", icon="🔒")
    for number, question in enumerate(quiz["questions"], start=1):
        with st.container(border=True):
            col1, col2 = st.columns([6, 1])
            col1.markdown(f"**Q{number}. {question['text']}**  ·  :gray[{question['points']} pt]")
            for index, option in enumerate(question["options"]):
                mark = "✅" if index == question["answer"] else "▫️"
                col1.markdown(f"{mark} {option}")
            if not locked and col2.button("Delete", key=f"delq_{question['id']}", icon="🗑️"):
                ui.report(coursework.delete_question(user, quiz["id"], question["id"]), "Question deleted.", "🗑️")

    if locked:
        return
    with st.form(f"add_question_{quiz['id']}", clear_on_submit=True):
        st.markdown("**➕ Add a multiple-choice question**")
        text = st.text_area("Question", height=70)
        option_cols = st.columns(2)
        options = [option_cols[i % 2].text_input(f"Option {chr(65 + i)}", key=f"opt_{quiz['id']}_{i}")
                   for i in range(4)]
        col1, col2 = st.columns(2)
        correct = col1.radio("Correct answer", [0, 1, 2, 3], format_func=lambda i: f"Option {chr(65 + i)}",
                             horizontal=True)
        points = col2.number_input("Points", 1, 100, 1)
        st.caption("Leave options C and D empty for a true/false or two-option question.")
        added = st.form_submit_button("Add question", type="primary", icon="➕")
    if added:
        ui.report(coursework.add_question(user, quiz["id"], text, options, correct, points), "Question added.", "➕")


def _quiz_settings(user, subjects, quiz):
    subject_ids = [s["id"] for s in subjects]
    due = utils.parse_dt(quiz["due"])
    with st.form(f"quiz_settings_{quiz['id']}"):
        col1, col2 = st.columns(2)
        subject_id = col1.selectbox("Subject", subject_ids, index=subject_ids.index(quiz["subject_id"]),
                                    format_func=school.subject_label)
        title = col2.text_input("Title", quiz["title"])
        description = st.text_area("Instructions", quiz.get("description", ""), height=70)
        col1, col2, col3 = st.columns(3)
        due_day = col1.date_input("Closes on", due.date(), format="DD/MM/YYYY")
        due_time = col2.time_input("Closing time", due.time(), step=900)
        attempts = col3.number_input("Attempts allowed", 1, 10, int(quiz.get("attempts_allowed", 1)))
        show_answers = st.checkbox("Show correct answers after submitting", quiz.get("show_answers", True))
        saved = st.form_submit_button("Save settings")
    if saved:
        _, error = coursework.save_quiz(user, subject_id, title, description, utils.combine(due_day, due_time),
                                        attempts, show_answers, quiz_id=quiz["id"])
        ui.report(error, "Quiz settings saved.")


def _quiz_results(quiz):
    subject = school.get_subject(quiz["subject_id"])
    students = school.class_students(subject["class_id"])
    rows, percents = [], []
    for student in students:
        attempts = coursework.attempts_for(quiz["id"], student["id"])
        best = max(attempts, key=lambda a: a["score"]) if attempts else None
        if best:
            percents.append(best["percent"])
        rows.append({"Student": student["full_name"], "Status": coursework.quiz_status(quiz, student["id"]),
                     "Attempts": len(attempts),
                     "Best score": f"{best['score']}/{best['max_score']}" if best else "—",
                     "Percent": best["percent"] if best else None,
                     "Submitted": utils.fmt_dt(best["submitted_at"]) if best else "—"})
    ui.metrics([("Completed", f"{len(percents)}/{len(students)}"),
                ("Class average", utils.fmt_pct(utils.mean(percents))),
                ("Highest", utils.fmt_pct(max(percents)) if percents else "—"),
                ("Lowest", utils.fmt_pct(min(percents)) if percents else "—")])
    ui.table(rows, {"Percent": ui.pct_column("Percent")})

    analysis = coursework.quiz_item_analysis(quiz)
    if percents and analysis:
        st.markdown("**🔬 Question analysis** — questions most students got wrong may need re-teaching.")
        ui.bar_chart([{"Question": f"Q{r['number']}", "% correct": r["percent_correct"] or 0} for r in analysis],
                     x="Question", y="% correct", height=240)
        ui.table([{"#": r["number"], "Question": r["question"], "Correct answer": r["correct_answer"],
                   "% correct": r["percent_correct"], "Most common wrong answer": r["common_wrong"]}
                  for r in analysis], {"% correct": ui.pct_column("% correct")})


def teacher_quizzes_page():
    user = auth.require_role("teacher")
    ui.page_header("Quiz Builder", "Multiple-choice quizzes that grade themselves.", "❓")
    subjects = school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("You are not assigned to any subjects yet.")
        return
    subject_ids = [s["id"] for s in subjects]
    quizzes = coursework.quizzes_for_subjects(subject_ids)

    tab_list, tab_build, tab_results, tab_new = st.tabs(["📋 My quizzes", "🛠️ Build & edit", "📈 Results", "➕ New quiz"])
    with tab_new:
        _new_quiz(user, subjects)

    with tab_list:
        rows = []
        for q in quizzes:
            class_size = len(school.class_students(school.get_subject(q["subject_id"])["class_id"]))
            takers = {a["student_id"] for a in coursework.attempts_for(q["id"])}
            rows.append({"Quiz": q["title"], "Subject": school.subject_label(q["subject_id"]),
                         "Status": "Published" if q.get("published") else "Draft",
                         "Questions": len(q["questions"]), "Closes": utils.fmt_dt(q["due"]),
                         "Completed": utils.percent(len(takers), class_size) or 0})
        ui.table(rows, {"Completed": ui.pct_column("Completed")})

    if not quizzes:
        with tab_build:
            ui.empty_state("Create a quiz in the 'New quiz' tab first.")
        with tab_results:
            ui.empty_state("No quizzes yet.")
        return

    quiz_ids = [q["id"] for q in quizzes]
    if st.session_state.get("builder_pick") not in quiz_ids:
        st.session_state["builder_pick"] = quiz_ids[0]

    with tab_build:
        quiz_id = st.selectbox("Quiz", quiz_ids, format_func=_quiz_label, key="builder_pick")
        quiz = storage.get("quizzes", quiz_id)
        col1, col2, col3 = st.columns([2, 1, 1])
        col1.markdown(f"{ui.badge('Published' if quiz.get('published') else 'Draft')} · closes "
                      f"{utils.fmt_dt(quiz['due'])} ({utils.relative_due(quiz['due'])})")
        if quiz.get("published"):
            if col2.button("Unpublish", icon="🙈", width="stretch"):
                ui.report(coursework.set_published(user, quiz_id, False), "Quiz hidden from students.", "🙈")
        elif col2.button("Publish", type="primary", icon="🚀", width="stretch"):
            ui.report(coursework.set_published(user, quiz_id, True), "Quiz published to students!", "🚀")
        with col3:
            if ui.confirm_button("Delete quiz", f"del_quiz_{quiz_id}", "Delete this quiz and all student attempts?"):
                ui.report(coursework.delete_quiz(user, quiz_id), "Quiz deleted.", "🗑️")
        with st.expander("⚙️ Quiz settings"):
            _quiz_settings(user, subjects, quiz)
        _question_builder(user, quiz)

    with tab_results:
        published = [q["id"] for q in quizzes if q.get("published")]
        if not published:
            ui.empty_state("Publish a quiz to start collecting results.")
        else:
            result_id = st.selectbox("Quiz", published, format_func=_quiz_label, key="results_pick")
            _quiz_results(storage.get("quizzes", result_id))


# ==========================================================================
# Student
# ==========================================================================
def _show_attempt_review(quiz, attempt):
    """Score summary and (if allowed) the correct answers."""
    st.success(f"You scored **{attempt['score']}/{attempt['max_score']}** ({utils.fmt_pct(attempt['percent'])}).",
               icon="🎯")
    if not quiz.get("show_answers", True):
        st.caption("Your teacher has chosen not to show the correct answers for this quiz.")
        return
    for number, question in enumerate(quiz["questions"], start=1):
        chosen = attempt["answers"].get(question["id"])
        correct = chosen == question["answer"]
        icon = "✅" if correct else "❌"
        st.markdown(f"{icon} **Q{number}. {question['text']}**")
        if chosen is not None and chosen < len(question["options"]):
            st.caption(f"Your answer: {question['options'][chosen]}"
                       + ("" if correct else f" · Correct answer: {question['options'][question['answer']]}"))


def _take_quiz(user, quiz):
    with st.form(f"take_{quiz['id']}"):
        answers = {}
        for number, question in enumerate(quiz["questions"], start=1):
            choice = st.radio(f"**Q{number}. {question['text']}** ({question['points']} pt)",
                              list(range(len(question["options"]))), index=None,
                              format_func=lambda i, q=question: q["options"][i], key=f"ans_{quiz['id']}_{question['id']}")
            answers[question["id"]] = choice
        sent = st.form_submit_button("Submit quiz", type="primary", icon="📤")
    if sent:
        attempt, error = coursework.submit_quiz(user, quiz["id"], answers)
        if error:
            st.error(error, icon="⚠️")
        else:
            st.session_state["last_attempt"] = attempt["id"]
            ui.done(f"Quiz submitted! You scored {attempt['score']}/{attempt['max_score']}.", "🎯")


def student_quizzes_page():
    user = auth.require_role("student")
    ui.page_header("Quizzes", "Take quizzes and get your results instantly.", "❓")
    subjects = school.subjects_for_student(user["id"])
    if not subjects:
        ui.empty_state("You are not enrolled in a class yet.")
        return
    col1, col2 = st.columns(2)
    with col1:
        subject_filter = ui.subject_select(subjects, "s_quiz_subject", include_all=True)
    status_filter = col2.selectbox("Status", ["All", "Open", "Completed", "Missed"], key="s_quiz_status")
    quizzes = coursework.quizzes_for_subjects([s["id"] for s in subjects] if subject_filter == "all" else [subject_filter],
                                              published_only=True)
    quizzes = [q for q in quizzes if status_filter == "All" or coursework.quiz_status(q, user["id"]) == status_filter]
    quizzes.sort(key=lambda q: (coursework.quiz_status(q, user["id"]) != "Open", q["due"]))
    if not quizzes:
        ui.empty_state("No quizzes match your filters.")
        return
    for quiz in quizzes:
        status = coursework.quiz_status(quiz, user["id"])
        attempts = coursework.attempts_for(quiz["id"], user["id"])
        remaining = quiz.get("attempts_allowed", 1) - len(attempts)
        best = coursework.best_attempt(quiz["id"], user["id"])
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            col1.markdown(f"**{quiz['title']}** {ui.badge(status)}  \n:gray[{school.subject_label(quiz['subject_id'])} · "
                          f"{len(quiz['questions'])} questions · closes {utils.fmt_dt(quiz['due'])} "
                          f"({utils.relative_due(quiz['due'])}) · attempts used {len(attempts)}/{quiz.get('attempts_allowed', 1)}]")
            if best:
                col2.metric("Best", utils.fmt_pct(best["percent"]))
            can_take = remaining > 0 and not utils.is_past(quiz["due"])
            expanded = st.session_state.get("last_attempt") in [a["id"] for a in attempts]
            with st.expander("Start quiz" if can_take and not attempts else "Open", expanded=expanded):
                if quiz.get("description"):
                    st.caption(quiz["description"])
                if best:
                    _show_attempt_review(quiz, attempts[-1])
                if can_take:
                    if attempts:
                        st.markdown(f"**Try again** — {remaining} attempt(s) left. Your best score counts.")
                    _take_quiz(user, quiz)
                elif not attempts:
                    st.error("This quiz has closed.", icon="🔒")
