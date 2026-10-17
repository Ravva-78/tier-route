"""EVALUATION-ONLY. Never import this from tierroute/ (enforced by tests/test_no_leak.py).
Exact-match grading harness for benchmark v2.
Supports:
- Numeric exact match (parsed from 'Answer: X')
- Multiple choice exact match (parsed from 'Answer: X')
- Subprocess unit-test execution for Python code
- Exact string match for messy extraction
No keyword or substring matching is used.
"""

import os
import re
import subprocess
import sys
import tempfile
from typing import Dict, Any, Tuple


def grade_numeric(response_text: str, gold_answer: str) -> Tuple[bool, str]:
    matches = re.findall(r"(?:Answer|ANSWER|Final Answer|final answer)[:\s]*([+-]?[0-9,]+(?:\.[0-9]+)?)", response_text)
    if not matches:
        return False, "missing_answer_format"
    pred_str = matches[-1].replace(",", "").strip()
    gold_str = str(gold_answer).replace(",", "").strip()
    try:
        val_pred = float(pred_str)
        val_gold = float(gold_str)
        if abs(val_pred - val_gold) < 1e-4:
            return True, f"exact_numeric_match ({val_pred})"
        return False, f"numeric_mismatch (pred={val_pred}, gold={val_gold})"
    except ValueError:
        if pred_str == gold_str:
            return True, f"exact_str_match ({pred_str})"
        return False, f"parse_error (pred={pred_str}, gold={gold_str})"


def grade_multiple_choice(response_text: str, gold_choice: str) -> Tuple[bool, str]:
    matches = re.findall(r"(?:Answer|ANSWER|Final Answer|final answer)[:\s]*\(?([A-Da-d1-4])\)?", response_text)
    if not matches:
        # Fallback: check last non-empty line
        lines = [l.strip() for l in response_text.strip().splitlines() if l.strip()]
        if lines:
            m_last = re.search(r"\(?([A-Da-d1-4])\)?$", lines[-1])
            if m_last:
                matches = [m_last.group(1)]
    if not matches:
        return False, "missing_choice_format"
    pred_choice = matches[-1].strip().upper()
    gold_clean = str(gold_choice).strip().upper()
    if pred_choice == gold_clean:
        return True, f"exact_choice_match ({pred_choice})"
    return False, f"choice_mismatch (pred={pred_choice}, gold={gold_clean})"


def grade_exact_extraction(response_text: str, gold_answer: str) -> Tuple[bool, str]:
    matches = re.findall(r"(?:Answer|ANSWER|Final Answer|final answer)[:\s]*(.+)", response_text)
    if not matches:
        # Check last line
        lines = [l.strip() for l in response_text.strip().splitlines() if l.strip()]
        if lines:
            matches = [lines[-1]]
    if not matches:
        return False, "missing_extraction_format"
    pred = matches[-1].strip().strip('"').strip("'").strip(".")
    gold = str(gold_answer).strip().strip('"').strip("'").strip(".")
    if pred.lower() == gold.lower():
        return True, f"exact_extraction_match ({pred})"
    return False, f"extraction_mismatch (pred='{pred}', gold='{gold}')"


def grade_code(response_text: str, test_code: str, timeout: float = 5.0) -> Tuple[bool, str]:
    # Extract code from ```python ... ``` or take all python definitions
    code_match = re.search(r"```(?:python)?\s*(.*?)\s*```", response_text, re.DOTALL)
    if code_match:
        code_to_run = code_match.group(1)
    else:
        # If no code fences, check if response contains def/import statements
        lines = response_text.splitlines()
        code_lines = [l for l in lines if not l.startswith("Here") and not l.startswith("Sure") and not l.startswith("Note")]
        code_to_run = "\n".join(code_lines)

    full_script = f"# -*- coding: utf-8 -*-\nimport sys\n\n{code_to_run}\n\n{test_code}\n\nprint('__ALL_TESTS_PASSED__')\n"

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(full_script)
        fname = f.name

    try:
        p = subprocess.run([sys.executable, fname], capture_output=True, timeout=timeout, text=True)
        if p.returncode == 0 and "__ALL_TESTS_PASSED__" in p.stdout:
            return True, "unit_tests_passed"
        err_msg = (p.stderr or p.stdout or "non-zero return code").strip().splitlines()[-1] if (p.stderr or p.stdout) else "failed"
        return False, f"test_execution_failed: {err_msg[:60]}"
    except subprocess.TimeoutExpired:
        return False, f"execution_timeout (>{timeout}s)"
    except Exception as e:
        return False, f"execution_error: {str(e)[:60]}"
    finally:
        if os.path.exists(fname):
            try:
                os.remove(fname)
            except Exception:
                pass


def grade_task_v2(task: Dict[str, Any], response_text: str) -> Tuple[bool, str]:
    """Grade a model response against task_v2 gold answer and test suite."""
    if not response_text:
        return False, "empty_response"
    grader = task.get("grader", {})
    gtype = grader.get("type")
    gold = task.get("answer", "")

    if gtype == "numeric":
        return grade_numeric(response_text, gold)
    elif gtype == "multiple_choice":
        return grade_multiple_choice(response_text, gold)
    elif gtype == "code":
        test_code = grader.get("test_code", "")
        return grade_code(response_text, test_code)
    elif gtype == "exact":
        return grade_exact_extraction(response_text, gold)
    else:
        # Fallback to exact
        return grade_exact_extraction(response_text, gold)
