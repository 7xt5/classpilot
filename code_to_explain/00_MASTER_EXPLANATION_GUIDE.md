# Novarix — Master Code Explanation & Presentation Guide

This folder (`code_to_explain/`) contains the **essential core code** of **Novarix** organized in numbered order (`01` to `07`) so you can easily study, present, and explain how your project works to a teacher, examiner, or judge.

---

## 1. High-Level Architecture (What to Say First)

- **Project Name:** **Novarix** (Smart Classroom & AI Learning Management System)
- **Language & Stack:** **100% Pure Python**
  - **Frontend & UI:** `streamlit` (native Python UI components, layouts, forms, tables, and charts — zero HTML, CSS, or JavaScript in `.py` files)
  - **Data Analysis & Tables:** `pandas`
  - **Database / Persistence:** Pure-Python **JSON file engine** (`data/*.json`) using Python's built-in `json` and `pathlib` modules (no SQL or SQLite required)
  - **Security:** Python's built-in `hashlib` (`PBKDF2-HMAC-SHA256` with 120,000 iterations + random salt) and `hmac`
  - **AI Engine (`NovaAI`):** Uses Python's standard `urllib.request` to call a live OpenAI-compatible Large Language Model (LLM) grounded in live classroom JSON data (RAG), combined with a Symbolic Math Solver built on Python's `ast` (Abstract Syntax Tree) module.

---

## 2. Folder Walkthrough (The 7 Files You Need to Know)

### [`01_app_router.py`](./01_app_router.py) — Entry Point & Role-Based Navigation (from `app.py`)
- **What it does:** Starts the app, ensures the `data/` folder exists, checks if a user is logged in, and builds a different navigation menu depending on the user's role:
  1. **Not Logged In:** Shows the Front Overview Landing Page and Sign Up / Log In portal (`views/login.py`).
  2. **Teacher:** Opens the Custom Teacher Studio Dashboard, NovaAI Copilot, Lesson Hub, Assignments, Quiz Builder, Attendance, Gradebook, NovaPulse, Early Support Alerts, and Deadline Planner.
  3. **Student:** Opens the Student Dashboard, NovaAI Study Tutor, Lessons, Assignments, Quizzes, My Grades, and My Attendance.
  4. **Admin:** Opens School Setup (Users, Classes, Subjects, Settings) + all teaching & insight tools.

### [`02_storage_engine.py`](./02_storage_engine.py) — JSON Database Engine (from `classpilot/storage.py`)
- **What it does:** Replaces SQL with clean JSON files stored in `data/` (`users.json`, `classes.json`, `subjects.json`, `lessons.json`, `assignments.json`, `submissions.json`, `quizzes.json`, `attendance.json`, `pulse.json`).
- **Key Functions to Explain:**
  - `load(collection)` / `save(collection, rows)`: Reads and writes a list of dictionaries to `data/<collection>.json`. Uses a temporary `.tmp` file and atomic `Path.replace()` so data is never corrupted.
  - `find(collection, **filters)`: Filters records using Python list comprehensions (e.g., `storage.find("submissions", assignment_id=a_id)`).
  - `insert(collection, record)` / `update(collection, record_id, changes)` / `delete(collection, record_id)`: Full CRUD (Create, Read, Update, Delete) in pure Python.

### [`03_auth_security.py`](./03_auth_security.py) — Password Hashing & "Remember Me" Sessions (from `classpilot/auth.py`)
- **What it does:** Handles account security, sign-in verification, and persistent login sessions.
- **Key Functions to Explain:**
  - `hash_password(password)`: Generates a 16-byte cryptographic salt with `secrets.token_hex(16)` and hashes the password with `hashlib.pbkdf2_hmac("sha256", ..., 120_000)`. Plain-text passwords are **never** stored.
  - `verify_password(password, stored)`: Recomputes the hash with the stored salt and uses `hmac.compare_digest()` to prevent timing attacks.
  - `login_session(user, remember=True)`: Stores the active user in `st.session_state["user_id"]` and issues a signed token (`?session=...` in `st.query_params` + `sessions.json`) so refreshing the browser keeps the user logged in.

### [`04_coursework_and_quizzes.py`](./04_coursework_and_quizzes.py) — Assignments, Late Penalties & Auto-Graded Quizzes (from `classpilot/coursework.py`)
- **What it does:** Powers the core academic workflow between teachers and students.
- **Key Functions to Explain:**
  - `submit_assignment()`: Saves a student's written work and uploaded file, and checks if the current timestamp is past the assignment's `due_at` deadline.
  - `grade_submission()`: Calculates the late penalty automatically (`late_penalty_per_day` × days late, capped at `max_late_penalty`) and records the final score and teacher feedback.
  - `submit_quiz_attempt()`: Compares the student's selected option index against `q["answer"]` for every question and calculates their score (`score / max_score`) instantaneously.

