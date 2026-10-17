"""Complexity analyser (rule-based v1). Returns a 0..1 difficulty score and a task type.
This is the component to upgrade later with a trained classifier for the comparison study."""
import re

SIMPLE_KW = ["extract", "classify", "categorize", "label", "reformat", "format", "convert", "translate",
             "list", "sort", "capitalize", "lowercase", "uppercase", "sentiment", "yes or no",
             "true or false", "spam", "email address", "capital of"]
HARD_KW = ["prove", "derive", "explain", "why", "step by step", "analyze", "analyse", "compare",
           "trade-off", "tradeoff", "design", "architecture", "optimize", "optimise", "debug",
           "implement", "algorithm", "evaluate", "critique", "strategy", "complexity", "probability",
           "how many ways", "edge case", "pros and cons", "solve", "twice as"]
CODE_RE = re.compile(r"```|\bdef \w+|\bclass \w+|\bfunction\b|\bSELECT\b|#include|=>|\bpython\b", re.I)
MATH_RE = re.compile(r"\d\s*[\+\-\*/\^=]\s*\d|\bequation\b|%|\bhow old\b|\bhow long\b|\bhow many\b|"
                     r"\bhow much\b|\btotal\b|\broots?\b|\bx\^?\d", re.I)

TASK_RULES = [
    ("extraction", ["extract", "email address", "phone number", "find the date"]),
    ("classification", ["classify", "categorize", "sentiment", "spam", "label"]),
    ("translation", ["translate"]),
    ("formatting", ["convert", "reformat", "format", "uppercase", "lowercase", "sort", "capitalize"]),
    ("code", ["python", "function", "code", "sql", "debug", "implement", "algorithm"]),
    ("reasoning", ["why", "prove", "derive", "how many", "probability", "solve", "explain", "analy",
                   "compare", "calculate", "how old", "how long", "twice as"]),
]
TASK_TYPES = [t for t, _ in TASK_RULES] + ["qa"]


def detect_task(low: str) -> str:
    for task, kws in TASK_RULES:
        if any(k in low for k in kws):
            return task
    return "qa"


def analyze(text: str) -> dict:
    low = text.lower()
    words = len(text.split())
    task = detect_task(low)
    hard_hits = [k for k in HARD_KW if k in low]
    simple_hits = [k for k in SIMPLE_KW if k in low]
    math = bool(MATH_RE.search(text))
    code = bool(CODE_RE.search(text)) or task == "code"
    multistep = bool(re.search(r"\b(step by step|multi-step|then|after that|in \d+ years)\b", low))

    score = 0.12
    score += min(0.20, words / 500)
    score += min(0.40, 0.14 * len(hard_hits))
    score += 0.18 if math else 0
    score += 0.15 if code else 0
    score += 0.08 if multistep else 0
    score -= min(0.20, 0.10 * len(simple_hits))
    score = max(0.0, min(1.0, score))

    signals = []
    if hard_hits:
        signals.append("reasoning cues: " + ", ".join(hard_hits[:3]))
    if math:
        signals.append("math/quantity")
    if code:
        signals.append("code")
    if simple_hits:
        signals.append("simple-task cues: " + ", ".join(simple_hits[:3]))
    signals.append(f"{words} words")
    return {"score": round(score, 3), "task_type": task, "signals": "; ".join(signals)}
