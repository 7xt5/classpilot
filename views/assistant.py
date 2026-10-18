"""
assistant.py - NovaAI Cognitive Workbench for Teachers/Admins and Students.

Features:
  * Live Chain-of-Thought Reasoning Trace + Token Streaming (st.write_stream)
  * Selectable Cognitive Personas / Tutor Modes
  * Pure-Python Symbolic Algebra, Calculus & Statistical Problem Solver
  * AI Submission Evaluator & Rubric Grader (saves directly to Gradebook)
  * 1-Click Lesson, Assignment/Rubric & Auto-Graded Quiz Generators
  * Interactive Study Flashcards & Personalized Study Roadmap
"""

import streamlit as st

from classpilot import ai_assistant, auth, coursework, insights, school, storage, tracking, ui, utils


def _render_chat(user, ask_fn, quick_prompts, placeholder, modes):
    """Shared persistent chat UI with Live LLM Model selector, Cognitive Persona, Chain-of-Thought trace, and streaming."""
    history = ai_assistant.get_chat_history(user["id"])

    # Top control bar: Reasoning Mode + Live LLM Model + Clear Chat
    ctrl_left, ctrl_mid, ctrl_right = st.columns([2.2, 2.0, 0.9])
    with ctrl_left:
        selected_mode = st.selectbox(
            "Cognitive Reasoning Mode",
            options=modes,
            key=f"ai_mode_{user['id']}",
        )
    with ctrl_mid:
        model_keys = list(ai_assistant.LLM_MODELS.keys())
        chosen_model = st.selectbox(
            "Live AI Model",
            options=model_keys,
            format_func=lambda k: ai_assistant.LLM_MODELS.get(k, k),
            key=f"ai_model_sel_{user['id']}",
        )
        st.session_state["novarix_ai_model"] = chosen_model
    with ctrl_right:
        st.write("")
        if history and st.button("Clear Chat", key=f"clear_ai_{user['id']}", icon=":material/delete:", width="stretch"):
            ai_assistant.clear_chat_history(user["id"])
            st.rerun()

    with st.expander("Optional: Custom API Key (OpenAI / Groq / OpenRouter)", expanded=False):
        st.caption("NovaAI works out-of-the-box with its built-in Cloud LLM (no key needed). You can optionally connect your own API key below.")
        k1, k2, k3 = st.columns([2, 2, 1.2])
        st.session_state["novarix_custom_api_key"] = k1.text_input(
            "API Key (optional)",
            value=st.session_state.get("novarix_custom_api_key", ""),
            type="password",
            placeholder="sk-...",
            key=f"cust_key_{user['id']}",
        )
        st.session_state["novarix_custom_base_url"] = k2.text_input(
            "Endpoint URL",
            value=st.session_state.get("novarix_custom_base_url", "https://api.openai.com/v1/chat/completions"),
            key=f"cust_url_{user['id']}",
        )
        st.session_state["novarix_custom_model"] = k3.text_input(
            "Model Name",
            value=st.session_state.get("novarix_custom_model", "gpt-4o-mini"),
            key=f"cust_mod_{user['id']}",
        )

    # Quick-prompt buttons in a spacious 2-column grid
    triggered_prompt = None
    for row_idx in range(0, len(quick_prompts), 2):
        chunk = quick_prompts[row_idx:row_idx + 2]
        cols = st.columns(len(chunk))
        for col, (label, prompt_text) in zip(cols, chunk):
            if col.button(label, key=f"qp_{user['id']}_{label}", width="stretch"):
                triggered_prompt = prompt_text

    typed_prompt = st.chat_input(placeholder, key=f"chat_in_{user['id']}")
    active_prompt = triggered_prompt or typed_prompt

    with st.container(border=True):
        if not history and not active_prompt:
            st.markdown(ask_fn(user, "summary", mode=selected_mode))

        for msg in history:
            with st.chat_message(msg["role"]):
                if msg.get("trace"):
                    with st.expander("Chain-of-Thought & RAG Reasoning Trace", expanded=False):
                        for step in msg["trace"]:
                            st.code(step, language="text")
                st.markdown(msg["content"])

        if active_prompt:
            with st.chat_message("user"):
                st.markdown(active_prompt)

            with st.chat_message("assistant"):
                with st.spinner("NovaAI is thinking..."):
                    reply = ask_fn(user, active_prompt, mode=selected_mode)
                trace = ai_assistant.get_latest_trace(user["id"])
                if trace:
                    with st.status("NovaAI Live LLM & RAG Reasoning Trace", expanded=False):
                        for step in trace:
                            st.code(step, language="text")
                if st.session_state.get("_fast_test_mode"):
                    st.markdown(reply)
                else:
                    st.write_stream(ai_assistant.stream_markdown(reply, delay=0.004))

            ai_assistant.append_chat_message(user["id"], "user", active_prompt)
            ai_assistant.append_chat_message(user["id"], "assistant", reply, trace=trace)


