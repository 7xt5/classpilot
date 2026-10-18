# 🧭 Novarix — School Learning Management System

**Novarix** is a complete, beginner-friendly school Learning Management System (LMS) built in **100% Python** using **Streamlit** for the interface and **JSON files** for persistent storage.

It includes role-based dashboards for **Admins**, **Teachers**, and **Students**, along with distinctive workflow features designed for real schools:
- **ClassPulse** — private student confidence ratings (1–5) per lesson that aggregate anonymously for teachers to spot confusing topics early.
- **Deadline Conflict Detector** — warns teachers across *all* subjects taught to the same class when deadlines pile up within a configurable day window, and suggests the nearest calmer weekday.
- **Early Support Alerts** — automatically ranks students needing attention based on missing work, low averages, declining grade trends, and low attendance.

---

## ✨ Features by Role

### 🛡️ Admin
- **Smart Admin Dashboard:** School-wide metrics, class comparisons, setup health checks (unassigned students, idle teachers, locked accounts), deadline clusters, and support alerts.
- **User Management:** Create, edit, activate/deactivate, reset passwords, delete accounts (with cascading cleanup), and bulk-import users via CSV lines.
- **Class & Roster Management:** Create classes, assign rooms/grade levels, and manage rosters (automatically moving students if reassigned).
- **Subject Management:** Link courses to classes and teachers.
- **School Settings & Backups:** Customize school name, academic year, grading scale, and thresholds for Deadline Conflict Detector, Early Support Alerts, and ClassPulse. Download a full JSON backup or reset demo data with one click.

### 👩‍🏫 Teacher
- **Priority Dashboard:** Instant summary of ungraded submissions, today's missing attendance registers, high-priority student alerts, deadline clusters, and low-confidence lessons.
- **Lesson Hub:** Publish Markdown lesson notes, web links, and downloadable file attachments organized by subject and topic.
- **Assignments & Bulk Grading:** Create assignments with live cross-subject deadline conflict checks, configurable late policies/penalties, inline spreadsheet-style bulk grading, and individual submission review.
- **Quiz Builder:** Create multiple-choice quizzes with auto-grading, configurable attempt limits, publish/draft controls, and question-level item analysis (identifying the most common wrong answers).
- **Gradebook:** Full student × assessment matrix with letter grades, progress bars, per-item averages chart, individual student trend charts, and CSV export.
- **Attendance:** Fast daily register with one-click "Mark everyone present", attendance percentage reports (Present & Late count as attended; Excused is excluded), and a 15-session history grid.
- **ClassPulse, Early Support Alerts & Deadline Planner:** Dedicated analytics views to act on student confidence, support needs, and workload balance.

### 🎒 Student
- **Smart Student Dashboard:** Upcoming deadlines, missing-work warnings, overall average with trend indicator, attendance rate, announcements, and ClassPulse reminders.
- **Lessons & ClassPulse:** Read notes, open links, download worksheets, and privately rate lesson confidence (1–5) with optional anonymous comments.
- **Assignments:** Filter by status, submit text/links/files, resubmit before grading, see late penalty calculations, and read teacher feedback.
- **Quizzes:** Take multiple-choice quizzes, get instant auto-graded scores, retry if extra attempts are allowed (best score counts), and review correct answers.
- **My Grades & My Attendance:** Track subject averages, letter grades, score trends over time, and session-by-session attendance records.

### 🌐 Shared Features (All Roles)
- **Announcements:** Post whole-school or class-specific updates with priority badges, pinning, read/unread filters, and read receipts for authors.
- **Role-Scoped Global Search:** Quickly find people, classes, subjects, assignments, quizzes, lessons, resources, and grades permitted for your role.
- **Security:** Salted `PBKDF2-HMAC-SHA256` password hashing (200,000 iterations), temporary account lockout after 5 failed sign-ins, and strict role guards on both the UI and backend functions.

---

## 🗂️ Project Structure

```text
classpilot/
├── app.py                  # Main Streamlit entry point & role navigation
├── requirements.txt        # Python dependencies
├── README.md               # Setup & architecture guide
├── .streamlit/
│   └── config.toml         # Clean light theme & upload limit config
├── classpilot/             # Core backend & UI helpers
│   ├── storage.py          # Atomic JSON file storage & safe file uploads
│   ├── auth.py             # PBKDF2 password hashing, lockout & role guards
│   ├── school.py           # Users, classes, subjects & announcements logic
│   ├── coursework.py       # Lessons, assignments, submissions & quizzes logic
│   ├── tracking.py         # Gradebook, attendance & ClassPulse calculations
│   ├── insights.py         # Conflict detector, support alerts & search
│   ├── seed.py             # Realistic, date-relative demo data generator
│   └── ui.py               # Reusable native Streamlit UI components
├── views/                  # One module per feature area
│   ├── login.py            # Sign-in screen & demo account table
│   ├── dashboard.py        # Admin, Teacher & Student dashboards
│   ├── admin.py            # Users, classes, subjects & settings pages
│   ├── lessons.py          # Teacher & Student Lesson Hub + ClassPulse input
│   ├── assignments.py      # Assignment manager, grading & student submissions
│   ├── quizzes.py          # Quiz Builder, item analysis & student quiz taker
│   ├── gradebook.py        # Teacher gradebook & Student grades view
│   ├── attendance.py       # Register, reports & Student attendance view
│   ├── pulse.py            # Teacher ClassPulse analytics
│   ├── support.py          # Early Support Alerts & Deadline Planner
│   ├── announcements.py    # Announcements feed & read receipts
│   ├── search.py           # Role-scoped search page
│   └── profile.py          # Account details & password change
└── data/                   # Auto-created JSON files & uploaded attachments
```

---

## 🚀 Setup & Running Instructions

### 1. Prerequisites
- **Python 3.10+** installed on your computer.

### 2. Install Dependencies
Open a terminal in the `classpilot` folder and run:

```bash
python -m pip install -r requirements.txt
```

### 3. Start Novarix
```bash
python -m streamlit run app.py
```
*(Or simply run `python run.py`, or double-click `run.bat` on Windows.)*

On first launch, Novarix automatically generates realistic demo data in the `data/` directory relative to today's date.

---

## 🔑 Demo Accounts

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@123` | Full school setup & insights |
| **Teacher** | `sara.khan` | `Teacher@123` | Mathematics (Grade 9 - A & Grade 10 - B) |
| **Teacher** | `bilal.ahmed` | `Teacher@123` | General Science (9A) & Physics (10B) |
| **Teacher** | `emily.wilson` | `Teacher@123` | English Language (9A) & Literature (10B) |
| **Student** | `ali.raza` | `Student@123` | Grade 9 - A |
| **Student** | `hamza.sheikh` | `Student@123` | Grade 9 - A (triggers Early Support Alert) |
| **Student** | `maryam.iqbal` | `Student@123` | Grade 10 - B |

*(All other demo students also use `Student@123`.)*
