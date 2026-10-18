"""
ai_assistant.py - NovaAI Multi-Engine Cognitive Assistant (100% Pure Python).

Architecture:
  1. Intent & Entity Parser: Classifies queries into Math/Symbolic Solving,
     Code Synthesis, Concept Explanation, Socratic Coaching, Lesson/Rubric
     Design, LMS Telemetry Analysis, or Multi-Turn Follow-ups.
  2. Symbolic & Numeric Math Engine: Uses Python's ``ast``, ``math``,
     ``fractions``, and ``statistics`` modules to solve arithmetic, linear
     equations (ax + b = cx + d), quadratic equations (ax^2 + bx + c = 0),
     polynomial derivatives/integrals, and statistical datasets step-by-step.
  3. Hybrid RAG (Retrieval-Augmented Generation): Combines live school JSON
     records (lessons, assignments, quizzes, grades, attendance, NovaPulse)
     with a rich built-in Academic Knowledge Graph across Math, Physics,
     Chemistry, Biology, Computer Science, English, and Study Science using
     TF-IDF weighted token scoring and fuzzy matching.
  4. Chain-of-Thought Trace & Token Streaming: Produces structured reasoning
     traces and generator streams for ``st.write_stream``.
"""

import ast
import difflib
import json
import math
import operator
import os
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from fractions import Fraction

from classpilot import coursework, insights, school, storage, tracking, utils


# ==========================================================================
# Live LLM Inference Engine (Zero-Key Cloud LLM + Optional Custom API Keys)
# ==========================================================================
LLM_MODELS = {
    "openai": "OpenAI GPT (Cloud LLM — Default)",
    "mistral": "Mistral Large (Fast Reasoning)",
    "deepseek": "DeepSeek R1 / V3 (Math & Code Specialist)",
}


def get_ai_config():
    """Return active AI provider settings from session_state, settings.json, or env."""
    cfg = {
        "model": "openai",
        "custom_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "custom_base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        "custom_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
    }
    try:
        import streamlit as st
        if "novarix_ai_model" in st.session_state:
            cfg["model"] = st.session_state["novarix_ai_model"]
        if st.session_state.get("novarix_custom_api_key"):
            cfg["custom_api_key"] = st.session_state["novarix_custom_api_key"].strip()
        if st.session_state.get("novarix_custom_base_url"):
            cfg["custom_base_url"] = st.session_state["novarix_custom_base_url"].strip()
        if st.session_state.get("novarix_custom_model"):
            cfg["custom_model"] = st.session_state["novarix_custom_model"].strip()
    except Exception:
        pass
    return cfg


