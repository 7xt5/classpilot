"""Global search page - results are limited to what the user may see."""

import streamlit as st

from classpilot import auth, insights, ui


def search_page():
    user = auth.require_role("admin", "teacher", "student")
    hints = {
        "admin": "people, classes, subjects, assignments, quizzes and resources",
        "teacher": "your students, classes, assignments, quizzes, grades and resources",
        "student": "your subjects, assignments, quizzes, lessons, resources and grades",
    }
    ui.page_header("Search", f"Find {hints[user['role']]}.", "🔎")

    query = st.text_input("Search", placeholder="Type at least 2 characters, e.g. 'pythagoras' or 'Ali'",
                          key="search_query", label_visibility="collapsed")
    if len(query.strip()) < 2:
        ui.empty_state("Start typing to search across Novarix.", "🔎")
        return

    results = insights.search(user, query)
    if not results:
        st.warning(f"No results for “{query}”. Try a shorter or different word.", icon="🤷")
        return

    total = sum(len(rows) for rows in results.values())
    st.caption(f"{total} result(s) for “{query}”")
    categories = list(results.keys())
    choice = st.segmented_control("Filter", ["All"] + categories, default="All", key="search_filter")
    for category in categories:
        if choice in (None, "All") or choice == category:
            st.subheader(f"{category} ({len(results[category])})")
            ui.table(results[category])
