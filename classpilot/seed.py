"""
seed.py - Realistic demo data for Novarix.

Runs automatically the first time the app starts (when there are no users).
All dates are calculated relative to *today*, so the demo always shows
upcoming deadlines, recent grades and fresh announcements.

Demo accounts
  admin         / Admin@123
  sara.khan     / Teacher@123   (Mathematics)
  bilal.ahmed   / Teacher@123   (Science & Physics)
  emily.wilson  / Teacher@123   (English)
  ali.raza      / Student@123   (Grade 9 - A)
  maryam.iqbal  / Student@123   (Grade 10 - B)
  ... every student uses Student@123
"""

import random
from datetime import date, datetime, timedelta

from classpilot import auth, storage

DEMO_ACCOUNTS = [
    ("Admin", "admin", "Admin@123"),
    ("Teacher", "sara.khan", "Teacher@123"),
    ("Teacher", "bilal.ahmed", "Teacher@123"),
    ("Teacher", "emily.wilson", "Teacher@123"),
    ("Student", "ali.raza", "Student@123"),
    ("Student", "maryam.iqbal", "Student@123"),
]

# (username, full name, base ability %, trend per week) - trend < 0 = declining
STUDENTS_9A = [
    ("ali.raza", "Ali Raza", 82, 0), ("ayesha.malik", "Ayesha Malik", 93, 0),
    ("omar.farooq", "Omar Farooq", 74, 1), ("zara.hussain", "Zara Hussain", 88, 0),
    ("hamza.sheikh", "Hamza Sheikh", 80, -12), ("fatima.noor", "Fatima Noor", 69, 2),
]
STUDENTS_10B = [
    ("daniyal.qureshi", "Daniyal Qureshi", 85, 0), ("maryam.iqbal", "Maryam Iqbal", 91, 0),
    ("usman.tariq", "Usman Tariq", 88, -11), ("hira.aslam", "Hira Aslam", 77, 1),
    ("saad.butt", "Saad Butt", 66, 0), ("leena.joseph", "Leena Joseph", 95, 0),
]
POOR_ATTENDANCE = {"hamza.sheikh": 0.22, "saad.butt": 0.25}
MISSES_WORK = {"hamza.sheikh": 0.45, "saad.butt": 0.2}


def _at(days, hour=23, minute=59):
    """ISO date-time ``days`` from today at the given clock time."""
    moment = datetime.now() + timedelta(days=days)
    return moment.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat(timespec="minutes")


def _ts(days, hour=10, minute=0):
    """ISO timestamp (with seconds) ``days`` from today."""
    return _at(days, hour, minute) + ":00"


