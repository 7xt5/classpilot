"""
ui.py - Reusable Streamlit building blocks with a Technical High-Contrast HUD
aesthetic, saturated telemetry accents, and pure-Python page transitions.

Only native Python & Streamlit components are used (no HTML/CSS/JS).
"""

import time as _time
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from classpilot import insights, storage, utils

# Geometric technical symbols for every status word shown in the app.
STATUS_SYMBOLS = {
    "Graded": "●", "Submitted": "◐", "Submitted late": "◑", "Missing": "▲",
    "Not submitted": "○", "Open": "◆", "Completed": "●", "Missed": "▲",
    "Present": "●", "Late": "◑", "Absent": "▲", "Excused": "○",
    "High": "▲", "Medium": "◆", "Low": "○", "Published": "●", "Draft": "○",
    "Normal": "○", "Important": "◆", "Urgent": "▲", "Pinned": "■", "New": "●",
    "Admin": "■", "Teacher": "◆", "Student": "●", "Active": "●", "Inactive": "○",
    "Assignment": "■", "Quiz": "◆", "Late work": "◑", "Closed": "○",
    "Checked": "●", "To Check": "○",
    "Assignment to Check": "■", "Class to Check": "◆", "Lesson Prep": "●",
    "Student Follow-up": "▲", "Note": "○",
}

STATUS_COLORS = {
    "Graded": "green", "Completed": "green", "Present": "green", "Published": "green",
    "Checked": "green", "Active": "green", "Low": "green",
    "Submitted": "blue", "Open": "blue", "New": "blue", "Pinned": "violet",
    "Teacher": "violet", "Student": "blue", "Admin": "orange",
    "Assignment": "blue", "Quiz": "violet",
    "Assignment to Check": "orange", "Class to Check": "violet",
    "Lesson Prep": "blue", "Student Follow-up": "red", "Note": "green",
    "Submitted late": "orange", "Late": "orange", "Medium": "orange",
    "Important": "orange", "Late work": "orange", "To Check": "orange", "High": "orange",
    "Missing": "red", "Missed": "red", "Absent": "red", "Urgent": "red",
}


def mono_icon(icon, default=":material/circle:"):
    """Ensure any icon passed to Streamlit is a clean Material icon."""
    if not icon:
        return None
    if isinstance(icon, str) and icon.startswith(":material/"):
        return icon
    return default


def logo_path():
    """Return the path to the custom Novarix emblem logo."""
    p = storage.PROJECT_DIR / "classpilot" / "logo.png"
    return str(p) if p.exists() else None


# --------------------------------------------------------------------------
# Pure-Python Page-Switch Transition & Clean Header
# --------------------------------------------------------------------------
def page_transition(title):
    """Track active route for smooth page transitions without interrupting chunk fetches."""
    st.session_state["_active_route"] = title


def badge(text):
    """Return markdown for a saturated high-contrast technical badge."""
    symbol = STATUS_SYMBOLS.get(text, "■")
    color = STATUS_COLORS.get(text, "blue")
    safe = str(text).replace("[", "(").replace("]", ")")
    return f":{color}-badge[{symbol} {safe}]"


def page_header(title, subtitle=None, icon=""):
    """Clean, modern header with subtle blue accent and divider."""
    clean_title = str(title).strip()
    page_transition(clean_title)
    st.title(f":blue[■] {clean_title}")
    if subtitle:
        st.caption(subtitle)
    st.divider()


def section(title, caption=None):
    clean = str(title).lstrip("■◆ ").strip()
    st.subheader(f":blue[◆] {clean}")
    if caption:
        st.caption(caption)


def empty_state(message, icon=None):
    with st.container(border=True):
        st.markdown(f":blue-badge[● STANDBY] &nbsp; {message}")


def page_link(path, label, icon=":material/arrow_forward:"):
    """Link to another page of the app (e.g. 'assignments')."""
    page = st.session_state.get("_pages", {}).get(path)
    if page is not None:
        st.page_link(page, label=label, icon=mono_icon(icon, ":material/arrow_forward:"))


# --------------------------------------------------------------------------
# Notifications that survive a rerun ("flash" messages)
# --------------------------------------------------------------------------
def flash(message, icon=":material/check_circle:"):
    """Queue a toast message to show after the next rerun."""
    st.session_state.setdefault("_flash", []).append((message, mono_icon(icon, ":material/check_circle:")))


def show_flash():
    """Display queued toast messages (called once at the top of every run)."""
    for message, icon in st.session_state.pop("_flash", []):
        st.toast(message, icon=mono_icon(icon, ":material/check_circle:"))


def done(message, icon=":material/check_circle:"):
    """Show a success toast and refresh the page so new data appears."""
    flash(message, icon)
    st.rerun()


def report(error, success_message, icon=":material/check_circle:"):
    """Common pattern: show the error, or refresh with a success toast."""
    if error:
        st.error(error, icon=":material/error:")
    else:
        done(success_message, icon)


# --------------------------------------------------------------------------
# Tables, metrics and charts
# --------------------------------------------------------------------------
def table(rows, column_config=None, height=None, key=None):
    """Show a list of dictionaries as a clean, full-width table."""
    if not rows:
        empty_state("Nothing to show yet.")
        return
    frame = pd.DataFrame(rows)
    hidden = [c for c in frame.columns if str(c).startswith("_")]
    frame = frame.drop(columns=hidden)
    options = {"hide_index": True, "width": "stretch", "column_config": column_config or {}}
    if height:
        options["height"] = height
    if key:
        options["key"] = key
    st.dataframe(frame, **options)


