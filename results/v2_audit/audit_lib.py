"""Audit helpers (v2 audit). Robust grader now lives in evaluation/grading_robust.py."""
import ast, re, sys
sys.path.insert(0, ".")
from evaluation.grading_v2 import grade_task_v2
from evaluation.grading_robust import grade_robust, norm
from tierroute.verifier import UNSURE

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
