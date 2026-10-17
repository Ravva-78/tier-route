"""Audit helpers: robust extraction grader + deployable (gold-free) verifier. Original grader/verifier code untouched."""
import ast, re, sys, unicodedata
sys.path.insert(0, ".")
from tierroute.grading_v2 import grade_task_v2, grade_exact_extraction
from tierroute.verifier import UNSURE  # pre-existing phrase list, reused unchanged

_HY = dict.fromkeys(map(ord, "‐‑‒–—―−­"), "-")
_QU = dict.fromkeys(map(ord, "‘’‚‛′`"), "'")
_QU.update(dict.fromkeys(map(ord, "“”„‟″"), '"'))

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_HY).translate(_QU)
    s = "".join(" " if unicodedata.category(c) == "Zs" else c for c in s)
    s = s.replace("*", "")                       # markdown bold/italic
    s = re.sub(r"(^|\s)_+|_+(\s|$)", r"\1\2", s)  # emphasis underscores only at token edges (keep snake_case)
    return re.sub(r"\s+", " ", s).strip()

def grade_robust(task, text):
    """Original grader everywhere, except extraction ('exact') tasks use normalised comparison."""
    if not text:
        return False, "empty_response"
    if task["grader"].get("type") not in ("exact", None):
        return grade_task_v2(task, text)
    ok, why = grade_exact_extraction(norm(text), norm(str(task["answer"])))
    return ok, why

def _code(text):
    m = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    return m.group(1) if m else text

def verify_deploy(prompt, text, finish_reason):
    """Gold-free verifier. Inputs: task prompt, model output, finish_reason. Returns (ok, reason)."""
    if not (text or "").strip():
        return False, "empty"
    if finish_reason == "length":
        return False, "finish_reason=length"
    low = text.lower()
    if any(p in low for p in UNSURE):
        return False, "uncertainty_phrase"
    if "```python" in prompt:
        try:
            ast.parse(_code(text))
        except (SyntaxError, ValueError):
            return False, "python_parse_failure"
    elif re.search(r"Answer:", prompt) and not re.search(r"answer\s*:", low):
        return False, "missing_Answer_format"
    return True, "ok"