# --------------------------------------------------------------------------
# Course content: lessons, assignments and quizzes for each subject
# --------------------------------------------------------------------------
SUBJECTS = {
    "MATH9A": {
        "name": "Mathematics", "class": "9A", "teacher": "sara.khan",
        "description": "Core algebra and geometry for Grade 9.",
        "lessons": [
            ("Algebra", "Solving Linear Equations", 4.1,
             "## Key ideas\n- An equation is balanced: whatever you do to one side, do to the other.\n"
             "- Undo operations in reverse order (BIDMAS backwards).\n\n"
             "## Worked example\nSolve `3x + 5 = 20`\n1. Subtract 5 → `3x = 15`\n2. Divide by 3 → `x = 5`\n\n"
             "## Practice\nTry questions 1-12 on the worksheet before Friday.",
             [("Maths is Fun - Solving equations", "https://www.mathsisfun.com/algebra/equations-solving.html"),
              ("Khan Academy - Algebra basics", "https://www.khanacademy.org/math/algebra-basics")],
             ("linear_equations_worksheet.txt",
              "Linear Equations Worksheet\n\n1) 2x + 3 = 11\n2) 5x - 4 = 21\n3) 7 = 3x - 8\n4) 4(x + 2) = 28\n")),
            ("Algebra", "Factorising Quadratics", 2.1,
             "## Key ideas\n- Look for two numbers that **multiply** to `c` and **add** to `b`.\n"
             "- Always check for a common factor first.\n\n## Example\n`x² + 7x + 12 = (x + 3)(x + 4)`\n\n"
             "## Watch out\nSigns! For `x² - x - 12` you need `-4` and `+3`.",
             [("Maths is Fun - Factoring quadratics", "https://www.mathsisfun.com/algebra/factoring-quadratics.html")],
             None),
            ("Geometry", "Pythagoras' Theorem", 3.8,
             "## Formula\n`a² + b² = c²` where `c` is the hypotenuse (longest side).\n\n"
             "## Steps\n1. Label the hypotenuse.\n2. Square the two known sides.\n3. Add (finding c) or subtract (finding a shorter side).\n4. Square root.",
             [("Maths is Fun - Pythagoras", "https://www.mathsisfun.com/pythagoras.html")], None),
        ],
        "assignments": [
            ("Linear Equations Practice Set", "Complete questions 1-20 from the worksheet. Show every step of your working.", -20, 20),
            ("Equations Word Problems", "Write and solve equations for the 8 word problems in the lesson notes.", -13, 30),
            ("Quadratics Factorising Drill", "Factorise the 15 quadratics. Check each answer by expanding.", -6, 30),
            ("Pythagoras in Real Life", "Find 3 real-world right triangles, measure two sides and calculate the third.", -1, 25),
            ("Geometry Problem Set", "Problems 1-15 on angles, triangles and Pythagoras.", 5, 40),
        ],
        "quizzes": [
            ("Algebra Checkpoint", -9, True, [
                ("Solve 2x + 6 = 14", ["x = 3", "x = 4", "x = 10", "x = 5"], 1),
                ("Factorise x² + 5x + 6", ["(x + 2)(x + 3)", "(x + 1)(x + 6)", "(x - 2)(x - 3)", "(x + 5)(x + 1)"], 0),
                ("Which value of x solves 5x - 5 = 0?", ["0", "5", "1", "-1"], 2),
                ("Expand 3(x - 4)", ["3x - 4", "3x - 12", "x - 12", "3x + 12"], 1),
            ]),
            ("Pythagoras Quick Quiz", 12, True, [
                ("A right triangle has legs 3 and 4. The hypotenuse is:", ["5", "6", "7", "12"], 0),
                ("Which side is the hypotenuse?", ["The shortest side", "Opposite the right angle", "Next to the right angle", "Any side"], 1),
                ("Legs 6 and 8 give a hypotenuse of:", ["10", "14", "48", "12"], 0),
            ]),
        ],
    },
    "SCI9A": {
        "name": "General Science", "class": "9A", "teacher": "bilal.ahmed",
        "description": "Biology, chemistry and physics foundations.",
        "lessons": [
            ("Cells", "Cell Structure and Function", 3.9,
             "## Animal vs plant cells\n| Part | Animal | Plant |\n|---|---|---|\n| Nucleus | ✔ | ✔ |\n| Cell wall | ✘ | ✔ |\n| Chloroplast | ✘ | ✔ |\n\n"
             "The **mitochondria** release energy through respiration.",
             [("Khan Academy - Biology", "https://www.khanacademy.org/science/biology")], None),
            ("Chemistry Basics", "Atoms and the Periodic Table", 3.3,
             "## Atom structure\n- Protons (+) and neutrons in the nucleus\n- Electrons (−) in shells\n\n"
             "Groups = columns (same outer electrons). Periods = rows.",
             [("Interactive periodic table", "https://ptable.com")], None),
            ("Forces", "Newton's Laws of Motion", 2.3,
             "1. An object stays at rest or keeps moving unless a force acts on it.\n2. `F = m × a`\n3. Every action has an equal and opposite reaction.",
             [("PhET - Forces and Motion simulation", "https://phet.colorado.edu/en/simulations/forces-and-motion-basics")], None),
        ],
        "assignments": [
            ("Cell Diagram", "Draw and label an animal and a plant cell. Explain the job of each part.", -18, 20),
            ("Periodic Table Research", "Choose one element and write a one-page profile.", -11, 25),
            ("Forces Lab Report", "Write up the trolley-and-ramp experiment using the lab report template.", -4, 40),
            ("Newton's Laws Poster", "Create a poster with a real-life example for each of Newton's three laws.", 6, 30),
        ],
        "quizzes": [
            ("Cells & Atoms Quiz", -8, True, [
                ("Which organelle releases energy?", ["Nucleus", "Mitochondria", "Cell wall", "Vacuole"], 1),
                ("Plant cells have ... but animal cells do not.", ["A nucleus", "Cytoplasm", "A cell wall", "A membrane"], 2),
                ("The charge of an electron is:", ["Positive", "Neutral", "Negative", "It varies"], 2),
                ("Rows in the periodic table are called:", ["Groups", "Periods", "Blocks", "Families"], 1),
            ]),
        ],
    },
    "ENG9A": {
        "name": "English Language", "class": "9A", "teacher": "emily.wilson",
        "description": "Reading, writing and speaking skills.",
        "lessons": [
            ("Writing Skills", "Persuasive Writing Techniques", 4.0,
             "Remember **AFOREST**: Alliteration, Facts, Opinions, Rhetorical questions, Emotive language, Statistics, Triples.",
             [("BBC Bitesize - English", "https://www.bbc.co.uk/bitesize/subjects/zr9d7ty")], None),
            ("Poetry", "Analysing Imagery in Poetry", 3.0,
             "Use **PEEL** paragraphs: Point, Evidence, Explain, Link.\n\nLook for similes, metaphors and personification.",
             [("Poetry Foundation", "https://www.poetryfoundation.org")], None),
        ],
        "assignments": [
            ("Persuasive Letter", "Write a 400-word letter persuading the principal to change one school rule.", -16, 30),
            ("Poetry Analysis Paragraphs", "Write three PEEL paragraphs analysing imagery in the poem from class.", -5, 30),
            ("Short Story Draft", "Draft a 600-word short story using at least three descriptive techniques.", 6, 40),
        ],
        "quizzes": [],
    },
    "MATH10B": {
        "name": "Mathematics", "class": "10B", "teacher": "sara.khan",
        "description": "Trigonometry and statistics for Grade 10.",
        "lessons": [
            ("Trigonometry", "SOH CAH TOA", 3.7,
             "- `sin θ = opposite / hypotenuse`\n- `cos θ = adjacent / hypotenuse`\n- `tan θ = opposite / adjacent`",
             [("Maths is Fun - Trigonometry", "https://www.mathsisfun.com/sine-cosine-tangent.html")], None),
            ("Trigonometry", "Sine and Cosine Rules", 2.2,
             "- Sine rule: `a / sin A = b / sin B`\n- Cosine rule: `a² = b² + c² − 2bc cos A`\n\nUse the cosine rule when you know two sides and the angle **between** them.",
             [("Maths is Fun - Law of Sines", "https://www.mathsisfun.com/algebra/trig-sine-law.html")], None),
            ("Statistics", "Mean, Median and Mode", 4.3,
             "- Mean: add up and divide by how many\n- Median: middle value when ordered\n- Mode: most common value",
             [("Khan Academy - Statistics", "https://www.khanacademy.org/math/statistics-probability")], None),
        ],
        "assignments": [
            ("Trigonometry Basics", "Questions 1-18 using SOH CAH TOA.", -19, 30),
            ("Sine & Cosine Rule Problems", "Solve the 10 triangle problems. Draw a diagram for each.", -12, 30),
            ("Statistics Survey Project", "Collect data from 20 people and calculate mean, median, mode and range.", -3, 50),
            ("Trigonometry Review Sheet", "Mixed review in preparation for the unit test.", 4, 30),
        ],
        "quizzes": [
            ("Trigonometry Quiz", -7, True, [
                ("sin θ equals:", ["adjacent/hypotenuse", "opposite/hypotenuse", "opposite/adjacent", "hypotenuse/opposite"], 1),
                ("tan 45° equals:", ["0", "0.5", "1", "Undefined"], 2),
                ("Use the cosine rule when you know:", ["Three angles", "Two sides and the included angle", "One side only", "Two angles"], 1),
                ("cos 60° equals:", ["0.5", "1", "0.866", "0"], 0),
            ]),
            ("Statistics Check-in", 9, True, [
                ("The median of 2, 5, 9 is:", ["5", "9", "2", "16"], 0),
                ("The mode of 3, 3, 4, 7 is:", ["3", "4", "7", "4.25"], 0),
                ("The mean of 2, 4, 6 is:", ["3", "4", "6", "12"], 1),
            ]),
            ("Probability Starter (draft)", 20, False, [
                ("The probability of a fair coin landing heads is:", ["0", "0.25", "0.5", "1"], 2),
            ]),
        ],
    },
    "PHY10B": {
        "name": "Physics", "class": "10B", "teacher": "bilal.ahmed",
        "description": "Electricity, waves and energy.",
        "lessons": [
            ("Electricity", "Ohm's Law and Circuits", 3.5,
             "`V = I × R`\n\n- Voltage (V) in volts\n- Current (I) in amps\n- Resistance (R) in ohms",
             [("PhET - Circuit Construction Kit", "https://phet.colorado.edu/en/simulations/circuit-construction-kit-dc")], None),
            ("Electricity", "Series and Parallel Circuits", 2.0,
             "- **Series:** same current everywhere, voltages add up.\n- **Parallel:** same voltage on each branch, currents add up.",
             [("PhET - Circuit Construction Kit", "https://phet.colorado.edu/en/simulations/circuit-construction-kit-dc")], None),
            ("Waves", "Properties of Waves", 3.9,
             "Wave speed: `v = f × λ`.\n\nTransverse waves vibrate at right angles to the direction of travel; longitudinal waves vibrate parallel to it.",
             [("PhET - Wave on a String", "https://phet.colorado.edu/en/simulations/wave-on-a-string")], None),
        ],
        "assignments": [
            ("Ohm's Law Calculations", "Complete the 12 calculation questions.", -17, 24),
            ("Circuit Building Lab", "Report on series vs parallel circuits built in the lab.", -10, 40),
            ("Waves Worksheet", "Label wave diagrams and calculate wave speeds.", -2, 20),
            ("Energy Resources Essay", "Compare two renewable energy resources (500 words).", 11, 40),
        ],
        "quizzes": [
            ("Electricity Quiz", -6, True, [
                ("Ohm's law is:", ["V = I × R", "P = I × V", "F = m × a", "E = m × c²"], 0),
                ("In a series circuit the current is:", ["Different in each component", "The same everywhere", "Zero", "Doubled"], 1),
                ("Resistance is measured in:", ["Volts", "Amps", "Ohms", "Watts"], 2),
                ("Adding branches in parallel makes total resistance:", ["Increase", "Decrease", "Stay the same", "Zero"], 1),
            ]),
        ],
    },
    "ENG10B": {
        "name": "English Literature", "class": "10B", "teacher": "emily.wilson",
        "description": "Shakespeare, poetry anthology and essay skills.",
        "lessons": [
            ("Shakespeare", "Macbeth Act 1 - Ambition", 3.6,
             "Focus on Macbeth's soliloquy *'Stars, hide your fires'*. What does it reveal about his ambition?",
             [("Folger Shakespeare - Macbeth", "https://www.folger.edu/explore/shakespeares-works/macbeth/")], None),
            ("Essay Skills", "Structuring a Literary Essay", 3.1,
             "1. Thesis statement\n2. Three analytical paragraphs\n3. Conclusion linking back to the question",
             [("Purdue OWL - Writing about literature", "https://owl.purdue.edu/owl/subject_specific_writing/writing_in_literature/index.html")], None),
        ],
        "assignments": [
            ("Macbeth Character Study", "A 500-word study of Lady Macbeth in Act 1.", -15, 30),
            ("Essay Plan: Ambition", "Plan an essay on how ambition is presented in Macbeth.", -8, 20),
            ("Act 2 Analysis", "Analyse the dagger soliloquy (Act 2 Scene 1).", 9, 30),
        ],
        "quizzes": [],
    },
}