### [`05_smart_insights_and_alerts.py`](./05_smart_insights_and_alerts.py) — Early Support Alerts & Deadline Conflict Detector (from `classpilot/insights.py`)
- **What it does:** Provides automated classroom intelligence using pure Python rules.
- **Key Functions to Explain:**
  - `support_alerts(subjects)`: Scans every student in every subject and calculates a **concern score** based on 4 signals:
    1. **Missing work** past the deadline (+2 pts each)
    2. **Low subject average** below threshold, e.g., <60% (+3 pts)
    3. **Declining grade trend** comparing recent grades vs. earlier grades (+2 pts)
    4. **Low attendance** below threshold, e.g., <80% (+2 pts)
  - `check_conflicts(class_id, due_iso)`: Checks a ±3 day window around a proposed due date. If a class already has too many deadlines in that window, it warns the teacher and suggests the next clear date.

### [`06_nova_ai_engine.py`](./06_nova_ai_engine.py) — Live Cloud LLM + Classroom RAG + Symbolic Math Solver (from `classpilot/ai_assistant.py`)
- **What it does:** Powers the **NovaAI Copilot** (for teachers) and **NovaAI Study Tutor** (for students).
- **Key Functions to Explain:**
  - `call_live_llm(messages)`: Sends a JSON `POST` request using Python's `urllib.request` to an OpenAI-compatible Cloud LLM endpoint (`https://text.pollinations.ai/openai` or a custom OpenAI/Groq API key).
  - `_build_teacher_rag_context()` & `_build_student_rag_context()`: **Retrieval-Augmented Generation (RAG)** — gathers the user's real classes, grades, missing work, and lesson notes from JSON and injects them into the AI's system prompt so the AI knows the user's live school data.
  - `solve_math_problem(query)`: Uses Python's `ast` module, quadratic formula ($\Delta = b^2 - 4ac$), symbolic differentiation (Power Rule), and `statistics` module to verify math calculations accurately.

### [`07_dashboards_and_ui.py`](./07_dashboards_and_ui.py) — Overview Landing Page, Sign-Up & Custom Dashboards (from `views/login.py` & `views/dashboard.py`)
- **What it does:** Shows how Streamlit columns, containers, forms, metrics, and charts build the user interface.
- **Key Highlights:**
  - **Landing Page (`_render_landing_page`)**: Explains Novarix before the user clicks **Sign Up / Log In**.
  - **Self-Registration (`login_page`)**: Lets a new user choose **Teacher** or **Student**, creates their account in `users.json`, and opens their tailored dashboard immediately.
  - **Teacher Custom Studio (`teacher_dashboard`)**: Teachers build their own workspace by adding classes, assignments to check, and custom checklist items stored in `teacher_prefs.json`.

---

## 3. Top Questions & Answers for Your Code Defense / Viva

1. **Q: Why did you use JSON files instead of SQLite or MySQL?**
   - **A:** Using a modular JSON storage layer (`storage.py`) keeps the project 100% pure Python with zero external database servers, while still supporting atomic writes (`.tmp` file replacement), auto-generated IDs, and key-value filtering (`storage.find()`).

2. **Q: How do you keep passwords secure without a third-party auth library?**
   - **A:** In `auth.py`, every password gets a unique 16-byte random salt from `secrets.token_hex(16)` and is hashed using `hashlib.pbkdf2_hmac('sha256', ...)` with 120,000 iterations. Even if two users pick the same password, their stored hashes are completely different.

3. **Q: How does the AI Assistant (`NovaAI`) actually work?**
   - **A:** It combines three layers in `ai_assistant.py`:
     1. **Live RAG Context:** Before calling the AI, Python reads the user's live classes, assignments, grades, and lessons from our JSON files and puts them into the system prompt.
     2. **Live Cloud LLM Inference:** Python sends the conversation history and system prompt via `urllib.request` to an OpenAI-compatible LLM endpoint, which returns both the answer and its reasoning trace.
     3. **Symbolic Math Verifier:** For equations, derivatives, or statistics, Python also computes the exact mathematical result using `ast`, `math`, and `statistics` so the AI never makes arithmetic mistakes.

4. **Q: How does the Early Support Alert system decide which students need help?**
   - **A:** In `insights.py`, `support_alerts()` evaluates every student across 4 measurable criteria: missing assignments, subject average below 60%, a drop of 12+ percentage points between earlier and recent work, and attendance below 80%. Each trigger adds concern points to rank students into High or Medium priority.

5. **Q: How did you style the dark sapphire-blue grid theme without writing HTML or CSS in your Python files?**
   - **A:** All styling is configured declaratively inside `.streamlit/config.toml` using Streamlit's native `[theme]`, `[theme.sidebar]`, and `[[theme.fontFaces]]` settings, keeping every `.py` file 100% pure Python.

6. **Q: How does the Single Admin Account & Class Join Request approval system work?**
   - **A:** In `seed.py` and `school.py`, the system enforces **1 School Admin account** (`admin` / `Admin@123`) who owns all classes and can add or remove classes (`create_class()`, `delete_class()`). When a Teacher or Student clicks **Join Class** on their dashboard, `request_join_class()` saves a `"pending"` request in `data/join_requests.json`. On the Admin Dashboard (`admin_dashboard()`), the Admin sees all pending requests and clicks **Accept** (`approve_join_request()`), which enrolls the student into the class roster or links the teacher and creates their subject for that class.
