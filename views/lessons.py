"""Lesson Hub - notes, files and links organised by subject and topic.

Students also rate their confidence for each lesson here (ClassPulse).
"""

import streamlit as st

from classpilot import auth, coursework, school, tracking, ui, utils


def _lesson_filters(subjects, key):
    """Subject, topic and keyword filters. Returns the filtered lesson list."""
    col1, col2, col3 = st.columns([1.4, 1, 1.4])
    with col1:
        subject_id = ui.subject_select(subjects, f"{key}_subject", include_all=True)
    subject_ids = [s["id"] for s in subjects] if subject_id == "all" else [subject_id]
    lessons = coursework.lessons_for_subjects(subject_ids)
    topics = sorted({l["topic"] for l in lessons})
    topic = col2.selectbox("Topic", ["All topics"] + topics, key=f"{key}_topic")
    query = col3.text_input("Search lessons & resources", key=f"{key}_query", placeholder="Keyword")
    if topic != "All topics":
        lessons = [l for l in lessons if l["topic"] == topic]
    if query:
        lessons = [l for l in lessons if utils.matches(query, l["title"], l["topic"], l["content"],
                                                        *[r["label"] for r in l.get("resources", [])],
                                                        *[f["name"] for f in l.get("files", [])])]
    return lessons


def _show_lesson_body(lesson, key_prefix):
    """The lesson notes, links and downloadable files."""
    if lesson.get("content"):
        st.markdown(lesson["content"])
    if lesson.get("resources"):
        st.markdown("**🔗 Resources**")
        for res in lesson["resources"]:
            st.markdown(f"- [{res['label']}]({res['url']})")
    if lesson.get("files"):
        st.markdown("**📎 Files**")
        for index, item in enumerate(lesson["files"]):
            ui.file_download(item, key=f"{key_prefix}_{lesson['id']}_{index}")


def _group_by_topic(lessons):
    groups = {}
    for lesson in lessons:
        key = (school.subject_label(lesson["subject_id"]), lesson["topic"])
        groups.setdefault(key, []).append(lesson)
    return groups


# ==========================================================================
# Teacher
# ==========================================================================
def _lesson_form(user, subjects, lesson=None):
    """Create a new lesson or edit an existing one."""
    key = lesson["id"] if lesson else "new"
    subject_ids = [s["id"] for s in subjects]
    with st.form(f"lesson_form_{key}", clear_on_submit=lesson is None):
        col1, col2 = st.columns(2)
        subject_id = col1.selectbox("Subject", subject_ids, format_func=school.subject_label,
                                    index=subject_ids.index(lesson["subject_id"]) if lesson else 0)
        existing_topics = sorted({l["topic"] for l in coursework.lessons_for_subjects(subject_ids)})
        topic = col2.text_input("Topic", lesson["topic"] if lesson else "",
                                help="Existing topics: " + (", ".join(existing_topics) or "none yet"))
        title = st.text_input("Lesson title", lesson["title"] if lesson else "")
        content = st.text_area("Notes (Markdown supported: **bold**, - lists, ## headings)",
                               lesson["content"] if lesson else "", height=200)
        resources = st.text_area("Links - one per line as `Label | https://...`",
                                 coursework.resources_to_text(lesson["resources"]) if lesson else "", height=90)
        files = st.file_uploader("Attach files (PDF, Word, PowerPoint, images, ... max 10 MB each)",
                                 accept_multiple_files=True, key=f"lesson_files_{key}")
        submitted = st.form_submit_button("Save lesson" if lesson else "Publish lesson", type="primary", icon="💾")
    if submitted:
        _, error = coursework.save_lesson(user, subject_id, topic, title, content, resources, files,
                                          lesson_id=lesson["id"] if lesson else None)
        ui.report(error, "Lesson saved." if lesson else "Lesson published.", "📖")


