"""Guards against leaked escalation: routing code must never import or call graders / gold / unit tests."""
import ast
import random
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tierroute.providers import LLMResult
from tierroute.strategies import ESCALATING, run_strategy
from tierroute.verifiers import REGISTRY, Ctx

FORBIDDEN_MODULE_PARTS = ("evaluation", "grading", "benchmark", "scratch")
FORBIDDEN_TOKENS = ("test_code", "grade_task", "grade_numeric", "grade_code", "grade_robust", "gold")
ROUTING_FILES = sorted((ROOT / "tierroute").glob("*.py"))


def test_routing_modules_do_not_import_grading_code():
    bad = []
    for f in ROUTING_FILES:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "")] + [a.name for a in node.names]
            for m in mods:
                if any(p in m.lower().split(".") or p in m.lower() for p in FORBIDDEN_MODULE_PARTS):
                    bad.append((f.name, m))
    assert not bad, f"routing modules import grading/benchmark code: {bad}"


def test_routing_modules_never_reference_gold_or_tests_in_code():
    # Identifier/attribute/string-literal level (comments and docstrings may talk about gold).
    # providers.py is the mock *model* simulator and may read meta['answer']; classifier*.py read prompts for training.
    offenders = []
    for f in ROUTING_FILES:
        if f.name in ("providers.py", "classifier.py", "classifier_v2.py"):
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 40:
                names = [node.value]
            offenders += [(f.name, n) for n in names if any(t in n.lower() for t in FORBIDDEN_TOKENS)]
    assert not offenders, offenders


class _Poison:
    def __getattr__(self, name):
        raise AssertionError(f"grader touched during routing: {name}")


PROMPTS = [
    "Solve the following math word problem step by step. Provide your final numerical answer on the last line "
    "strictly in the format 'Answer: X'.\n\nProblem: What is 2+3?",
    "Write a Python function to add two numbers.\nTask: add\nassert add(1, 2) == 3\n"
    "Provide your code inside a ```python ... ``` block.",
    "Extract the id from 'ID: 5'. Provide your final answer on the last line as 'Answer: <id>'.",
]


def _ctx(good_from_tier):
    def gen(tier, prompt, sample=0, temperature=0.0, judge=False):
        if judge:
            return LLMResult('{"confidence": 0.1}', 10, 5, 0.01)
        if tier >= good_from_tier:
            txt = "```python\ndef add(a, b):\n    return a + b\n```" if "```python" in prompt else "Answer: 5"
        else:
            txt = "I'm not sure."
        return LLMResult(txt, 20, 10, 0.01, finish_reason="stop")
    return Ctx(gen, lambda tier, r: 1e-6 * (tier + 1))


class _Clf:
    def predict(self, prompt, bias=0.5):
        return {"tier": 1}


@pytest.mark.parametrize("vname", list(REGISTRY))
@pytest.mark.parametrize("strategy", ["always_strong", "always_cheap", "random", "cascade", "rules", "classifier"])
def test_all_strategies_run_with_graders_poisoned(monkeypatch, strategy, vname):
    for mod in ("evaluation", "evaluation.grading_v2", "evaluation.grading_robust"):
        monkeypatch.setitem(sys.modules, mod, _Poison())
    verifier = REGISTRY[vname]()
    for p in PROMPTS:
        out = run_strategy(strategy, p, _ctx(good_from_tier=1), verifier, rnd=random.Random(1), classifier=_Clf())
        assert out.attempts
        if strategy in ESCALATING and out.first_tier == 0:
            assert out.escalated  # tier-0 draft is junk -> a gold-free verifier must still escalate it


def test_verifier_signature_has_no_task_or_gold_argument():
    import inspect
    from tierroute.verifiers import Verifier
    assert list(inspect.signature(Verifier.check).parameters) == ["self", "prompt", "res", "tier", "ctx"]