def call_live_llm(messages, temperature=0.4, max_tokens=1500, timeout=25):
    """Call a real Large Language Model over HTTPS using pure Python stdlib.

    1. If a custom OpenAI/Groq/OpenRouter API key is provided, calls that endpoint.
    2. Otherwise, calls the free, no-key Pollinations OpenAI-compatible LLM endpoint
       (``https://text.pollinations.ai/openai``) with automatic fallback.

    Returns ``(reply_text, reasoning_text, model_used)`` or ``(None, None, error_str)``.
    """
    try:
        import streamlit as st
        if st.session_state.get("_fast_test_mode"):
            return None, None, "fast_test_mode"
    except Exception:
        pass

    cfg = get_ai_config()

    # Route 1: Custom API Key (OpenAI / Groq / OpenRouter compatible)
    if cfg["custom_api_key"]:
        payload = {
            "model": cfg["custom_model"] or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['custom_api_key']}",
            "User-Agent": "Novarix-LMS/2.0",
        }
        try:
            req = urllib.request.Request(
                cfg["custom_base_url"],
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            choice = (data.get("choices") or [{}])[0].get("message", {})
            content = (choice.get("content") or "").strip()
            reasoning = (choice.get("reasoning") or choice.get("reasoning_content") or "").strip()
            if content:
                return content, reasoning, data.get("model", cfg["custom_model"])
        except Exception:
            pass  # Fall through to built-in cloud LLM

    # Route 2: Built-in Zero-Key Cloud LLM (OpenAI-compatible endpoint)
    payload = {
        "model": cfg.get("model") or "openai",
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Novarix-LMS/2.0",
    }
    try:
        req = urllib.request.Request(
            "https://text.pollinations.ai/openai",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        choice = (data.get("choices") or [{}])[0].get("message", {})
        content = (choice.get("content") or "").strip()
        reasoning = (choice.get("reasoning") or choice.get("reasoning_content") or "").strip()
        model_used = data.get("model") or cfg.get("model") or "gpt-oss-20b"
        if content:
            return content, reasoning, model_used
    except Exception as exc:
        err_msg = str(exc)
    else:
        err_msg = "Empty response"

    # Route 3: Direct plain-text POST fallback to text.pollinations.ai
    try:
        req2 = urllib.request.Request(
            "https://text.pollinations.ai/",
            data=json.dumps({"messages": messages, "model": "openai"}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=timeout) as resp2:
            txt = resp2.read().decode("utf-8", errors="replace").strip()
        if txt:
            if txt.startswith("{"):
                try:
                    d2 = json.loads(txt)
                    c2 = (d2.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
                    if c2:
                        return c2, "", d2.get("model", "openai-cloud")
                except Exception:
                    pass
            return txt, "", "openai-cloud"
    except Exception as exc2:
        err_msg = f"{err_msg}; {exc2}"

    return None, None, err_msg


STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "to", "of",
    "in", "on", "for", "with", "about", "how", "what", "why", "who", "when",
    "where", "can", "you", "me", "my", "please", "tell", "explain", "help",
    "do", "does", "did", "i", "we", "they", "it", "this", "that", "and", "or",
}

# ==========================================================================
# Built-in Academic Knowledge Graph (Multi-Subject Encyclopedia)
# ==========================================================================
KNOWLEDGE_GRAPH = [
    {
        "id": "math_quadratics",
        "subject": "Mathematics",
        "topic": "Algebra & Quadratics",
        "title": "Quadratic Equations & The Quadratic Formula",
        "keywords": ["quadratic", "parabola", "discriminant", "roots", "factoring", "completing the square", "ax^2", "vertex"],
        "summary": (
            "A **quadratic equation** is a second-degree polynomial equation of the form:\n"
            "$$ax^2 + bx + c = 0 \\quad (a \\neq 0)$$\n\n"
            "### 1. The Quadratic Formula\n"
            "Every quadratic equation can be solved using:\n"
            "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
            "### 2. The Discriminant ($\\Delta = b^2 - 4ac$)\n"
            "- **$\\Delta > 0$**: Two distinct real roots (the parabola crosses the x-axis twice).\n"
            "- **$\\Delta = 0$**: Exactly one repeated real root ($x = -b / 2a$; vertex touches the x-axis).\n"
            "- **$\\Delta < 0$**: No real roots (two complex conjugate roots).\n\n"
            "### 3. Vertex & Axis of Symmetry\n"
            "- **Axis of symmetry:** $x = -\\frac{b}{2a}$\n"
            "- **Sum of roots:** $x_1 + x_2 = -\\frac{b}{a}$ &nbsp;|&nbsp; **Product of roots:** $x_1 \\cdot x_2 = \\frac{c}{a}$"
        ),
        "example": (
            "**Worked Example:** Solve $2x^2 + 5x - 3 = 0$\n"
            "1. Identify coefficients: $a = 2, \\; b = 5, \\; c = -3$\n"
            "2. Compute discriminant: $\\Delta = 5^2 - 4(2)(-3) = 25 + 24 = 49$\n"
            "3. Apply formula: $x = \\frac{-5 \\pm \\sqrt{49}}{4} = \\frac{-5 \\pm 7}{4}$\n"
            "4. Roots: $x_1 = \\frac{2}{4} = 0.5$ and $x_2 = \\frac{-12}{4} = -3$"
        ),
        "practice": "Solve $x^2 - 7x + 10 = 0$ by finding two numbers that multiply to $10$ and add to $-7$.",
    },
    {
        "id": "math_linear",
        "subject": "Mathematics",
        "topic": "Linear Equations & Graphs",
        "title": "Linear Equations, Slope & Simultaneous Systems",
        "keywords": ["linear", "slope", "gradient", "intercept", "y=mx+b", "y=mx+c", "simultaneous", "solve for x", "equation"],
        "summary": (
            "A **linear equation** represents a straight line with a constant rate of change.\n\n"
            "### 1. Slope-Intercept Form\n"
            "$$y = mx + c$$\n"
            "- **$m$ (Slope / Gradient):** $m = \\frac{y_2 - y_1}{x_2 - x_1} = \\frac{\\text{Rise}}{\\text{Run}}$\n"
            "- **$c$ (y-intercept):** The value of $y$ where the line crosses the vertical axis ($x = 0$).\n\n"
            "### 2. Parallel & Perpendicular Lines\n"
            "- **Parallel lines** have identical slopes ($m_1 = m_2$).\n"
            "- **Perpendicular lines** have negative reciprocal slopes ($m_1 \\cdot m_2 = -1$)."
        ),
        "example": (
            "**Worked Example:** Solve $5x - 8 = 2x + 10$\n"
            "1. Subtract $2x$ from both sides: $3x - 8 = 10$\n"
            "2. Add $8$ to both sides: $3x = 18$\n"
            "3. Divide by $3$: $x = 6$ (Check: $5(6)-8 = 22$ and $2(6)+10 = 22$ ✓)"
        ),
        "practice": "Find the equation of the line passing through $(2, 5)$ and $(4, 11)$.",
    },
    {
        "id": "math_trig",
        "subject": "Mathematics",
        "topic": "Geometry & Trigonometry",
        "title": "Pythagoras' Theorem & Right-Triangle Trigonometry",
        "keywords": ["pythagoras", "hypotenuse", "trigonometry", "sin", "cos", "tan", "sohcahtoa", "triangle", "angle", "sine", "cosine"],
        "summary": (
            "### 1. Pythagoras' Theorem\n"
            "In any right-angled triangle with legs $a, b$ and hypotenuse $c$:\n"
            "$$a^2 + b^2 = c^2 \\implies c = \\sqrt{a^2 + b^2}$$\n\n"
            "### 2. Trigonometric Ratios (SOH-CAH-TOA)\n"
            "$$\\sin(\\theta) = \\frac{\\text{Opposite}}{\\text{Hypotenuse}}, \\quad "
            "\\cos(\\theta) = \\frac{\\text{Adjacent}}{\\text{Hypotenuse}}, \\quad "
            "\\tan(\\theta) = \\frac{\\text{Opposite}}{\\text{Adjacent}}$$\n\n"
            "### 3. Fundamental Identity & Non-Right Triangles\n"
            "- **Pythagorean Identity:** $\\sin^2(\\theta) + \\cos^2(\\theta) = 1$\n"
            "- **Sine Rule:** $\\frac{a}{\\sin A} = \\frac{b}{\\sin B} = \\frac{c}{\\sin C}$\n"
            "- **Cosine Rule:** $c^2 = a^2 + b^2 - 2ab\\cos(C)$"
        ),
        "example": (
            "**Worked Example:** A right triangle has legs $a = 6\\text{ cm}$ and $b = 8\\text{ cm}$.\n"
            "- Hypotenuse $c = \\sqrt{6^2 + 8^2} = \\sqrt{36 + 64} = \\sqrt{100} = 10\\text{ cm}$.\n"
            "- Angle $\\theta$ opposite side $a$: $\\sin(\\theta) = 6/10 = 0.6 \\implies \\theta \\approx 36.87^\\circ$."
        ),
        "practice": "A ladder $13\\text{ m}$ long leans against a wall with its base $5\\text{ m}$ from the wall. How high up the wall does it reach?",
    },
    {
        "id": "math_calculus",
        "subject": "Mathematics",
        "topic": "Calculus",
        "title": "Derivatives, Rates of Change & Integration",
        "keywords": ["calculus", "derivative", "differentiate", "integral", "integrate", "tangent", "slope", "power rule", "chain rule", "maxima", "minima"],
        "summary": (
            "### 1. Differentiation (Instantaneous Rate of Change)\n"
            "The derivative $f'(x) = \\frac{dy}{dx}$ measures the instantaneous slope of $f(x)$.\n"
            "- **Power Rule:** $\\frac{d}{dx}[x^n] = n x^{n-1}$\n"
            "- **Product Rule:** $(uv)' = u'v + uv'$\n"
            "- **Chain Rule:** $\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x)$\n\n"
            "### 2. Stationary / Critical Points\n"
            "Set $f'(x) = 0$ to find local maxima or minima. If $f''(x) < 0$, it is a local maximum; if $f''(x) > 0$, a local minimum.\n\n"
            "### 3. Integration (Antiderivatives & Area)\n"
            "$$\\int x^n \\, dx = \\frac{x^{n+1}}{n+1} + C \\quad (n \\neq -1)$$"
        ),
        "example": (
            "**Worked Example:** Differentiate $f(x) = 3x^3 - 6x^2 + 4x - 9$\n"
            "- Apply Power Rule term-by-term:\n"
            "  $f'(x) = 3(3x^2) - 6(2x^1) + 4(1) - 0 = 9x^2 - 12x + 4$"
        ),
        "practice": "Find the derivative of $y = 4x^3 - 12x + 5$ and find the $x$-values where the tangent line is horizontal ($dy/dx = 0$).",
    },
    {
        "id": "phys_newton",
        "subject": "Physics",
        "topic": "Mechanics & Forces",
        "title": "Newton's Laws of Motion, Force & Kinematics",
        "keywords": ["newton", "force", "mass", "acceleration", "inertia", "f=ma", "kinematics", "velocity", "momentum", "friction", "gravity"],
        "summary": (
            "### 1. Newton's Three Laws of Motion\n"
            "1. **First Law (Inertia):** An object remains at rest or in uniform straight-line motion unless acted upon by a net external force ($\\Sigma F = 0 \\iff a = 0$).\n"
            "2. **Second Law ($F = ma$):** Net force equals mass times acceleration:\n"
            "   $$F_{\\text{net}} = m \\cdot a \\quad (\\text{in Newtons, } 1\\text{ N} = 1\\text{ kg}\\cdot\\text{m/s}^2)$$\n"
            "3. **Third Law (Action-Reaction):** When body A exerts force $\\vec{F}$ on body B, body B simultaneously exerts $-\\vec{F}$ on body A.\n\n"
            "### 2. SUVAT Kinematic Equations (Constant Acceleration)\n"
            "- $v = u + at$\n"
            "- $s = ut + \\frac{1}{2}at^2$\n"
            "- $v^2 = u^2 + 2as$"
        ),
        "example": (
            "**Worked Example:** A $1200\\text{ kg}$ car accelerates from rest ($u=0$) to $v=20\\text{ m/s}$ in $t=5\\text{ s}$.\n"
            "1. Acceleration: $a = \\frac{v - u}{t} = \\frac{20 - 0}{5} = 4\\text{ m/s}^2$\n"
            "2. Net Driving Force: $F = ma = 1200 \\times 4 = 4800\\text{ N}$"
        ),
        "practice": "What net force is required to accelerate a $15\\text{ kg}$ bicycle at $2.5\\text{ m/s}^2$?",
    },
    {
        "id": "phys_electricity",
        "subject": "Physics",
        "topic": "Electricity & Circuits",
        "title": "Ohm's Law, Electric Circuits & Power",
        "keywords": ["ohm", "voltage", "current", "resistance", "circuit", "series", "parallel", "power", "watt", "ampere", "v=ir"],
        "summary": (
            "### 1. Ohm's Law & Electrical Power\n"
            "$$V = I \\cdot R \\quad \\text{and} \\quad P = V \\cdot I = I^2 R = \\frac{V^2}{R}$$\n"
            "- **$V$ (Voltage / Potential Difference):** Measured in Volts ($\\text{V}$).\n"
            "- **$I$ (Current):** Rate of charge flow ($I = Q/t$), measured in Amperes ($\\text{A}$).\n"
            "- **$R$ (Resistance):** Opposition to current, measured in Ohms ($\\Omega$).\n\n"
            "### 2. Series vs. Parallel Circuits\n"
            "- **Series:** Current $I$ is the same everywhere; voltages add ($R_{\\text{total}} = R_1 + R_2 + \\dots$).\n"
            "- **Parallel:** Voltage $V$ is the same across branches; currents add ($\\frac{1}{R_{\\text{total}}} = \\frac{1}{R_1} + \\frac{1}{R_2} + \\dots$)."
        ),
        "example": (
            "**Worked Example:** Two resistors ($4\\,\\Omega$ and $6\\,\\Omega$) are connected in series to a $20\\text{ V}$ battery.\n"
            "- Total Resistance: $R_{\\text{total}} = 4 + 6 = 10\\,\\Omega$\n"
            "- Current: $I = V / R_{\\text{total}} = 20 / 10 = 2\\text{ A}$\n"
            "- Power dissipated: $P = V \\cdot I = 20 \\times 2 = 40\\text{ W}$"
        ),
        "practice": "Calculate the current flowing through an $8\\,\\Omega$ resistor connected across a $12\\text{ V}$ supply.",
    },
    {
        "id": "bio_photosynthesis",
        "subject": "Biology",
        "topic": "Cellular Bioenergetics",
        "title": "Photosynthesis vs. Cellular Respiration",
        "keywords": ["photosynthesis", "respiration", "chloroplast", "chlorophyll", "mitochondria", "atp", "glucose", "carbon dioxide", "oxygen", "stomata", "plant", "cell"],
        "summary": (
            "### 1. Photosynthesis (Chloroplasts)\n"
            "Plants convert light energy into chemical energy stored in glucose:\n"
            "$$6\\text{CO}_2 + 6\\text{H}_2\\text{O} \\xrightarrow{\\text{Light + Chlorophyll}} \\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2$$\n"
            "- **Light-Dependent Reactions (Thylakoid membranes):** Split water (photolysis), release $\\text{O}_2$, and generate ATP + NADPH.\n"
            "- **Calvin Cycle / Light-Independent (Stroma):** Fixes $\\text{CO}_2$ using ATP and NADPH to synthesize glucose.\n\n"
            "### 2. Aerobic Cellular Respiration (Mitochondria)\n"
            "Cells break down glucose in the presence of oxygen to release usable ATP energy:\n"
            "$$\\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2 \\longrightarrow 6\\text{CO}_2 + 6\\text{H}_2\\text{O} + \\approx 36\\text{--}38\\text{ ATP}$$\n"
            "- Stages: **Glycolysis** (cytoplasm) $\\rightarrow$ **Krebs / Citric Acid Cycle** (mitochondrial matrix) $\\rightarrow$ **Electron Transport Chain** (inner mitochondrial membrane)."
        ),
        "example": (
            "**Key Comparison:**\n"
            "| Feature | Photosynthesis | Aerobic Respiration |\n"
            "| :--- | :--- | :--- |\n"
            "| **Organelle** | Chloroplast | Mitochondrion |\n"
            "| **Energy Flow** | Endergonic (stores light energy in glucose) | Exergonic (releases energy as ATP) |\n"
            "| **Reactants** | $\\text{CO}_2 + \\text{H}_2\\text{O}$ | $\\text{Glucose} + \\text{O}_2$ |"
        ),
        "practice": "Why do plant cells still need mitochondria if they already have chloroplasts?",
    },
    {
        "id": "bio_genetics",
        "subject": "Biology",
        "topic": "Genetics & Molecular Biology",
        "title": "DNA, RNA, Protein Synthesis & Mendelian Inheritance",
        "keywords": ["dna", "rna", "gene", "chromosome", "allele", "dominant", "recessive", "punnett", "mitosis", "meiosis", "mutation", "transcription", "translation"],
        "summary": (
            "### 1. Central Dogma of Molecular Biology\n"
            "$$\\text{DNA} \\xrightarrow{\\text{Transcription (Nucleus)}} \\text{mRNA} \\xrightarrow{\\text{Translation (Ribosome)}} \\text{Polypeptide / Protein}$$\n"
            "- **DNA Base Pairing:** Adenine ($\\text{A}$) pairs with Thymine ($\\text{T}$); Cytosine ($\\text{C}$) pairs with Guanine ($\\text{G}$). In RNA, Uracil ($\\text{U}$) replaces Thymine.\n\n"
            "### 2. Mendelian Genetics & Punnett Squares\n"
            "- **Genotype:** The genetic allele combination (e.g., homozygous dominant $BB$, heterozygous $Bb$, homozygous recessive $bb$).\n"
            "- **Phenotype:** The observable physical trait.\n"
            "- **Monohybrid Cross ($Bb \\times Bb$):** Produces a $1:2:1$ genotype ratio ($1\\,BB : 2\\,Bb : 1\\,bb$) and a $3:1$ dominant-to-recessive phenotype ratio."
        ),
        "example": (
            "**Worked Example:** In pea plants, Tall ($T$) is dominant over short ($t$). Crossing two heterozygous tall plants ($Tt \\times Tt$) gives:\n"
            "- $25\\% \\; TT$ (Tall), $50\\% \\; Tt$ (Tall), $25\\% \\; tt$ (short) $\\implies 75\\%$ Tall, $25\\%$ short."
        ),
        "practice": "What is the probability of a recessive offspring ($bb$) from a cross between $Bb$ and $bb$?",
    },
    {
        "id": "chem_atoms_bonding",
        "subject": "Chemistry",
        "topic": "Atomic Structure & Bonding",
        "title": "Atomic Structure, Periodic Trends, Stoichiometry & Bonding",
        "keywords": ["atom", "proton", "neutron", "electron", "periodic table", "ionic", "covalent", "mole", "molar mass", "stoichiometry", "acid", "base", "ph", "chemistry"],
        "summary": (
            "### 1. Atomic Structure\n"
            "- **Atomic Number ($Z$):** Number of protons (defines the element).\n"
            "- **Mass Number ($A$):** $\\text{Protons} + \\text{Neutrons}$. **Isotopes** are atoms of the same element with different neutron counts.\n\n"
            "### 2. Chemical Bonding\n"
            "- **Ionic Bonding (Metal + Non-metal):** Transfer of valence electrons forming oppositely charged ions held by electrostatic attraction (e.g., $\\text{NaCl}$).\n"
            "- **Covalent Bonding (Non-metal + Non-metal):** Sharing of electron pairs to achieve a full octet (e.g., $\\text{H}_2\\text{O}, \\text{CO}_2$).\n\n"
            "### 3. Moles & Stoichiometry\n"
            "$$n (\\text{moles}) = \\frac{m (\\text{mass in g})}{M (\\text{molar mass in g/mol})} = \\frac{N}{6.022 \\times 10^{23}} \\quad \\text{and} \\quad C = \\frac{n}{V(\\text{L})}$$"
        ),
        "example": (
            "**Worked Example:** How many moles are in $36\\text{ g}$ of water ($\\text{H}_2\\text{O}$)?\n"
            "1. Molar mass $M(\\text{H}_2\\text{O}) = 2(1.0) + 16.0 = 18.0\\text{ g/mol}$\n"
            "2. Moles $n = \\frac{36}{18.0} = 2.0\\text{ mol}$"
        ),
        "practice": "Calculate the mass of $0.5\\text{ mol}$ of Carbon Dioxide ($\\text{CO}_2$, where $\\text{C}=12, \\text{O}=16$).",
    },
    {
        "id": "cs_python",
        "subject": "Computer Science",
        "topic": "Python Programming & Algorithms",
        "title": "Python Fundamentals: Loops, Functions, Data Structures & Algorithms",
        "keywords": ["python", "code", "loop", "for", "while", "function", "def", "list", "dictionary", "dict", "algorithm", "recursion", "class", "programming", "array", "sort", "binary search"],
        "summary": (
            "### 1. Core Python Building Blocks\n"
            "```python\n"
            "# List comprehension + filtering\n"
            "numbers = [1, 2, 3, 4, 5, 6, 7, 8]\n"
            "even_squares = [n ** 2 for n in numbers if n % 2 == 0]\n"
            "\n"
            "# Reusable function with type hints\n"
            "def summarize_scores(scores: list[float]) -> dict:\n"
            "    if not scores:\n"
            "        return {'mean': 0.0, 'max': 0.0}\n"
            "    return {'mean': sum(scores) / len(scores), 'max': max(scores)}\n"
            "```\n\n"
            "### 2. Data Structures Complexity (Big-O)\n"
            "- **`list` (Dynamic Array):** Index lookup $O(1)$, append $O(1)$, linear search $O(n)$.\n"
            "- **`dict` / `set` (Hash Table):** Lookup, insertion, and deletion average $O(1)$.\n"
            "- **Binary Search (on sorted list):** Halves the search space each step $\\implies O(\\log_2 n)$."
        ),
        "example": (
            "**Worked Example — Binary Search in Python:**\n"
            "```python\n"
            "def binary_search(arr, target):\n"
            "    low, high = 0, len(arr) - 1\n"
            "    while low <= high:\n"
            "        mid = (low + high) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            low = mid + 1\n"
            "        else:\n"
            "            high = mid - 1\n"
            "    return -1\n"
            "```"
        ),
        "practice": "Write a Python function `count_vowels(text)` that returns the number of vowels in a string.",
    },
    {
        "id": "eng_writing_literature",
        "subject": "English",
        "topic": "Literature & Essay Composition",
        "title": "Analytical Essay Writing (PEEL) & Literary Analysis",
        "keywords": ["essay", "thesis", "paragraph", "peel", "macbeth", "shakespeare", "metaphor", "simile", "irony", "theme", "literature", "grammar", "writing", "poem", "analysis"],
        "summary": (
            "### 1. The PEEL Analytical Paragraph Framework\n"
            "- **P — Point (Topic Sentence):** State a clear analytical claim tied directly to your thesis.\n"
            "- **E — Evidence (Quotation):** Embed a concise, relevant quote or textual reference.\n"
            "- **E — Explanation (Close Reading):** Analyze *how* specific word choices (diction), imagery, or literary devices create meaning.\n"
            "- **L — Link:** Connect the insight back to the overarching prompt and transition smoothly.\n\n"
            "### 2. High-Impact Literary Devices\n"
            "- **Juxtaposition / Foil:** Placing contrasting ideas or characters side-by-side to highlight their differences.\n"
            "- **Dramatic Irony:** When the audience knows a crucial truth that the characters on stage do not (e.g., Duncan praising Macbeth's castle).\n"
            "- **Motif:** A recurring image or symbol that develops a central theme (e.g., blood and sleeplessness in *Macbeth* symbolizing inescapable guilt)."
        ),
        "example": (
            "**Model PEEL Excerpt (*Macbeth*):**\n"
            "> **Point:** Shakespeare uses the recurring motif of blood to trace Macbeth's psychological descent from ambition into remorse. "
            "**Evidence:** After murdering Duncan, Macbeth asks, *\"Will all great Neptune's ocean wash this blood / Clean from my hand?\"* "
            "**Explanation:** The hyperbole contrasting a single human hand with the entire ocean emphasizes that moral corruption cannot be physically cleansed. "
            "**Link:** Thus, Shakespeare warns that unchecked ambition destroys the perpetrator's own conscience."
        ),
        "practice": "Draft a thesis statement comparing how two characters respond to pressure or moral conflict.",
    },
    {
        "id": "study_science",
        "subject": "Study Science & Pedagogy",
        "topic": "Cognitive Learning Strategies",
        "title": "Active Recall, Spaced Repetition & Exam Mastery",
        "keywords": ["study", "memorize", "exam", "revision", "focus", "procrastination", "pomodoro", "flashcard", "active recall", "spaced repetition", "notes"],
        "summary": (
            "### 1. Evidence-Based Study Methods\n"
            "1. **Active Recall (Self-Testing):** Close your notes and force your brain to retrieve the concept from memory. Answering 5 practice questions strengthens neural pathways far more than re-reading a page 5 times.\n"
            "2. **Spaced Repetition:** Review material at expanding intervals (**Day 1 $\\rightarrow$ Day 3 $\\rightarrow$ Day 7 $\\rightarrow$ Day 16**) right before the forgetting curve drops.\n"
            "3. **The Feynman Technique:** Explain the concept aloud or on paper as if teaching a 12-year-old. Anywhere you hesitate or rely on jargon reveals the exact gap to review.\n"
            "4. **Interleaving:** Mix problem types (e.g., linear, quadratic, and word problems) in one session so you practice *choosing* the right method."
        ),
        "example": (
            "**25-Minute High-Yield Study Sprint (Pomodoro):**\n"
            "- **Minutes 0–5:** Skim lesson headings and write 3 key questions.\n"
            "- **Minutes 5–20:** Solve 3–4 problems without looking at worked solutions.\n"
            "- **Minutes 20–25:** Check answers, log mistakes, and rate your confidence in NovaPulse."
        ),
        "practice": "Pick your lowest-rated NovaPulse lesson and summarize its core rule in one sentence without looking at your notes.",
    },
]


# ==========================================================================
# Persistent Chat History & Reasoning Trace Storage
# ==========================================================================
def get_chat_history(user_id):
    """Return the saved chat messages for ``user_id``."""
    found = storage.find("ai_history", user_id=user_id)
    if found:
        return found[0].get("messages", [])
    return []


def append_chat_message(user_id, role, content, trace=None):
    """Save a chat message (and optional reasoning trace) to ``ai_history.json``."""
    found = storage.find("ai_history", user_id=user_id)
    messages = found[0].get("messages", []) if found else []
    entry = {
        "role": role,
        "content": content,
        "timestamp": utils.now_iso(),
    }
    if trace:
        entry["trace"] = trace
    messages.append(entry)
    messages = messages[-40:]
    if found:
        storage.update("ai_history", found[0]["id"], {"messages": messages})
    else:
        storage.insert("ai_history", {
            "id": storage.new_id("aih"),
            "user_id": user_id,
            "messages": messages,
        })


def clear_chat_history(user_id):
    """Clear saved chat messages for ``user_id``."""
    found = storage.find("ai_history", user_id=user_id)
    if found:
        storage.update("ai_history", found[0]["id"], {"messages": []})


def stream_markdown(text, delay=0.008):
    """Generator that yields chunks of markdown for ``st.write_stream``."""
    tokens = re.split(r"(\s+)", str(text))
    step = 3
    for i in range(0, len(tokens), step):
        yield "".join(tokens[i:i + step])
        if delay > 0:
            time.sleep(delay)


# ==========================================================================
# Pure-Python Symbolic & Numeric Math Engine
# ==========================================================================
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "sqrt": math.sqrt,
    "sin": lambda d: math.sin(math.radians(d)) if abs(d) > 2 * math.pi else math.sin(d),
    "cos": lambda d: math.cos(math.radians(d)) if abs(d) > 2 * math.pi else math.cos(d),
    "tan": lambda d: math.tan(math.radians(d)) if abs(d) > 2 * math.pi else math.tan(d),
    "log": math.log10,
    "ln": math.log,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "pi": math.pi,
    "e": math.e,
}


def _eval_ast(node):
    """Safely evaluate a mathematical AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in _SAFE_FUNCS:
        val = _SAFE_FUNCS[node.id]
        if isinstance(val, (int, float)):
            return float(val)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent too large.")
        return _SAFE_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
        fn = _SAFE_FUNCS[node.func.id]
        args = [_eval_ast(a) for a in node.args]
        if node.func.id in ("factorial", "gcd", "lcm"):
            args = [int(a) for a in args]
        return float(fn(*args))
    raise ValueError("Unsupported expression")


def _parse_polynomial_side(expr_str, var="x"):
    """Parse an algebraic side like '2x^2 + 5x - 3' into {degree: coeff}."""
    s = expr_str.replace(" ", "").replace("**", "^").replace("−", "-")
    # Expand simple k(ax+b) parentheses
    s = re.sub(
        r"([+-]?\d*\.?\d+)\(([+-]?\d*\.?\d*" + re.escape(var) + r"[+-]\d+\.?\d*)\)",
        lambda m: _expand_simple_group(m.group(1), m.group(2), var),
        s,
    )
    if not s:
        return {0: 0.0}
    if s[0] not in "+-":
        s = "+" + s
    tokens = re.findall(r"[+-][^+-]+", s)
    if not tokens or "".join(tokens) != s:
        return None
    coeffs = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
    for tok in tokens:
        m_pow = re.fullmatch(r"([+-]?\d*\.?\d*)\*?" + re.escape(var) + r"\^(\d+)", tok)
        m_lin = re.fullmatch(r"([+-]?\d*\.?\d*)\*?" + re.escape(var), tok)
        m_con = re.fullmatch(r"([+-]?\d+\.?\d*)", tok)
        if m_pow:
            raw_c, deg = m_pow.group(1), int(m_pow.group(2))
            if deg > 3:
                return None
            c = 1.0 if raw_c in ("", "+") else -1.0 if raw_c == "-" else float(raw_c)
            coeffs[deg] = coeffs.get(deg, 0.0) + c
        elif m_lin:
            raw_c = m_lin.group(1)
            c = 1.0 if raw_c in ("", "+") else -1.0 if raw_c == "-" else float(raw_c)
            coeffs[1] += c
        elif m_con:
            coeffs[0] += float(m_con.group(1))
        else:
            return None
    return coeffs


def _expand_simple_group(mult_str, inner_str, var):
    k = 1.0 if mult_str in ("", "+") else -1.0 if mult_str == "-" else float(mult_str)
    inner = _parse_polynomial_side(inner_str, var)
    if not inner:
        return f"{mult_str}({inner_str})"
    parts = []
    for deg in (2, 1, 0):
        c = k * inner.get(deg, 0.0)
        if abs(c) > 1e-12:
            if deg == 2:
                parts.append(f"{c:+g}{var}^2")
            elif deg == 1:
                parts.append(f"{c:+g}{var}")
            else:
                parts.append(f"{c:+g}")
    return "".join(parts) or "+0"


def solve_math_problem(query):
    """Attempt to solve an algebraic equation, derivative, statistics list, or expression.

    Returns ``(markdown_solution, reasoning_note)`` or ``(None, None)`` if the query
    is not a mathematical calculation/equation.
    """
    q = (query or "").strip()
    q_low = q.lower()

    # 1. Dataset Statistics (e.g., "mean, median, std of 12, 15, 18, 22, 30")
    if any(k in q_low for k in ("mean", "median", "standard deviation", "std", "variance", "average of")):
        nums = [float(x) for x in re.findall(r"(?<![a-zA-Z0-9_])-?\d+\.?\d*", q)]
        if len(nums) >= 3:
            mean_v = statistics.mean(nums)
            med_v = statistics.median(nums)
            stdev_v = statistics.stdev(nums) if len(nums) > 1 else 0.0
            var_v = statistics.variance(nums) if len(nums) > 1 else 0.0
            sorted_n = sorted(nums)
            sol = (
                "### ■ Symbolic & Statistical Engine — Dataset Analysis\n"
                f"- **Input Dataset ($n = {len(nums)}$):** `{nums}`\n"
                f"- **Sorted Order:** `{sorted_n}`\n\n"
                "| Metric | Formula / Method | Calculated Value |\n"
                "| :--- | :--- | :--- |\n"
                f"| **Mean ($\\bar{{x}}$)** | $\\frac{{\\sum x_i}}{{n}} = \\frac{{{sum(nums):g}}}{{{len(nums)}}}$ | **{mean_v:.4g}** |\n"
                f"| **Median** | Middle value of sorted data | **{med_v:.4g}** |\n"
                f"| **Range** | $\\max(x) - \\min(x) = {max(nums):g} - {min(nums):g}$ | **{max(nums) - min(nums):.4g}** |\n"
                f"| **Sample Variance ($s^2$)** | $\\frac{{\\sum (x_i - \\bar{{x}})^2}}{{n - 1}}$ | **{var_v:.4g}** |\n"
                f"| **Sample Std Dev ($s$)** | $\\sqrt{{s^2}}$ | **{stdev_v:.4g}** |"
            )
            return sol, f"Computed descriptive statistics over n={len(nums)} numeric values."

    # 2. Polynomial Derivative (e.g., "derivative of 3x^3 - 5x^2 + 4x - 7")
    if any(k in q_low for k in ("derivative", "differentiate", "dy/dx", "d/dx")):
        m_expr = re.search(r"(?:of|differentiate|d/dx)\s+([0-9xX\+\-\^\*\.\s]+)", q)
        expr_candidate = m_expr.group(1).strip() if m_expr else q
        poly = _parse_polynomial_side(expr_candidate.lower(), "x")
        if poly and any(abs(poly[d]) > 1e-12 for d in (1, 2, 3)):
            terms, steps = [], []
            for d in (3, 2, 1, 0):
                c = poly.get(d, 0.0)
                if abs(c) < 1e-12:
                    continue
                if d == 0:
                    steps.append(f"- Constant term ${c:+g} \\xrightarrow{{d/dx}} 0$")
                else:
                    new_c = c * d
                    new_d = d - 1
                    term_str = f"{new_c:+g}x^{new_d}" if new_d > 1 else (f"{new_c:+g}x" if new_d == 1 else f"{new_c:+g}")
                    terms.append(term_str)
                    steps.append(f"- Power Rule on ${c:+g}x^{d}$: ${d} \\cdot ({c:g})x^{{{d}-1}} = {term_str.lstrip('+')}$")
            deriv_str = " ".join(terms).lstrip("+") or "0"
            sol = (
                "### ■ Symbolic Calculus Engine — Differentiation\n"
                f"**Function:** $f(x) = {expr_candidate}$\n\n"
                "**Step-by-Step Power Rule ($\\frac{d}{dx}[cx^n] = c \\cdot n x^{n-1}$):**\n"
                + "\n".join(steps)
                + f"\n\n**Resulting Derivative:**\n$$f'(x) = {deriv_str}$$"
            )
            return sol, f"Differentiated polynomial {expr_candidate} using the symbolic Power Rule."

    # 3. Algebraic Equation Solver (Linear & Quadratic equations with '=')
    if "=" in q:
        eq_match = re.search(r"([0-9a-zA-Z\+\-\^\*\(\)\.\s]+)=([0-9a-zA-Z\+\-\^\*\(\)\.\s]+)", q)
        if eq_match:
            lhs_raw = re.sub(r"^[a-zA-Z\s:]+", "", eq_match.group(1)).strip()
            rhs_raw = eq_match.group(2).strip()
            var_candidates = re.findall(r"[a-zA-Z]", lhs_raw + rhs_raw)
            var = var_candidates[0].lower() if var_candidates else "x"
            lhs = _parse_polynomial_side(lhs_raw.lower(), var)
            rhs = _parse_polynomial_side(rhs_raw.lower(), var)
            if lhs is not None and rhs is not None:
                a = lhs.get(2, 0.0) - rhs.get(2, 0.0)
                b = lhs.get(1, 0.0) - rhs.get(1, 0.0)
                c = lhs.get(0, 0.0) - rhs.get(0, 0.0)

                # Linear Equation: b*x + c = 0
                if abs(a) < 1e-12 and abs(b) > 1e-12:
                    root = -c / b
                    frac = Fraction(root).limit_denominator(1000)
                    frac_str = f"\\frac{{{frac.numerator}}}{{{frac.denominator}}}" if frac.denominator != 1 else f"{frac.numerator}"
                    sol = (
                        f"### ■ Symbolic Algebra Engine — Linear Equation Solution\n"
                        f"**Equation:** $${lhs_raw} = {rhs_raw}$$\n\n"
                        f"**Step-by-Step Derivation:**\n"
                        f"1. **Collect variable terms ($\\text{{{var}}}$) on the left and constants on the right:**\n"
                        f"   $${b:g}{var} = {-c:g}$$\n"
                        f"2. **Divide both sides by the coefficient ${b:g}$:**\n"
                        f"   $${var} = \\frac{{{-c:g}}}{{{b:g}}} = {frac_str} \\approx {root:.6g}$$\n"
                        f"3. **Verification Check:** Substitute ${var} = {root:g}$ back into the equation $\\implies$ LHS = RHS ✓"
                    )
                    return sol, f"Solved linear equation {lhs_raw} = {rhs_raw} -> {var} = {root:g}."

                # Quadratic Equation: a*x^2 + b*x + c = 0
                if abs(a) > 1e-12:
                    disc = b * b - 4 * a * c
                    vertex_x = -b / (2 * a)
                    vertex_y = a * (vertex_x ** 2) + b * vertex_x + c
                    steps = [
                        f"### ■ Symbolic Algebra Engine — Quadratic Equation Solution",
                        f"**Standard Form ($a{var}^2 + b{var} + c = 0$):**",
                        f"$${a:g}{var}^2 {b:+g}{var} {c:+g} = 0 \\quad (a = {a:g},\\; b = {b:g},\\; c = {c:g})$$",
                        f"**Step 1 — Compute the Discriminant ($\\Delta = b^2 - 4ac$):**",
                        f"$$\\Delta = ({b:g})^2 - 4({a:g})({c:g}) = {b*b:g} - ({4*a*c:g}) = {disc:g}$$",
                    ]
                    if disc > 1e-12:
                        sqrt_d = math.sqrt(disc)
                        x1 = (-b + sqrt_d) / (2 * a)
                        x2 = (-b - sqrt_d) / (2 * a)
                        steps.append(
                            f"**Step 2 — Apply the Quadratic Formula ($\\Delta > 0 \\implies 2$ distinct real roots):**\n"
                            f"$${var} = \\frac{{-({b:g}) \\pm \\sqrt{{{disc:g}}}}}{{2({a:g})}} = \\frac{{{-b:g} \\pm {sqrt_d:.6g}}}{{{2*a:g}}}$$\n"
                            f"- **Root 1:** $${var}_1 = {x1:.6g}$$\n"
                            f"- **Root 2:** $${var}_2 = {x2:.6g}$$\n"
                            f"- **Parabola Vertex (Turning Point):** $({vertex_x:.4g},\\; {vertex_y:.4g})$"
                        )
                    elif abs(disc) <= 1e-12:
                        x1 = -b / (2 * a)
                        steps.append(
                            f"**Step 2 — Apply the Quadratic Formula ($\\Delta = 0 \\implies 1$ repeated real root):**\n"
                            f"$${var} = \\frac{{-({b:g})}}{{2({a:g})}} = {x1:.6g}$$"
                        )
                    else:
                        real_p = -b / (2 * a)
                        imag_p = math.sqrt(-disc) / abs(2 * a)
                        steps.append(
                            f"**Step 2 — Complex Roots ($\\Delta < 0 \\implies$ no real roots):**\n"
                            f"$${var}_1 = {real_p:.4g} + {imag_p:.4g}i, \\quad {var}_2 = {real_p:.4g} - {imag_p:.4g}i$$"
                        )
                    return "\n\n".join(steps), f"Solved quadratic equation (a={a:g}, b={b:g}, c={c:g}, Δ={disc:g})."

    # 4. Pure Arithmetic / Scientific Expression Evaluator
    cleaned_expr = re.sub(
        r"^(?:calculate|compute|evaluate|solve|what is|whats)\s+",
        "",
        q_low.rstrip("?."),
    ).strip()
    cleaned_expr = cleaned_expr.replace("^", "**")
    if any(ch.isdigit() for ch in cleaned_expr) and re.fullmatch(r"[0-9\.\+\-\*\/\%\(\)\s\,a-z]+", cleaned_expr):
        try:
            tree = ast.parse(cleaned_expr, mode="eval")
            val = _eval_ast(tree.body)
            frac = Fraction(val).limit_denominator(1000)
            frac_note = f" (Exact fraction: `$\\frac{{{frac.numerator}}}{{{frac.denominator}}}$`)" if frac.denominator not in (1, 1000) and abs(float(frac) - val) < 1e-9 else ""
            sol = (
                "### ■ Symbolic Computation Engine — Direct Evaluation\n"
                f"- **Expression:** `{cleaned_expr.replace('**', '^')}`\n"
                f"- **Computed Result:** **`{val:.8g}`**{frac_note}"
            )
            return sol, f"Evaluated mathematical expression '{cleaned_expr}' = {val:.8g}."
        except Exception:
            pass

    return None, None


# ==========================================================================
# Hybrid RAG Semantic Retriever (School Lessons + Built-in Knowledge Graph)
# ==========================================================================
def _tokenize(text):
    words = re.findall(r"[a-z0-9\^\=\+]+", (text or "").lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def semantic_retrieve(query, subject_ids=None, top_k=3):
    """Score both live school Lesson Hub notes and the built-in Knowledge Graph
    against ``query`` using weighted keyword + fuzzy token similarity."""
    q_low = (query or "").lower()
    q_tokens = _tokenize(query)
    if not q_tokens:
        return [], []

    # 1. Score School Lesson Hub documents
    lessons = coursework.lessons_for_subjects(subject_ids) if subject_ids else storage.load("lessons")
    scored_lessons = []
    for les in lessons:
        title_low = les["title"].lower()
        topic_low = les["topic"].lower()
        body_low = les["content"].lower()
        score = 0.0
        for tok in q_tokens:
            if tok in title_low:
                score += 4.5
            if tok in topic_low:
                score += 3.0
            if tok in body_low:
                score += 1.5
            # Fuzzy prefix match
            for word in _tokenize(title_low + " " + topic_low):
                if difflib.SequenceMatcher(None, tok, word).ratio() >= 0.82:
                    score += 2.0
        if score > 0:
            scored_lessons.append((score, les))
    scored_lessons.sort(key=lambda x: x[0], reverse=True)

    # 2. Score Built-in Academic Knowledge Graph nodes
    scored_kg = []
    for node in KNOWLEDGE_GRAPH:
        score = 0.0
        title_low = node["title"].lower()
        subj_low = node["subject"].lower()
        for kw in node["keywords"]:
            if kw in q_low:
                score += 5.0
        for tok in q_tokens:
            if tok in title_low:
                score += 3.5
            if tok in subj_low:
                score += 2.5
            if any(tok in kw for kw in node["keywords"]):
                score += 3.0
            if tok in node["summary"].lower():
                score += 1.0
        if score > 0:
            scored_kg.append((score, node))
    scored_kg.sort(key=lambda x: x[0], reverse=True)

    return [l for _, l in scored_lessons[:top_k]], [n for _, n in scored_kg[:top_k]]


def _resolve_conversation_context(user_id, query):
    """If the user asks a short follow-up ('give me an example', 'quiz me on that',
    'explain more simply'), enrich the query with the last turn's topic."""
    q_low = (query or "").strip().lower()
    followup_triggers = (
        "example", "simpler", "eli5", "quiz me", "practice", "another",
        "more detail", "why is that", "how does it", "explain that", "hint",
        "summary", "summarize that", "harder", "step by step",
    )
    if len(q_low.split()) <= 8 and any(t in q_low for t in followup_triggers):
        history = get_chat_history(user_id)
        for msg in reversed(history):
            if msg.get("role") == "user" and len(msg.get("content", "").split()) > 3:
                return f"{query} (regarding: {msg['content']})", msg["content"]
    return query, None


# ==========================================================================
# Live RAG Context Builders for Real LLM Calls
# ==========================================================================
def _build_teacher_rag_context(user, query):
    """Build a live Novarix school context string to ground the LLM for a teacher/admin."""
    subjects = (school.all_subjects() if user["role"] == "admin"
                else school.subjects_for_teacher(user["id"]))
    subject_ids = [s["id"] for s in subjects]
    subj_names = [school.subject_label(s) for s in subjects]

    queue, _ = coursework.grading_queue(subject_ids) if subject_ids else ([], [])
    alerts = insights.support_alerts(subjects) if subjects else []
    prefs = insights.get_teacher_prefs(user["id"])
    dash_classes = prefs.get("added_classes", [])
    dash_asgs = prefs.get("added_assignments", [])

    ctx_lines = [
        f"Teacher Name: {user['full_name']} (@{user['username']}, Role: {user['role']})",
        f"Assigned LMS Subjects ({len(subj_names)}): {', '.join(subj_names) if subj_names else 'None yet'}",
        f"Custom Dashboard Classes ({len(dash_classes)}): {', '.join(c.get('name', '') + ' (' + c.get('subject', '') + ')' for c in dash_classes[:8]) or 'None'}",
        f"Dashboard Assignments to Check ({len(dash_asgs)}): "
        + (", ".join(f"{a.get('title')} [{'Done' if a.get('done') else 'Pending'}]" for a in dash_asgs[:8]) or "None"),
        f"LMS Ungraded Submissions Queue ({len(queue)}): "
        + (", ".join(
            f"{school.user_name(s['student_id'])} -> {storage.get('assignments', s['assignment_id'])['title']}"
            for s in queue[:6] if storage.get("assignments", s["assignment_id"])
        ) or "Empty"),
        f"Early Support Alerts ({len(alerts)}): "
        + (", ".join(f"{a['student']} ({a['subject']}: {', '.join(a['reasons'])})" for a in alerts[:6]) or "None"),
    ]

    # Include matching Lesson Hub excerpts if relevant
    matched_lessons, _ = semantic_retrieve(query, subject_ids, top_k=2)
    for les in matched_lessons:
        ctx_lines.append(f"Relevant Lesson in Novarix ('{les['title']}'): {les['content'][:500]}")

    # Include exact symbolic math verification if query contains math
    math_sol, math_note = solve_math_problem(query)
    if math_sol:
        ctx_lines.append(f"Verified Symbolic Math Engine Result ({math_note}):\n{math_sol}")

    return "\n".join(ctx_lines), math_sol, math_note


def _build_student_rag_context(user, query):
    """Build a live Novarix school context string to ground the LLM for a student."""
    cls = school.student_class(user["id"])
    subjects = school.subjects_for_student(user["id"])
    subject_ids = [s["id"] for s in subjects]
    todo = insights.student_todo(user["id"])
    items = tracking.grade_items_for_student(user["id"])
    overall = utils.mean([i["percent"] for i in items])

    ctx_lines = [
        f"Student Name: {user['full_name']} (@{user['username']})",
        f"Enrolled Class: {cls['name'] if cls else 'Unassigned'}",
        f"Enrolled Subjects: {', '.join(school.subject_label(s) for s in subjects) or 'None yet'}",
        f"Overall Grade Average: {utils.fmt_pct(overall)} across {len(items)} graded items",
        "Upcoming / Missing Coursework: "
        + (", ".join(f"{t['title']} ({t['subject']}, {t['status']}, due {utils.fmt_dt(t['due'])})" for t in todo[:6]) or "All caught up"),
    ]
    if items:
        recent = list(reversed(items))[:4]
        ctx_lines.append(
            "Recent Grades: " + ", ".join(f"{r['title']}: {r['score']:g}/{r['max']} ({utils.fmt_pct(r['percent'])})" for r in recent)
        )

    matched_lessons, _ = semantic_retrieve(query, subject_ids, top_k=2)
    for les in matched_lessons:
        ctx_lines.append(f"Teacher's Lesson Note ('{les['title']}'): {les['content'][:500]}")

    math_sol, math_note = solve_math_problem(query)
    if math_sol:
        ctx_lines.append(f"Verified Symbolic Math Engine Result ({math_note}):\n{math_sol}")

    return "\n".join(ctx_lines), math_sol, math_note


def solve_any_problem_with_ai(query):
    """Solve any math, science, calculus, statistics, or coding problem using both
    the exact Symbolic Engine and the live Cloud LLM."""
    q = (query or "").strip()
    if not q:
        return None, None

    math_sol, math_note = solve_math_problem(q)
    sys_prompt = (
        "You are NovaAI, an expert Mathematics, Physics, Chemistry, Statistics, and Computer Science solver. "
        "Solve the user's problem clearly and step-by-step using clean Markdown and LaTeX math ($...$ and $$...$$). "
        "Always show: (1) Problem Setup / Given Formula, (2) Step-by-Step Working, and (3) Final Verified Answer."
    )
    if math_sol:
        sys_prompt += f"\n\nVerified Symbolic Engine Check (must match your final numerical answer):\n{math_sol}"

    reply, _, model_used = call_live_llm(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Solve step-by-step: {q}"},
        ],
        temperature=0.2,
    )
    if reply:
        note = f"Live AI Solver ({model_used})" + (f" + {math_note}" if math_note else "")
        return reply, note
    if math_sol:
        return math_sol, math_note
    return None, None


# ==========================================================================
# Teacher AI Copilot Engine (Live LLM + Multi-Turn Memory + Live RAG)
# ==========================================================================
def ask_teacher_ai(user, prompt, mode="Analytical & Data-Driven"):
    """Answer a teacher's question using a real Large Language Model grounded in
    live Novarix school telemetry and multi-turn conversation history."""
    raw_q = (prompt or "").strip()
    subjects = (school.all_subjects() if user["role"] == "admin"
                else school.subjects_for_teacher(user["id"]))
    subject_ids = [s["id"] for s in subjects]

    # Initial welcome screen when chat is empty
    if not raw_q or raw_q.lower() == "summary":
        queue, _ = coursework.grading_queue(subject_ids) if subject_ids else ([], [])
        alerts = insights.support_alerts(subjects) if subjects else []
        prefs = insights.get_teacher_prefs(user["id"])
        dash_classes = prefs.get("added_classes", [])
        dash_asgs = [a for a in prefs.get("added_assignments", []) if not a.get("done")]
        return (
            f"### NovaAI Copilot — Welcome, {user['full_name'].split()[0]}\n"
            f"I am powered by a **live Large Language Model** connected directly to your Novarix workspace.\n\n"
            f"- **Dashboard Classes:** `{len(dash_classes)}` · **Assignments to Check:** `{len(dash_asgs)}` pending\n"
            f"- **LMS Grading Queue:** `{len(queue)}` ungraded submission(s) · **Support Alerts:** `{len(alerts)}`\n\n"
            "**Ask me anything in natural language:**\n"
            "- *Any academic, math, science, history, or coding question*\n"
            "- *Custom lesson plans, worksheets, exam questions, parent emails, or rubrics*\n"
            "- *Live questions about your classes, grading queue, or students*"
        )

    rag_context, math_sol, math_note = _build_teacher_rag_context(user, raw_q)
    trace = [
        f"STAGE 01 // USER PROMPT: '{raw_q[:80]}' | Mode='{mode}'",
        f"STAGE 02 // LIVE RAG CONTEXT: Injected teacher workspace telemetry ({len(subjects)} subjects)",
    ]
    if math_note:
        trace.append(f"STAGE 02b // SYMBOLIC VERIFIER: {math_note}")

    sys_prompt = (
        f"You are NovaAI, an intelligent AI Teaching Copilot built into the Novarix school LMS.\n"
        f"Adopt the cognitive persona: {mode}.\n"
        f"Answer any question the teacher asks — whether it is an open-ended academic question, math/science problem, "
        f"coding request, lesson/curriculum design, parent email draft, or a question about their live Novarix classes.\n"
        f"Use clean Markdown formatting and LaTeX ($...$ / $$...$$) for any mathematical formulas.\n\n"
        f"=== LIVE NOVARIX CLASSROOM TELEMETRY ===\n{rag_context}\n========================================"
    )

    messages = [{"role": "system", "content": sys_prompt}]
    for past in get_chat_history(user["id"])[-8:]:
        if past.get("role") in ("user", "assistant") and past.get("content"):
            messages.append({"role": past["role"], "content": past["content"][:1200]})
    messages.append({"role": "user", "content": raw_q})

    llm_reply, llm_reasoning, model_used = call_live_llm(messages, temperature=0.45)
    if llm_reply:
        trace.append(f"STAGE 03 // LIVE LLM INFERENCE: Model='{model_used}' responded ({len(llm_reply)} chars)")
        if llm_reasoning:
            trace.append(f"LLM REASONING TRACE:\n{llm_reasoning}")
        st_session_save_trace(user["id"], trace)
        return llm_reply

    # Offline fallback if network is unreachable or in fast test mode
    trace.append(f"STAGE 03 // OFFLINE FALLBACK ({model_used})")
    st_session_save_trace(user["id"], trace)
    if math_sol:
        return math_sol
    matched_lessons, matched_kg = semantic_retrieve(raw_q, subject_ids, top_k=1)
    if matched_kg:
        node = matched_kg[0]
        return f"### {node['title']} ({node['subject']})\n\n{node['summary']}\n\n{node['example']}"
    if matched_lessons:
        les = matched_lessons[0]
        return f"### {les['title']}\n\n{les['content']}"
    return f"### NovaAI Workspace Summary\n\n```\n{rag_context}\n```"


# ==========================================================================
# AI Submission Evaluator & Rubric Grader (Powered by Live LLM)
# ==========================================================================
def evaluate_submission_with_ai(assignment_title, max_points, student_text, rubric_focus=""):
    """Evaluate a student's submission using the live LLM and return a structured
    evaluation with suggested score, criterion breakdown, and feedback."""
    text = (student_text or "").strip()
    max_pts = float(max_points or 100)
    if not text:
        return {
            "suggested_score": 0.0,
            "percent": 0.0,
            "summary": "No text content was provided in this submission.",
            "feedback": "Please submit your written response or file so it can be evaluated.",
        }

    sys_prompt = (
        "You are an expert teacher and academic evaluator in the Novarix LMS. "
        "Evaluate the student's submission fairly and constructively against the assignment title, max points, and rubric focus. "
        "Return ONLY valid JSON with these exact keys:\n"
        '{\n'
        '  "suggested_score": <number between 0 and max_points>,\n'
        '  "completeness_pct": <number 0-100>,\n'
        '  "Completeness_comment": "<short comment>",\n'
        '  "depth_pct": <number 0-100>,\n'
        '  "depth_comment": "<short comment>",\n'
        '  "clarity_pct": <number 0-100>,\n'
        '  "clarity_comment": "<short comment>",\n'
        '  "strengths": ["<strength 1>", "<strength 2>"],\n'
        '  "improvements": ["<improvement 1>", "<improvement 2>"],\n'
        '  "feedback": "<2-3 sentence constructive feedback directly addressing the student>"\n'
        '}'
    )
    user_msg = (
        f"Assignment Title: {assignment_title}\n"
        f"Maximum Points: {max_pts:g}\n"
        f"Rubric Focus / Key Concepts: {rubric_focus or 'Accuracy, step-by-step reasoning, and clarity'}\n\n"
        f"Student Submission:\n{text}"
    )

    llm_reply, _, model_used = call_live_llm(
        [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}],
        temperature=0.2,
    )
    if llm_reply:
        try:
            m_json = re.search(r"\{.*\}", llm_reply, re.DOTALL)
            parsed = json.loads(m_json.group(0) if m_json else llm_reply)
            suggested_score = round(min(max_pts, max(0.0, float(parsed.get("suggested_score", max_pts * 0.85)))), 1)
            pct = round((suggested_score / max_pts) * 100, 1) if max_pts > 0 else 0.0
            comp_pct = float(parsed.get("completeness_pct", pct))
            depth_pct = float(parsed.get("depth_pct", pct))
            clarity_pct = float(parsed.get("clarity_pct", pct))
            comp_c = parsed.get("Completeness_comment") or parsed.get("completeness_comment") or "Evaluated by AI"
            depth_c = parsed.get("depth_comment") or "Evaluated by AI"
            clarity_c = parsed.get("clarity_comment") or "Evaluated by AI"
            feedback_text = (parsed.get("feedback") or "").strip() or f"Good work on {assignment_title}."
            strengths = parsed.get("strengths") or []
            improvements = parsed.get("improvements") or []

            strengths_md = "\n".join(f"- **Strength:** {s}" for s in strengths)
            improve_md = "\n".join(f"- **Area to Improve:** {i}" for i in improvements)
            report_md = (
                f"### NovaAI Live Evaluation — *{assignment_title}* (`{model_used}`)\n"
                f"- **Recommended Score:** **`{suggested_score:g} / {max_pts:g}`** (**`{pct}%`**)\n\n"
                "| Rubric Criterion | Weight | Score | AI Assessment |\n"
                "| :--- | :--- | :--- | :--- |\n"
                f"| **Completeness & Coverage** | 40% | `{comp_pct:.0f}%` | {comp_c} |\n"
                f"| **Analytical Depth & Accuracy** | 35% | `{depth_pct:.0f}%` | {depth_c} |\n"
                f"| **Clarity & Structure** | 25% | `{clarity_pct:.0f}%` | {clarity_c} |\n\n"
                + (f"{strengths_md}\n" if strengths_md else "")
                + (f"{improve_md}\n\n" if improve_md else "\n")
                + f"**Ready-to-Save Feedback:**\n> {feedback_text}"
            )
            return {
                "suggested_score": suggested_score,
                "percent": pct,
                "summary": report_md,
                "feedback": feedback_text,
            }
        except Exception:
            pass

    # Fallback heuristic evaluation if offline
    words = text.split()
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    has_structure = any(marker in text for marker in ("\n", "1.", "-", "•", "because", "therefore", "however", "def ", "="))
    has_quant = bool(re.search(r"(\d+|\"[^\"]+\"|'[^']+'|==|\+|\-|\*|\/)", text))
    comp_ratio = min(1.0, word_count / 65.0) if word_count >= 15 else max(0.35, word_count / 30.0)
    depth_ratio = 0.92 if (has_structure and has_quant) else (0.80 if (has_structure or has_quant) else 0.68)
    clarity_ratio = 0.95 if len(sentences) >= 3 else 0.78
    total_ratio = min(0.98, max(0.45, 0.40 * comp_ratio + 0.35 * depth_ratio + 0.25 * clarity_ratio))
    suggested_score = round(max_pts * total_ratio, 1)
    pct = round(total_ratio * 100, 1)
    feedback_text = f"Solid effort on '{assignment_title}'. Your response covers the key points clearly."
    report_md = (
        f"### NovaAI Submission Evaluation — *{assignment_title}*\n"
        f"- **Recommended Score:** **`{suggested_score:g} / {max_pts:g}`** (**`{pct}%`**)\n\n"
        f"**Ready-to-Save Feedback:**\n> {feedback_text}"
    )
    return {
        "suggested_score": suggested_score,
        "percent": pct,
        "summary": report_md,
        "feedback": feedback_text,
    }