def teacher_lessons_page():
    user = auth.require_role("teacher")
    ui.page_header("Lesson Hub", "Organise notes, materials and resources by subject and topic.", "📖")
    subjects = school.subjects_for_teacher(user["id"])
    if not subjects:
        ui.empty_state("You are not assigned to any subjects yet. Ask the school admin to add you.")
        return

    tab_browse, tab_new = st.tabs(["📚 My lessons", "➕ New lesson"])
    with tab_new:
        _lesson_form(user, subjects)

    with tab_browse:
        lessons = _lesson_filters(subjects, "t_lessons")
        st.caption(f"{len(lessons)} lesson(s)")
        if not lessons:
            ui.empty_state("No lessons match. Use the 'New lesson' tab to add one.")
        pulse_by_lesson = {}
        for subject in subjects:
            for row in tracking.pulse_summary(subject["id"]):
                pulse_by_lesson[row["lesson_id"]] = row
        for (subject_label, topic), group in _group_by_topic(lessons).items():
            st.markdown(f"#### {topic}  \n:gray[{subject_label}]")
            for lesson in group:
                pulse = pulse_by_lesson.get(lesson["id"], {})
                avg = pulse.get("average")
                pulse_text = f" · 💓 {avg:.1f}/5 ({pulse['responses']} votes)" if avg else " · 💓 no ratings yet"
                with st.expander(f"{lesson['title']}{pulse_text}"):
                    view_tab, edit_tab = st.tabs(["View", "Edit"])
                    with view_tab:
                        st.caption(f"Updated {utils.fmt_dt(lesson.get('updated_at'))}")
                        _show_lesson_body(lesson, "t")
                    with edit_tab:
                        _lesson_form(user, subjects, lesson)
                        for item in lesson.get("files", []):
                            if st.button(f"Remove {item['name']}", key=f"rm_{lesson['id']}_{item['path']}", icon="✖️"):
                                ui.report(coursework.remove_lesson_file(user, lesson["id"], item["path"]), "File removed.")
                        if ui.confirm_button("Delete lesson", f"del_lesson_{lesson['id']}",
                                             "Delete this lesson, its files and its ClassPulse ratings?"):
                            ui.report(coursework.delete_lesson(user, lesson["id"]), "Lesson deleted.", "🗑️")


# ==========================================================================
# Student
# ==========================================================================
def _pulse_widget(user, lesson):
    """Private confidence rating for one lesson."""
    current = tracking.my_pulse(user["id"], lesson["id"])
    st.markdown("**💓 ClassPulse — how confident do you feel about this lesson?**")
    st.caption("🔒 Private: your teacher only sees class totals, never your name.")
    with st.form(f"pulse_{lesson['id']}"):
        rating = st.select_slider("Confidence", options=list(tracking.CONFIDENCE_LABELS),
                                  value=current["rating"] if current else 3,
                                  format_func=lambda v: tracking.CONFIDENCE_LABELS[v], label_visibility="collapsed")
        note = st.text_input("What's confusing? (optional, anonymous)", current.get("note", "") if current else "",
                             max_chars=300)
        saved = st.form_submit_button("Update my rating" if current else "Save my rating", icon="💓")
    if saved:
        ui.report(tracking.set_pulse(user, lesson["id"], rating, note), "Thanks! Your rating was saved privately.", "💓")


def student_lessons_page():
    user = auth.require_role("student")
    ui.page_header("Lessons", "Notes and resources from your teachers. Rate your confidence to help them help you.", "📖")
    subjects = school.subjects_for_student(user["id"])
    if not subjects:
        ui.empty_state("You are not enrolled in a class yet.")
        return
    lessons = _lesson_filters(subjects, "s_lessons")
    unrated = [l for l in lessons if not tracking.my_pulse(user["id"], l["id"])]
    st.caption(f"{len(lessons)} lesson(s) · {len(unrated)} not yet rated in ClassPulse")
    if not lessons:
        ui.empty_state("No lessons match your filters.")
    for (subject_label, topic), group in _group_by_topic(lessons).items():
        st.markdown(f"#### {topic}  \n:gray[{subject_label}]")
        for lesson in group:
            mine = tracking.my_pulse(user["id"], lesson["id"])
            marker = f"💓 you rated {mine['rating']}/5" if mine else "⭐ not rated yet"
            with st.expander(f"{lesson['title']}  ·  {marker}"):
                _show_lesson_body(lesson, "s")
                st.divider()
                _pulse_widget(user, lesson)