def _render_symbolic_solver_panel(key_prefix):
    """Interactive Live AI + Symbolic Algebra, Calculus, Science & Statistics Solver panel."""
    with st.container(border=True):
        st.subheader("AI Math, Science, Calculus & Problem Solver")
        st.caption("Enter any math equation, word problem, physics/chemistry problem, calculus derivative/integral, or dataset for step-by-step AI + symbolic solving.")

        presets = [
            ("Quadratic: 2x^2 + 5x - 3 = 0", "Solve 2x^2 + 5x - 3 = 0"),
            ("Physics: Projectile launched at 25 m/s at 30°", "A projectile is launched at 25 m/s at 30 degrees above horizontal. Find max height and range."),
            ("Calculus: d/dx (3x^3 - 6x^2 + 4x - 9)", "Derivative of 3x^3 - 6x^2 + 4x - 9"),
            ("Statistics: 74, 82, 88, 91, 95, 68", "Mean, median, std of 74, 82, 88, 91, 95, 68"),
        ]
        chosen_preset = None
        for row_idx in range(0, len(presets), 2):
            chunk = presets[row_idx:row_idx + 2]
            p_cols = st.columns(len(chunk))
            for col, (lbl, val) in zip(p_cols, chunk):
                if col.button(lbl, key=f"{key_prefix}_pre_{lbl}", width="stretch"):
                    chosen_preset = val

        default_val = chosen_preset or st.session_state.get(f"{key_prefix}_math_in", "2x^2 + 5x - 3 = 0")
        if chosen_preset:
            st.session_state[f"{key_prefix}_math_in"] = chosen_preset

        expr_in = st.text_input(
            "Problem, Equation, Word Problem, Derivative, or Dataset",
            value=default_val,
            key=f"{key_prefix}_math_input_box",
        )
        if st.button("Solve Problem Step-by-Step", type="primary", icon=":material/calculate:", key=f"{key_prefix}_run_math") or chosen_preset:
            with st.spinner("Solving step-by-step with NovaAI Live LLM + Symbolic Engine..."):
                sol, note = ai_assistant.solve_any_problem_with_ai(expr_in)
            if sol:
                st.markdown(f"**Solver Engine:** `{note}`")
                st.markdown(sol)
            else:
                st.warning("Please enter a problem or question to solve.")