PULSE_NOTES = {
    "low": ["The part with negative numbers lost me", "Could we do more worked examples?",
            "I understood the class example but not the homework", "Went a bit too fast for me"],
    "high": ["Really clear explanation!", "The practice questions helped a lot", "The simulation made it click"],
}


# --------------------------------------------------------------------------
# Main seeding function
# --------------------------------------------------------------------------
def seed_demo_data():
    """Create all demo records. Existing data is replaced."""
    rng = random.Random(2026)
    storage.wipe_all()
    storage.save_settings(dict(storage.DEFAULT_SETTINGS))

    # ---- Users ---------------------------------------------------------
    users, by_username = [], {}

    def add_user(username, full_name, role, password, ability=None, trend=0):
        user = {
            "id": storage.new_id("usr"), "username": username, "full_name": full_name,
            "email": f"{username}@riverside.edu", "role": role,
            "password_hash": auth.hash_password(password), "active": True,
            "created_at": _ts(-60), "last_login": None, "failed_attempts": 0, "locked_until": None,
        }
        users.append(user)
        by_username[username] = {**user, "ability": ability, "trend": trend}
        return user

    add_user("admin", "Nadia Rahman", "admin", "Admin@123")
    add_user("sara.khan", "Sara Khan", "teacher", "Teacher@123")
    add_user("bilal.ahmed", "Bilal Ahmed", "teacher", "Teacher@123")
    add_user("emily.wilson", "Emily Wilson", "teacher", "Teacher@123")
    for username, name, ability, trend in STUDENTS_9A + STUDENTS_10B:
        add_user(username, name, "student", "Student@123", ability, trend)
    storage.save("users", users)

    # ---- Classes -------------------------------------------------------
    classes = {
        "9A": {"id": storage.new_id("cls"), "name": "Grade 9 - A", "grade_level": "Grade 9", "room": "Room 104",
               "student_ids": [by_username[s[0]]["id"] for s in STUDENTS_9A], "created_at": _ts(-60)},
        "10B": {"id": storage.new_id("cls"), "name": "Grade 10 - B", "grade_level": "Grade 10", "room": "Room 211",
                "student_ids": [by_username[s[0]]["id"] for s in STUDENTS_10B], "created_at": _ts(-60)},
    }
    storage.save("classes", list(classes.values()))
    roster = {"9A": STUDENTS_9A, "10B": STUDENTS_10B}

    subjects, lessons, assignments, submissions = [], [], [], []
    quizzes, attempts, pulse = [], [], []

    for code, spec in SUBJECTS.items():
        teacher_id = by_username[spec["teacher"]]["id"]
        subject = {"id": storage.new_id("sub"), "name": spec["name"], "code": code,
                   "class_id": classes[spec["class"]]["id"], "teacher_id": teacher_id,
                   "description": spec["description"], "created_at": _ts(-60)}
        subjects.append(subject)
        students = [by_username[s[0]] for s in roster[spec["class"]]]

        # ---- Lessons + ClassPulse ratings ------------------------------
        for index, (topic, title, mood, content, resources, demo_file) in enumerate(spec["lessons"]):
            files = []
            if demo_file:
                folder = storage.UPLOAD_DIR / "lessons"
                folder.mkdir(parents=True, exist_ok=True)
                stored = f"demo{index}_{demo_file[0]}"
                (folder / stored).write_text(demo_file[1], encoding="utf-8")
                files.append({"name": demo_file[0], "path": f"lessons/{stored}", "size": len(demo_file[1])})
            lesson = {"id": storage.new_id("les"), "subject_id": subject["id"], "topic": topic, "title": title,
                      "content": content, "resources": [{"label": l, "url": u} for l, u in resources],
                      "files": files, "created_by": teacher_id,
                      "created_at": _ts(-25 + index * 6), "updated_at": _ts(-25 + index * 6)}
            lessons.append(lesson)
            for student in students:
                if rng.random() < 0.15:  # not everyone responds
                    continue
                rating = max(1, min(5, round(rng.gauss(mood, 0.8))))
                note = ""
                if rng.random() < 0.35:
                    note = rng.choice(PULSE_NOTES["low" if rating <= 2 else "high"]) if rating != 3 else ""
                pulse.append({"id": storage.new_id("pls"), "lesson_id": lesson["id"], "subject_id": subject["id"],
                              "student_id": student["id"], "rating": rating, "note": note,
                              "updated_at": _ts(-20 + index * 6)})

        # ---- Assignments + submissions ---------------------------------
        for title, description, offset, points in spec["assignments"]:
            assignment = {"id": storage.new_id("asg"), "subject_id": subject["id"], "title": title,
                          "description": description, "due": _at(offset), "max_points": points,
                          "allow_late": True, "late_penalty": 10, "created_by": teacher_id,
                          "created_at": _ts(offset - 10)}
            assignments.append(assignment)
            if offset > 0:
                continue  # future work: nobody has submitted yet
            graded = offset <= -4  # the most recent work is still waiting to be graded
            for student in students:
                if rng.random() < MISSES_WORK.get(student["username"], 0.04) and offset > -20:
                    continue  # missing work
                late = rng.random() < 0.12
                submitted = _at(offset + (1 if late else -1), rng.randint(15, 21), rng.randint(0, 59)) + ":00"
                weeks_ago = abs(offset) / 7
                level = student["ability"] + student["trend"] * (3 - weeks_ago)
                pct = max(25, min(100, rng.gauss(level, 6)))
                score = round(points * pct / 100) if graded else None
                feedback = ""
                if graded:
                    feedback = ("Excellent work - clear and well organised." if pct >= 88 else
                                "Good effort. Review the steps you missed." if pct >= 70 else
                                "Let's go over this together - please see me after class.")
                submissions.append({
                    "id": storage.new_id("smb"), "assignment_id": assignment["id"], "student_id": student["id"],
                    "text": f"Submission for '{title}'. All questions are answered below with working shown.",
                    "link": "", "file": None, "submitted_at": submitted, "offline": False, "revision": 1,
                    "score": score, "feedback": feedback,
                    "graded_at": _ts(offset + 2) if graded else None,
                    "graded_by": teacher_id if graded else None,
                })

        # ---- Quizzes + attempts ----------------------------------------
        for title, offset, published, questions in spec["quizzes"]:
            quiz = {"id": storage.new_id("quiz"), "subject_id": subject["id"], "title": title,
                    "description": f"Multiple-choice quiz on recent {spec['name'].lower()} topics.",
                    "due": _at(offset), "attempts_allowed": 1 if offset < 0 else 2, "show_answers": True,
                    "published": published, "created_by": teacher_id, "created_at": _ts(offset - 7),
                    "questions": [{"id": storage.new_id("q"), "text": q, "options": opts, "answer": ans, "points": 1}
                                  for q, opts, ans in questions]}
            quizzes.append(quiz)
            if offset > 0 or not published:
                continue
            for student in students:
                if rng.random() < MISSES_WORK.get(student["username"], 0.03):
                    continue
                level = student["ability"] + student["trend"] * (3 - abs(offset) / 7)
                answers, score = {}, 0
                for q in quiz["questions"]:
                    if rng.random() * 100 < level:
                        answers[q["id"]] = q["answer"]
                        score += 1
                    else:
                        wrong = [i for i in range(len(q["options"])) if i != q["answer"]]
                        answers[q["id"]] = rng.choice(wrong)
                attempts.append({"id": storage.new_id("att"), "quiz_id": quiz["id"], "student_id": student["id"],
                                 "answers": answers, "score": score, "max_score": len(quiz["questions"]),
                                 "percent": round(100 * score / len(quiz["questions"]), 1),
                                 "submitted_at": _at(offset - 1, 18, rng.randint(0, 59)) + ":00"})

    storage.save("subjects", subjects)
    storage.save("lessons", lessons)
    storage.save("assignments", assignments)
    storage.save("submissions", submissions)
    storage.save("quizzes", quizzes)
    storage.save("quiz_attempts", attempts)
    storage.save("pulse", pulse)

    # ---- Attendance: the last 20 school days (today is left for the demo) --
    attendance, day, recorded = [], date.today() - timedelta(days=1), 0
    while recorded < 20:
        if day.weekday() < 5:
            for subject in subjects:
                class_key = "9A" if subject["class_id"] == classes["9A"]["id"] else "10B"
                records = {}
                for username, *_ in roster[class_key]:
                    roll = rng.random()
                    absent_chance = POOR_ATTENDANCE.get(username, 0.04)
                    if roll < absent_chance:
                        status = "Absent"
                    elif roll < absent_chance + 0.05:
                        status = "Late"
                    elif roll < absent_chance + 0.07:
                        status = "Excused"
                    else:
                        status = "Present"
                    records[by_username[username]["id"]] = status
                attendance.append({"id": storage.new_id("atd"), "subject_id": subject["id"], "date": day.isoformat(),
                                   "records": records, "taken_by": subject["teacher_id"],
                                   "updated_at": f"{day.isoformat()}T09:15:00"})
            recorded += 1
        day -= timedelta(days=1)
    storage.save("attendance", attendance)

    # ---- Announcements -------------------------------------------------
    def readers(class_key, share):
        people = [by_username[s[0]]["id"] for s in roster[class_key]]
        return [p for p in people if rng.random() < share and p != by_username["ali.raza"]["id"]]

    all_readers = readers("9A", 0.6) + readers("10B", 0.7)
    announcements = [
        {"class_id": "all", "author": "admin", "days": -3, "pinned": True, "priority": "Important",
         "title": "Parent-Teacher Conferences next Thursday",
         "body": "Conferences run from 2:00 pm to 6:00 pm in the main hall. Booking slips go home on Monday. "
                 "Teachers: please have your gradebooks up to date by Wednesday.",
         "read_by": all_readers + [by_username["bilal.ahmed"]["id"]]},
        {"class_id": classes["9A"]["id"], "author": "sara.khan", "days": -1, "pinned": False, "priority": "Normal",
         "title": "Bring a scientific calculator tomorrow",
         "body": "We start the geometry problem set tomorrow. Please bring a scientific calculator and a ruler.",
         "read_by": readers("9A", 0.5)},
        {"class_id": classes["9A"]["id"], "author": "bilal.ahmed", "days": -6, "pinned": False, "priority": "Urgent",
         "title": "Lab safety goggles are required",
         "body": "From next week, nobody may take part in practical work without safety goggles. Spare pairs are available from the science office.",
         "read_by": readers("9A", 0.8) + [by_username["ali.raza"]["id"]]},
        {"class_id": classes["10B"]["id"], "author": "sara.khan", "days": -2, "pinned": True, "priority": "Normal",
         "title": "Extra help session: Trigonometry",
         "body": "Drop-in help session every Tuesday at lunch in Room 211. Bring the questions you found hardest - especially sine and cosine rules.",
         "read_by": readers("10B", 0.5)},
        {"class_id": classes["10B"]["id"], "author": "emily.wilson", "days": -4, "pinned": False, "priority": "Normal",
         "title": "Macbeth reading schedule",
         "body": "Please finish reading Act 2 by next Friday. Audio versions are linked in the Lesson Hub.",
         "read_by": readers("10B", 0.8)},
    ]
    storage.save("announcements", [{
        "id": storage.new_id("ann"), "class_id": a["class_id"], "title": a["title"], "body": a["body"],
        "author_id": by_username[a["author"]]["id"], "created_at": _ts(a["days"], 8, 30),
        "pinned": a["pinned"], "priority": a["priority"], "read_by": sorted(set(a["read_by"])),
    } for a in announcements])


OLD_DEMO_USERNAMES = {
    "sara.khan", "bilal.ahmed", "emily.wilson",
    "ali.raza", "ayesha.malik", "omar.farooq", "zara.hussain", "hamza.sheikh", "fatima.noor",
    "daniyal.qureshi", "maryam.iqbal", "usman.tariq", "hira.aslam", "saad.butt", "leena.joseph",
}


def reset_to_clean_slate():
    """Remove pre-seeded demo people (sara.khan, ali.raza, etc.) so users create their own accounts."""
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    storage.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    storage.save_settings(storage.DEFAULT_SETTINGS)
    for name in storage.COLLECTIONS:
        storage.save(name, [])


def ensure_data():
    """Ensure storage directories and default settings exist without seeding demo users."""
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    storage.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not (storage.DATA_DIR / "settings.json").exists():
        storage.save_settings(storage.DEFAULT_SETTINGS)
        return True
    return False



if __name__ == "__main__":
    reset_to_clean_slate()
    print("Clean slate initialized in", storage.DATA_DIR)


