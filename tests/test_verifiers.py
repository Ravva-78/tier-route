import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tierroute.answers import final_answer, prompt_examples
from tierroute.providers import LLMResult
from tierroute.verifiers import Ctx, JudgeVerifier, SelfConsistencyVerifier, StrictFormatVerifier

HE = 'Complete the following Python function.\n\n```python\ndef inc(x):\n    """Add one.\n    inc(1) ==> 2\n    inc(5) == 6\n    >>> inc(0)\n    1\n    """\n```\n\nProvide your code inside a ```python ... ``` block.'
MBPP = "Write a function that doubles.\nYour code should pass this test:\nassert dbl(2) == 4\nProvide your code inside a ```python ... ``` block."
MATH = "Solve. Provide the final line as 'Answer: X'.\nProblem: 1+1"


def R(text, fr="stop"):
    return LLMResult(text, 5, 5, 0.1, finish_reason=fr)


def test_prompt_examples_only_from_prompt():
    fn, a = prompt_examples(HE)
    assert fn == "inc" and len(a) == 3
    fn, a = prompt_examples(MBPP)
    assert fn == "dbl" and a == ["assert dbl(2) == 4"]


def test_strict_runs_prompt_examples():
    v = StrictFormatVerifier()
    good = R("```python\ndef inc(x):\n    return x + 1\n```")
    bad = R("```python\ndef inc(x):\n    return x + 2\n```")
    assert v.check(HE, good, 0).ok
    assert v.check(HE, bad, 0).reason == "example_fail"
    assert v.check(HE, R("```python\ndef inc(:\n```"), 0).reason == "python_parse_failure"
    assert v.check(MBPP, R("```python\ndef double(x): return 2*x\n```"), 0).reason == "example_fail"  # wrong name


def test_strict_format_and_length():
    v = StrictFormatVerifier()
    assert v.check(MATH, R("so it is 2"), 0).reason == "missing_Answer_format"
    assert v.check(MATH, R("Answer: 2", "length"), 0).reason == "finish_reason=length"
    assert v.check(MATH, R(""), 0).reason == "empty"
    assert v.check(MATH, R("**Answer: 2**"), 0).ok


def _ctx(texts, judge_text='{"confidence": 0.9}'):
    it = iter(texts)

    def gen(tier, prompt, sample=0, temperature=0.0, judge=False):
        return R(judge_text) if judge else R(next(it))
    return Ctx(gen, lambda t, r: 0.001)


def test_self_consistency():
    v = SelfConsistencyVerifier(min_agree=2)
    assert v.check(MATH, R("Answer: 2"), 0, _ctx(["Answer: 2", "Answer: 3"])).ok
    assert not v.check(MATH, R("Answer: 2"), 0, _ctx(["Answer: 3", "Answer: 4"])).ok
    assert not SelfConsistencyVerifier(min_agree=3).check(MATH, R("Answer: 2"), 0, _ctx(["Answer: 2", "Answer: 3"])).ok
    assert final_answer(MATH, "**Answer: 1,000.**") == "1000"


def test_judge_threshold_and_cost():
    v = JudgeVerifier(threshold=0.7)
    ok = v.check(MATH, R("Answer: 2"), 0, _ctx([], '{"confidence": 0.9}'))
    low = v.check(MATH, R("Answer: 2"), 0, _ctx([], '{"confidence": 0.3}'))
    assert ok.ok and not low.ok and low.cost == 0.001