# ==========================================================================
# Teacher & Admin AI Copilot Workbench
# ==========================================================================
def teacher_assistant_page():
    user = auth.require_role("teacher", "admin")
    ui.page_header(
        "NovaAI — Cognitive Teaching Copilot",
        "Multi-engine AI with Chain-of-Thought reasoning, symbolic math solving, AI submission grading, and 1-click LMS generators.",
    )
    subjects = (school.all_subjects() if user["role"] == "admin"
                else school.subjects_for_teacher(user["id"]))

    tab_chat, tab_grader, tab_studio, tab_quiz, tab_solver = st.tabs([
        "Copilot Chat",
        "AI Submission Grader",
        "Lesson & Rubric Studio",
        "AI Quiz Generator",
        "Symbolic Math & Stats Lab",
    ])

    with tab_chat:
        teacher_modes = [
            "Analytical & Data-Driven",
            "Lesson & Curriculum Architect",
            "Strict Rubric & Assessment Evaluator",
            "Empathetic Mentor & Parent Outreach",
        ]
        quick = [
            ("Who needs support?", "Who is falling behind and needs support in my classes?"),
            ("Grading & Check Queue", "What assignments and submissions are waiting for me to check?"),
            ("Solve 2x^2 + 5x - 3 = 0", "Solve 2x^2 + 5x - 3 = 0"),
            ("Photosynthesis vs Respiration", "Explain photosynthesis vs cellular respiration with a comparison table"),
        ]
        _render_chat(
            user,
            ai_assistant.ask_teacher_ai,
            quick,
            "Ask about your classes, solve an equation, explain a concept, or draft a lesson...",
            teacher_modes,
        )

    with tab_grader:
        with st.container(border=True):
            st.subheader("AI Submission Evaluator & Feedback Copilot")
            st.caption("Evaluate a real student submission from your grading queue or paste any written work/code to generate a criterion score breakdown and feedback.")

            subject_ids = [s["id"] for s in subjects]
            queue, _ = coursework.grading_queue(subject_ids) if subject_ids else ([], [])

            eval_mode = st.radio(
                "Evaluation Source",
                options=["Paste or Test Any Student Response", "Select from LMS Grading Queue"],
                horizontal=True,
                key="ai_eval_src_mode",
            )

            selected_sub = None
            selected_asg = None
            if eval_mode == "Select from LMS Grading Queue":
                if not queue:
                    st.info("Your LMS grading queue is currently empty. Switch to 'Paste or Test Any Student Response' to test the AI Evaluator on any text.")
                else:
                    sub_id = st.selectbox(
                        "Select Ungraded Submission",
                        options=[s["id"] for s in queue],
                        format_func=lambda sid: (
                            f"{school.user_name(storage.get('submissions', sid)['student_id'])} — "
                            f"{storage.get('assignments', storage.get('submissions', sid)['assignment_id'])['title']}"
                        ),
                    )
                    selected_sub = storage.get("submissions", sub_id)
                    selected_asg = storage.get("assignments", selected_sub["assignment_id"]) if selected_sub else None

            c1, c2 = st.columns([2, 1])
            asg_title_in = c1.text_input(
                "Assignment Title",
                value=selected_asg["title"] if selected_asg else "Analytical Response & Problem Set",
                key="ai_ev_title",
            )
            max_pts_in = c2.number_input(
                "Max Points",
                min_value=5,
                max_value=200,
                value=int(selected_asg["max_points"]) if selected_asg else 30,
                step=5,
                key="ai_ev_max",
            )
            rubric_focus_in = st.text_input(
                "Key Vocabulary / Rubric Concepts to Check For (optional)",
                placeholder="e.g. quadratic, discriminant, formula, verification",
                key="ai_ev_focus",
            )
            sample_stu_text = (
                selected_sub.get("text", "") if selected_sub else
                "1. To solve 2x^2 + 5x - 3 = 0, we identify a = 2, b = 5, and c = -3.\n"
                "2. Therefore, the discriminant is Δ = 5^2 - 4(2)(-3) = 25 + 24 = 49.\n"
                "3. Using the quadratic formula, x = (-5 ± 7) / 4, which gives x = 0.5 or x = -3."
            )
            stu_text_in = st.text_area(
                "Student Submission Text / Code",
                value=sample_stu_text,
                height=140,
                key="ai_ev_text",
            )

            if st.button("Run AI Rubric Evaluation", type="primary", icon=":material/fact_check:", key="btn_run_ai_eval"):
                with st.spinner("Evaluating submission with NovaAI Live LLM..."):
                    st.session_state["ai_eval_result"] = ai_assistant.evaluate_submission_with_ai(
                        asg_title_in, max_pts_in, stu_text_in, rubric_focus_in
                    )

            eval_res = st.session_state.get("ai_eval_result")
            if eval_res:
                st.divider()
                st.markdown(eval_res["summary"])
                if selected_sub and selected_asg:
                    g1, g2 = st.columns([1, 3])
                    final_score = g1.number_input(
                        "Final Score to Record",
                        min_value=0.0,
                        max_value=float(selected_asg["max_points"]),
                        value=float(eval_res["suggested_score"]),
                        step=0.5,
                        key="ai_ev_final_score",
                    )
                    final_fb = g2.text_input("Feedback to Save", value=eval_res["feedback"], key="ai_ev_final_fb")
                    if st.button("Save Score & Feedback to Gradebook", type="primary", icon=":material/check:", key="ai_ev_commit"):
                        err = coursework.grade_submission(user, selected_sub["id"], final_score, final_fb, apply_penalty=True)
                        ui.report(err, "Grade and AI feedback saved to Gradebook.")

    with tab_studio:
        if not subjects:
            ui.empty_state("Add a Class & Subject on your Dashboard first to publish lessons and assignments directly to your courses.")
        else:
            col_les, col_asg = st.columns(2)
            with col_les.container(border=True):
                st.subheader("AI Lesson Draft Generator")
                st.caption("Generates structured Markdown notes with formulas and worked examples, and publishes straight to the Lesson Hub.")
                subj_id = ui.subject_select(subjects, "ai_les_subj")
                subj_obj = school.get_subject(subj_id)
                topic = st.text_input("Topic / Unit", placeholder="e.g. Quadratic Equations or Photosynthesis", key="ai_les_topic")
                title = st.text_input("Lesson Title", placeholder="e.g. Mastering the Discriminant", key="ai_les_title")
                focus = st.text_input("Key focus (optional)", placeholder="e.g. Step-by-step sign rules", key="ai_les_focus")
                if st.button("Generate Lesson Draft", key="btn_gen_les", type="primary", icon=":material/auto_awesome:"):
                    with st.spinner("Generating custom lesson with NovaAI Live LLM..."):
                        st.session_state["ai_lesson_draft"] = ai_assistant.generate_lesson_draft(
                            subj_obj["name"], topic or "Core Unit", title or f"{topic or 'Core'} Essentials", focus
                        )
                        st.session_state["ai_lesson_subj"] = subj_id

                draft = st.session_state.get("ai_lesson_draft")
                if draft:
                    st.divider()
                    ed_topic = st.text_input("Topic", draft["topic"], key="ed_ai_les_topic")
                    ed_title = st.text_input("Title", draft["title"], key="ed_ai_les_title")
                    ed_content = st.text_area("Generated Markdown Notes (editable)", draft["content"], height=220, key="ed_ai_les_body")
                    ed_res = st.text_area("Resources (`Label | https://...`)", draft["resources"], height=70, key="ed_ai_les_res")
                    if st.button("Publish directly to Lesson Hub", key="pub_ai_les", type="primary", icon=":material/check:"):
                        _, err = coursework.save_lesson(user, subj_id, ed_topic, ed_title, ed_content, ed_res)
                        if not err:
                            st.session_state.pop("ai_lesson_draft", None)
                        ui.report(err, f"Lesson '{ed_title}' published to Lesson Hub.")

            with col_asg.container(border=True):
                st.subheader("AI Assignment & Rubric Builder")
                st.caption("Generates task instructions with a 3-tier Markdown grading rubric table.")
                asg_subj_id = ui.subject_select(subjects, "ai_asg_subj")
                asg_subj = school.get_subject(asg_subj_id)
                asg_topic = st.text_input("Assignment Topic", placeholder="e.g. Newton's Laws in Everyday Life", key="ai_asg_topic")
                asg_pts = st.number_input("Max Points", 10, 200, 30, step=5, key="ai_asg_pts")
                if st.button("Generate Assignment & Rubric", key="btn_gen_asg", type="primary", icon=":material/auto_awesome:"):
                    with st.spinner("Designing custom assignment & rubric with NovaAI Live LLM..."):
                        st.session_state["ai_asg_draft"] = ai_assistant.generate_assignment_and_rubric(
                            asg_subj["name"], asg_topic or asg_subj["name"], asg_pts
                        )

                asg_draft = st.session_state.get("ai_asg_draft")
                if asg_draft:
                    st.divider()
                    default_day, default_time = ui.default_due(7)
                    a_title = st.text_input("Assignment Title", asg_draft["title"], key="ed_ai_asg_title")
                    a_desc = st.text_area("Instructions & Rubric (editable)", asg_draft["description"], height=220, key="ed_ai_asg_desc")
                    c1, c2 = st.columns(2)
                    a_day = c1.date_input("Due Date", default_day, format="DD/MM/YYYY", key="ed_ai_asg_day")
                    a_time = c2.time_input("Due Time", default_time, step=900, key="ed_ai_asg_time")
                    if st.button("Create Assignment in Novarix", key="pub_ai_asg", type="primary", icon=":material/check:"):
                        _, err = coursework.save_assignment(
                            user, asg_subj_id, a_title, a_desc, utils.combine(a_day, a_time), asg_draft["max_points"]
                        )
                        if not err:
                            st.session_state.pop("ai_asg_draft", None)
                        ui.report(err, f"Assignment '{a_title}' created.")

    with tab_quiz:
        if not subjects:
            ui.empty_state("Add a Class & Subject on your Dashboard first to save quizzes.")
        else:
            with st.container(border=True):
                st.subheader("One-Click AI Quiz Generator")
                st.caption("Generates multiple-choice questions for any topic and saves them as a live quiz in Novarix.")
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    q_subj_id = ui.subject_select(subjects, "ai_q_subj")
                q_subj = school.get_subject(q_subj_id)
                q_topic = c2.text_input("Topic to Quiz", placeholder="e.g. Pythagoras' Theorem", key="ai_q_topic")
                q_count = c3.number_input("Questions", 2, 6, 4, key="ai_q_count")
                if st.button("Generate Quiz Questions", key="btn_gen_quiz", type="primary", icon=":material/auto_awesome:"):
                    topic_val = q_topic.strip() or q_subj["name"]
                    with st.spinner("Generating multiple-choice quiz with NovaAI Live LLM..."):
                        st.session_state["ai_quiz_questions"] = ai_assistant.generate_quiz_questions(
                            q_subj["name"], topic_val, q_count
                        )
                        st.session_state["ai_quiz_title"] = f"{topic_val} Quick Check"

                q_list = st.session_state.get("ai_quiz_questions")
                if q_list:
                    st.divider()
                    q_title = st.text_input("Quiz Title", st.session_state.get("ai_quiz_title", "Quick Check"), key="ai_q_title_in")
                    for idx, item in enumerate(q_list, start=1):
                        st.markdown(f"**Q{idx}. {item['text']}**")
                        for opt_i, opt in enumerate(item["options"]):
                            mark = "●" if opt_i == item["answer"] else "○"
                            st.caption(f"  {mark} {opt}")
                    default_day, default_time = ui.default_due(7)
                    d1, d2, d3 = st.columns(3)
                    q_day = d1.date_input("Closing Date", default_day, format="DD/MM/YYYY", key="ai_q_day")
                    q_time = d2.time_input("Closing Time", default_time, step=900, key="ai_q_time")
                    publish_now = d3.checkbox("Publish immediately", value=True, key="ai_q_pub_now")
                    if st.button("Save Quiz to Novarix", key="save_ai_quiz", type="primary", icon=":material/check:"):
                        quiz_rec, err = coursework.save_quiz(
                            user, q_subj_id, q_title,
                            f"Auto-graded check on {q_topic or q_subj['name']}.",
                            utils.combine(q_day, q_time), attempts_allowed=2, show_answers=True
                        )
                        if not err and quiz_rec:
                            for item in q_list:
                                coursework.add_question(user, quiz_rec["id"], item["text"], item["options"], item["answer"], item["points"])
                            if publish_now:
                                coursework.set_published(user, quiz_rec["id"], True)
                            st.session_state.pop("ai_quiz_questions", None)
                        ui.report(err, f"Quiz '{q_title}' saved with {len(q_list)} questions.")

    with tab_solver:
        _render_symbolic_solver_panel("teacher_solver")