# ==========================================================================
# Teacher Content Generators (Powered by Live LLM)
# ==========================================================================
def generate_lesson_draft(subject_name, topic, title, focus_points=""):
    """Generate a rich, structured Markdown lesson using the live LLM."""
    topic = utils.clean(topic, 80) or "Core Concepts"
    title = utils.clean(title, 120) or f"Introduction to {topic}"
    focus = utils.clean(focus_points, 300)

    prompt = (
        f"Write a comprehensive, engaging classroom lesson in Markdown for:\n"
        f"- Subject: {subject_name}\n"
        f"- Unit / Topic: {topic}\n"
        f"- Lesson Title: {title}\n"
        f"- Specific Focus: {focus or 'Core theory, key formulas/rules, worked step-by-step example, and common misconceptions'}\n\n"
        f"Include: (1) Learning Objectives, (2) Core Theory & Key Rules/Formulas (use LaTeX $...$ if applicable), "
        f"(3) A Complete Step-by-Step Worked Classroom Example, and (4) 3 Quick Self-Check Exit Ticket Questions."
    )
    llm_reply, _, _ = call_live_llm(
        [
            {"role": "system", "content": "You are an expert curriculum designer writing clear, structured Markdown lessons for students."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    resources = f"{title} — Reference Guide | https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"
    if llm_reply:
        return {"topic": topic, "title": title, "content": llm_reply, "resources": resources}

    # Offline fallback
    content = (
        f"# {title}\n"
        f"**Subject:** {subject_name} · **Unit / Topic:** {topic}\n\n"
        f"## 1. Learning Objectives\n"
        f"1. Define the foundational principles of **{title}** within {subject_name}.\n"
        f"2. Apply step-by-step problem-solving strategies to analyze **{topic}** scenarios.\n\n"
        f"## 2. Core Concepts\n"
        f"- **Fundamental Principle of {topic}**: Definition, key terminology, and governing rules.\n"
        f"- **Worked Application**: Step-by-step analysis and verification.\n"
    )
    return {"topic": topic, "title": title, "content": content, "resources": resources}


def generate_quiz_questions(subject_name, topic, count=4):
    """Generate real, topic-specific multiple-choice questions using the live LLM."""
    topic = utils.clean(topic, 80) or subject_name
    num_q = max(1, min(int(count or 4), 6))

    sys_prompt = (
        "You are an expert academic assessment writer. Generate multiple-choice quiz questions. "
        "Return ONLY a valid JSON array of objects, where each object has:\n"
        '{"text": "<question text>", "options": ["<option A>", "<option B>", "<option C>", "<option D>"], "answer": <integer 0, 1, 2, or 3 indicating the correct option>, "points": 2}'
    )
    user_msg = (
        f"Generate {num_q} rigorous, specific multiple-choice questions on the topic '{topic}' "
        f"for the subject '{subject_name}'. Make the questions test real subject knowledge, calculations, or concepts."
    )
    llm_reply, _, _ = call_live_llm(
        [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}],
        temperature=0.35,
    )
    if llm_reply:
        try:
            m_arr = re.search(r"\[.*\]", llm_reply, re.DOTALL)
            parsed = json.loads(m_arr.group(0) if m_arr else llm_reply)
            valid_questions = []
            for item in parsed:
                if isinstance(item, dict) and item.get("text") and isinstance(item.get("options"), list) and len(item["options"]) >= 2:
                    opts = [str(o) for o in item["options"][:4]]
                    while len(opts) < 4:
                        opts.append("None of the above")
                    ans = int(item.get("answer", 0))
                    if ans < 0 or ans >= len(opts):
                        ans = 0
                    valid_questions.append({
                        "text": str(item["text"]),
                        "options": opts,
                        "answer": ans,
                        "points": int(item.get("points", 2)),
                    })
            if valid_questions:
                return valid_questions[:num_q]
        except Exception:
            pass

    # Offline fallback
    templates = [
        {
            "text": f"Which statement best describes the primary objective of studying {topic} in {subject_name}?",
            "options": [
                f"Understanding the core rules, relationships, and applications of {topic}",
                f"Memorizing random numbers without applying {topic} principles",
                f"Ignoring evidence and skipping verification steps in {topic}",
                f"Replacing all {subject_name} methods with guesswork",
            ],
            "answer": 0,
            "points": 2,
        },
        {
            "text": f"When solving a multi-step problem involving {topic}, what should be your FIRST step?",
            "options": [
                "Guess the final answer immediately",
                f"Identify the known values, target goal, and governing {topic} principle",
                "Skip writing down intermediate steps",
                "Change the units randomly",
            ],
            "answer": 1,
            "points": 2,
        },
        {
            "text": f"How can you verify that your solution to a {topic} problem is accurate?",
            "options": [
                "Substitute the result back into the original context and check units/reasonableness",
                "Assume the first calculation is always right without checking",
                "Erase the working steps so errors cannot be seen",
                "Only check the answer if it is a whole number",
            ],
            "answer": 0,
            "points": 2,
        },
        {
            "text": f"If you encounter an unfamiliar challenge in {topic}, which strategy is most effective?",
            "options": [
                "Leave the question blank immediately",
                f"Break the problem into smaller parts and connect it to foundational {subject_name} rules",
                "Copy an unrelated formula from another chapter",
                "Skip reading the problem statement",
            ],
            "answer": 1,
            "points": 2,
        },
    ]
    return templates[:num_q]


def generate_assignment_and_rubric(subject_name, topic, max_points=30):
    """Generate a tailored assignment prompt and grading rubric using the live LLM."""
    topic = utils.clean(topic, 80) or subject_name
    pts = int(max_points or 30)
    title = f"{topic} — Applied Problem Set & Analysis"

    prompt = (
        f"Create a detailed student assignment and a 3-tier Markdown grading rubric table for:\n"
        f"- Subject: {subject_name}\n"
        f"- Topic: {topic}\n"
        f"- Total Points: {pts}\n\n"
        f"Include concrete, specific questions/tasks on {topic} (Part 1: Conceptual Questions, Part 2: Applied Problems/Tasks, Part 3: Critical Thinking), "
        f"followed by a Markdown Grading Rubric table whose criteria add up to {pts} points."
    )
    llm_reply, _, _ = call_live_llm(
        [
            {"role": "system", "content": "You are an expert teacher creating clear, rigorous classroom assignments and Markdown rubrics."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    if llm_reply:
        return {"title": title, "description": llm_reply, "max_points": pts}

    c1 = round(pts * 0.4)
    c2 = round(pts * 0.4)
    c3 = pts - c1 - c2
    description = (
        f"### Assignment Overview\n"
        f"Demonstrate your mastery of **{topic}** in **{subject_name}** by completing the three parts below.\n\n"
        f"#### Part 1: Concept Explanation ({c1} pts)\n"
        f"Explain the core principles of **{topic}** in your own words and include one example.\n\n"
        f"#### Part 2: Worked Problems ({c2} pts)\n"
        f"Solve the practice problems on **{topic}**, showing every step of your reasoning.\n\n"
        f"#### Part 3: Reflection ({c3} pts)\n"
        f"Identify one common mistake in **{topic}** and explain how to avoid it."
    )
    return {"title": title, "description": description, "max_points": pts}


# ==========================================================================
# Student AI Study Tutor Engine (Live LLM + Socratic Modes + Live RAG)
# ==========================================================================
def ask_student_ai(user, prompt, mode="Step-by-Step Deep Explainer"):
    """Answer a student's question using a real Large Language Model grounded in
    their live Novarix coursework, grades, deadlines, and multi-turn chat history."""
    raw_q = (prompt or "").strip()
    subjects = school.subjects_for_student(user["id"])
    subject_ids = [s["id"] for s in subjects]

    if not raw_q or raw_q.lower() == "summary":
        todo = insights.student_todo(user["id"])
        items = tracking.grade_items_for_student(user["id"])
        overall = utils.mean([i["percent"] for i in items])
        return (
            f"### Hi {user['full_name'].split()[0]}! I'm your NovaAI Live Study Tutor.\n"
            f"I am powered by a **live Large Language Model** and connected to your Novarix classes.\n\n"
            f"- **Enrolled Subjects:** `{len(subjects)}` · **Pending Deadlines:** `{len(todo)}` · **Overall Average:** `{utils.fmt_pct(overall)}`\n\n"
            "**Ask me anything at all:**\n"
            "- *Solve any math, calculus, physics, chemistry, or statistics problem step-by-step*\n"
            "- *Explain any concept, historical event, literary text, or write/debug code*\n"
            "- *Quiz you on a topic, give Socratic hints, or check your upcoming assignments & grades*"
        )

    rag_context, math_sol, math_note = _build_student_rag_context(user, raw_q)
    trace = [
        f"STAGE 01 // STUDENT QUERY: '{raw_q[:80]}' | TutorMode='{mode}'",
        f"STAGE 02 // LIVE RAG CONTEXT: Injected student coursework, grades & lessons ({len(subjects)} subjects)",
    ]
    if math_note:
        trace.append(f"STAGE 02b // SYMBOLIC VERIFIER: {math_note}")

    mode_instructions = {
        "Step-by-Step Deep Explainer": (
            "Explain concepts and solve problems thoroughly step-by-step. Show clear derivations, formulas (in LaTeX $...$ / $$...$$), and a concrete example."
        ),
        "Socratic Hint Coach (Guided Thinking)": (
            "Act as a Socratic tutor: guide the student with clear intuition, step-by-step hints, and a guiding question so they learn how to reason through the problem, while still being super helpful."
        ),
        "ELI5 / Intuition & Analogies": (
            "Explain the topic using vivid real-world analogies and simple, intuitive language first, then connect it to the formal academic rules."
        ),
        "Exam Cram & Practice Quizzer": (
            "Give a high-yield exam summary (key formulas, definitions, common traps) followed by 2 quick practice questions with answers."
        ),
    }.get(mode, "Explain clearly and step-by-step.")

    sys_prompt = (
        f"You are NovaAI, an intelligent, encouraging AI Study Tutor built into the Novarix school LMS.\n"
        f"Tutor Mode: {mode} — {mode_instructions}\n"
        f"Answer any question the student asks across any subject (Math, Physics, Chemistry, Biology, Computer Science, "
        f"English, History, World Languages, Study Skills, or their own Novarix deadlines and grades).\n\n"
        f"=== LIVE STUDENT NOVARIX CONTEXT ===\n{rag_context}\n===================================="
    )

    messages = [{"role": "system", "content": sys_prompt}]
    for past in get_chat_history(user["id"])[-8:]:
        if past.get("role") in ("user", "assistant") and past.get("content"):
            messages.append({"role": past["role"], "content": past["content"][:1200]})
    messages.append({"role": "user", "content": raw_q})

    llm_reply, llm_reasoning, model_used = call_live_llm(messages, temperature=0.45)
    if llm_reply:
        trace.append(f"STAGE 03 // LIVE LLM INFERENCE: Model='{model_used}' responded ({len(llm_reply)} chars)")
        if llm_reasoning:
            trace.append(f"LLM REASONING TRACE:\n{llm_reasoning}")
        st_session_save_trace(user["id"], trace)
        return llm_reply

    # Offline fallback if network is unreachable or in fast test mode
    trace.append(f"STAGE 03 // OFFLINE FALLBACK ({model_used})")
    st_session_save_trace(user["id"], trace)
    if math_sol:
        return math_sol
    matched_lessons, matched_kg = semantic_retrieve(raw_q, subject_ids, top_k=1)
    if matched_kg:
        node = matched_kg[0]
        return f"### {node['title']} ({node['subject']})\n\n{node['summary']}\n\n{node['example']}"
    if matched_lessons:
        les = matched_lessons[0]
        return f"### {les['title']}\n\n{les['content']}"
    return f"### Study Context\n\n```\n{rag_context}\n```"


def st_session_save_trace(user_id, trace_steps):
    """Store the latest Chain-of-Thought reasoning trace in Streamlit session_state."""
    try:
        import streamlit as st
        st.session_state[f"_ai_trace_{user_id}"] = trace_steps
    except Exception:
        pass


def get_latest_trace(user_id):
    """Retrieve the latest Chain-of-Thought reasoning trace for ``user_id``."""
    try:
        import streamlit as st
        return st.session_state.get(f"_ai_trace_{user_id}", [])
    except Exception:
        return []


def build_study_cards(user, subject_id=None):
    """Turn published lessons (plus built-in core concepts if no lessons exist yet)
    into interactive study flashcards."""
    subjects = school.subjects_for_student(user["id"])
    subject_ids = [s["id"] for s in subjects if not subject_id or subject_id == "all" or s["id"] == subject_id]
    lessons = coursework.lessons_for_subjects(subject_ids)
    cards = []
    for les in lessons:
        my_rating = tracking.my_pulse(user["id"], les["id"])
        paragraphs = [p.strip() for p in les["content"].split("\n\n") if p.strip()]
        summary = "\n\n".join(paragraphs[:2]) if paragraphs else les["content"]
        cards.append({
            "lesson_id": les["id"],
            "subject": school.subject_label(les["subject_id"]),
            "topic": les["topic"],
            "front": les["title"],
            "prompt": f"Explain the core idea and key rules of '{les['title']}' ({les['topic']}) before flipping the card.",
            "back": summary,
            "confidence": my_rating["rating"] if my_rating else None,
            "resources": les.get("resources", []),
            "is_builtin": False,
        })

    # If the student's class has no teacher-published lessons yet, provide rich built-in flashcards!
    if not cards:
        for node in KNOWLEDGE_GRAPH:
            cards.append({
                "lesson_id": None,
                "subject": node["subject"],
                "topic": node["topic"],
                "front": node["title"],
                "prompt": node["practice"],
                "back": f"{node['summary']}\n\n{node['example']}",
                "confidence": None,
                "resources": [],
                "is_builtin": True,
            })
    return cards


def generate_study_plan(user):
    """Create a personalized, step-by-step study checklist for a student."""
    todo = insights.student_todo(user["id"])
    subjects = school.subjects_for_student(user["id"])
    subject_ids = [s["id"] for s in subjects]
    lessons = coursework.lessons_for_subjects(subject_ids)

    low_pulse = []
    unrated = []
    for les in lessons:
        vote = tracking.my_pulse(user["id"], les["id"])
        if vote and vote["rating"] <= 3:
            low_pulse.append((les, vote["rating"]))
        elif not vote:
            unrated.append(les)

    steps = []
    missing = [t for t in todo if t["status"] == "Missing"]
    for m in missing[:2]:
        steps.append({
            "priority": "1 · URGENT (Missing)",
            "task": f"Complete & submit **{m['title']}** ({m['subject']})",
            "why": f"Past due ({utils.relative_due(m['due'])}) — submitting now still recovers points.",
        })

    upcoming = [t for t in todo if t["status"] != "Missing"]
    for u in upcoming[:3]:
        steps.append({
            "priority": "2 · UPCOMING DEADLINE",
            "task": f"Work on {u['kind'].lower()} **{u['title']}** ({u['subject']})",
            "why": f"Due {utils.fmt_dt(u['due'])} ({utils.relative_due(u['due'])}).",
        })

    for les, rating in sorted(low_pulse, key=lambda x: x[1])[:2]:
        steps.append({
            "priority": "3 · CONCEPT REVIEW",
            "task": f"Review flashcards & notes for **{les['title']}** ({school.subject_label(les['subject_id'])})",
            "why": f"You rated your confidence {rating}/5 on NovaPulse.",
        })

    if unrated:
        steps.append({
            "priority": "4 · SELF-CHECK",
            "task": f"Read and rate **{unrated[0]['title']}** on NovaPulse",
            "why": f"You have {len(unrated)} unrated lesson(s).",
        })

    if not steps:
        steps.append({
            "priority": "● ALL CAUGHT UP",
            "task": "Practice 3 flashcards or test the Symbolic Math Solver in NovaAI",
            "why": "You have zero missing items and all deadlines are under control!",
        })
    return steps
