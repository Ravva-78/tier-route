"""EVALUATION-ONLY formatting-robust extraction grader (the original grader stays in grading_v2).
Never import from tierroute/ (enforced by tests/test_no_leak.py)."""
import re
import unicodedata

from evaluation.grading_v2 import grade_exact_extraction, grade_task_v2

_HY = dict.fromkeys(map(ord, "‐‑‒–—―−­"), "-")
_QU = dict.fromkeys(map(ord, "‘’‚‛′`"), "'")
_QU.update(dict.fromkeys(map(ord, "“”„‟″"), '"'))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_HY).translate(_QU)
    s = "".join(" " if unicodedata.category(c) == "Zs" else c for c in s)
    s = s.replace("*", "")                        # markdown bold/italic
    s = re.sub(r"(^|\s)_+|_+(\s|$)", r"\1\2", s)  # emphasis underscores only at token edges (keeps snake_case)
    return re.sub(r"\s+", " ", s).strip()


def grade_robust(task, text):
    """Original grader everywhere, except extraction ('exact') tasks use normalised comparison."""
    if not text:
        return False, "empty_response"
    if task["grader"].get("type") not in ("exact", None):
        return grade_task_v2(task, text)
    return grade_exact_extraction(norm(text), norm(str(task["answer"])))