# ==========================================================================
# Student AI Study Tutor Workbench
# ==========================================================================
def student_assistant_page():
    user = auth.require_role("student")
    ui.page_header(
        "NovaAI — Cognitive Study Tutor & Math Engine",
        "Ask questions with live Chain-of-Thought reasoning, solve algebra & calculus step-by-step, and practice with flashcards.",
    )
    subjects = school.subjects_for_student(user["id"])

    tab_tutor, tab_solver, tab_cards, tab_plan = st.tabs([
        "Study Tutor Chat",
        "Symbolic Math & Science Solver",
        "Interactive Flashcards",
        "Smart Study Roadmap",
    ])

    with tab_tutor:
        student_modes = [
            "Step-by-Step Deep Explainer",
            "Socratic Hint Coach (Guided Thinking)",
            "ELI5 / Intuition & Analogies",
            "Exam Cram & Practice Quizzer",
        ]
        quick = [
            ("Solve 2x^2 + 5x - 3 = 0", "Solve 2x^2 + 5x - 3 = 0"),
            ("Explain Photosynthesis", "Explain photosynthesis vs cellular respiration"),
            ("Python Binary Search", "Show me how binary search works in Python"),
            ("What's due soon?", "What assignments and quizzes do I have due soon?"),
        ]
        _render_chat(
            user,
            ai_assistant.ask_student_ai,
            quick,
            "Ask any question: solve an equation, explain a topic, write Python code, or check deadlines...",
            student_modes,
        )

    with tab_solver:
        _render_symbolic_solver_panel("student_solver")

    with tab_cards:
        subj_filter = ui.subject_select(subjects, "fc_subj", include_all=True) if subjects else None
        cards = ai_assistant.build_study_cards(user, subj_filter)
        if not cards:
            ui.empty_state("No flashcards found.")
        else:
            idx_key = "fc_index"
            idx = st.session_state.get(idx_key, 0) % len(cards)
            card = cards[idx]

            nav1, nav2, nav3 = st.columns([1, 2, 1])
            if nav1.button("← Previous Card", width="stretch", key="fc_prev"):
                st.session_state[idx_key] = (idx - 1) % len(cards)
                st.rerun()
            nav2.markdown(f"**Card {idx + 1} / {len(cards)}** — **{card['subject']}** · *{card['topic']}*")
            if nav3.button("Next Card →", width="stretch", key="fc_next"):
                st.session_state[idx_key] = (idx + 1) % len(cards)
                st.rerun()

            with st.container(border=True):
                conf_text = f"Your NovaPulse rating: {card['confidence']}/5" if card["confidence"] else "Built-in / Unrated Concept Card"
                st.markdown(f"### {card['front']}")
                st.caption(conf_text)
                st.markdown(f"**Active-Recall Prompt:** *{card['prompt']}*")
                with st.expander("Flip Card — Reveal Full Notes, Formulas & Worked Example", expanded=False):
                    st.markdown(card["back"])
                    for r in card["resources"]:
                        st.markdown(f"- [{r['label']}]({r['url']})")
                if card.get("lesson_id"):
                    st.divider()
                    st.caption("Update your NovaPulse confidence after reviewing this card:")
                    r_cols = st.columns(5)
                    for level in range(1, 6):
                        label = f"{level}★" + (" (current)" if card["confidence"] == level else "")
                        if r_cols[level - 1].button(label, key=f"fc_rate_{card['lesson_id']}_{level}", width="stretch"):
                            tracking.set_pulse(user, card["lesson_id"], level, "")
                            ui.done(f"Updated confidence to {level}/5 for '{card['front']}'.")

    with tab_plan:
        st.subheader("Personalized Study Roadmap")
        st.caption("Automatically prioritized from your upcoming deadlines, subject averages, and NovaPulse ratings.")
        steps = ai_assistant.generate_study_plan(user)
        for step in steps:
            with st.container(border=True):
                st.markdown(f"**[{step['priority']}]** {step['task']}")
                st.caption(f"Rationale: {step['why']}")