def pct_column(label, help_text=None):
    """Column config that shows a percentage as a progress bar."""
    return st.column_config.ProgressColumn(label, min_value=0, max_value=100, format="%.0f%%", help=help_text)


def metrics(items):
    """Row of technical metric cards. ``items`` = list of (label, value, help, delta)."""
    if not items:
        return
    per_row = 3 if len(items) > 4 else len(items)
    for row_start in range(0, len(items), per_row):
        chunk = items[row_start:row_start + per_row]
        columns = st.columns(len(chunk))
        for column, item in zip(columns, chunk):
            label, value = item[0], item[1]
            help_text = item[2] if len(item) > 2 else None
            delta = item[3] if len(item) > 3 else None
            with column.container(border=True):
                st.metric(label, value, delta=delta, help=help_text)


def bar_chart(rows, x, y, color=None, horizontal=False, height=280):
    if not rows:
        empty_state("No data for this chart yet.")
        return
    chart_color = color if color is not None else "#3B82F6"
    st.bar_chart(pd.DataFrame(rows), x=x, y=y, color=chart_color, horizontal=horizontal, height=height)


def line_chart(rows, x, y, height=280):
    if not rows:
        empty_state("No data for this chart yet.")
        return
    st.line_chart(pd.DataFrame(rows), x=x, y=y, color="#38BDF8", height=height)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
def subject_select(subjects, key, label="Subject", include_all=False):
    """Selectbox of subjects. Returns a subject id, or 'all'."""
    from classpilot import school  # local import avoids a circular import
    options = [s["id"] for s in subjects]
    labels = {s["id"]: school.subject_label(s) for s in subjects}
    if include_all:
        options = ["all"] + options
        labels["all"] = "All subjects"
    if not options:
        return None
    return st.selectbox(label, options, format_func=lambda v: labels.get(v, v), key=key)


def default_due(days=7):
    """A sensible default deadline: N days from now at 23:59."""
    return date.today() + timedelta(days=days), time(23, 59)


def file_download(file_info, key):
    """Download button for a stored upload (lesson material or submission)."""
    data = storage.read_upload(file_info["path"])
    if data is None:
        st.caption(f"[File missing] {file_info['name']}")
        return
    st.download_button(
        f"{file_info['name']} ({file_info['size'] // 1024 + 1} KB)",
        data=data,
        file_name=file_info["name"],
        key=key,
        icon=":material/attach_file:",
    )


def confirm_button(label, key, warning, button_type="secondary"):
    """Two-step button for dangerous actions. Returns True once confirmed."""
    flag = f"_confirm_{key}"
    if st.session_state.get(flag):
        st.warning(warning, icon=":material/error:")
        yes, no = st.columns(2)
        if yes.button("Yes, I'm sure", key=f"{key}_yes", type="primary", width="stretch"):
            st.session_state.pop(flag, None)
            return True
        if no.button("Cancel", key=f"{key}_no", width="stretch"):
            st.session_state.pop(flag, None)
            st.rerun()
        return False
    if st.button(label, key=key, type=button_type):
        st.session_state[flag] = True
        st.rerun()
    return False


# --------------------------------------------------------------------------
# Deadline Conflict Detector panel (used when creating assignments/quizzes)
# --------------------------------------------------------------------------
def deadline_check_panel(class_id, due_iso, date_key=None, time_key=None, exclude_id=None):
    """Show a live warning if the chosen deadline clashes with others for
    the same class. Returns the check result dictionary."""
    result = insights.check_conflicts(class_id, due_iso, exclude_id)
    if result["conflict"]:
        with st.container(border=True):
            st.markdown(
                f":red-badge[▲ CONFLICT DETECTED] &nbsp; **{result['load']} deadlines** for this class within "
                f"**{result['window']} days** (limit {result['limit'] - 1})."
            )
            for item in result["nearby"]:
                st.markdown(f"- {badge(item['kind'])} **{item['title']}** — {item['subject']} · {utils.fmt_dt(item['due'])}")
            if result["suggestion"]:
                suggestion = result["suggestion"]
                st.markdown(f":green-badge[● RECOMMENDED SLOT] &nbsp; **{suggestion.strftime('%a %d %b')}**")
                if date_key and time_key:
                    def _apply():
                        st.session_state[date_key] = suggestion.date()
                        st.session_state[time_key] = suggestion.time()
                    st.button(f"Use {suggestion.strftime('%a %d %b')} instead", on_click=_apply,
                              key=f"{date_key}_suggest", icon=":material/event:")
    elif result["nearby"]:
        lines = ", ".join(f"{i['title']} ({i['subject'].split(' · ')[0]}, {utils.fmt_date(i['due'])})"
                          for i in result["nearby"])
        with st.container(border=True):
            st.markdown(f":orange-badge[◆ NEARBY DEADLINES] &nbsp; {lines}. Still within the healthy limit.")
    else:
        with st.container(border=True):
            st.markdown(":green-badge[● SCHEDULE CLEAR] &nbsp; No other deadlines for this class around this date.")
    return result
