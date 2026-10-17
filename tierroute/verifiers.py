"""Deployable, gold-free verifiers behind one interface.

check(prompt, res, tier, ctx) -> Verdict. A verifier sees ONLY the prompt, the model output
(text / finish_reason / error) and, via ctx, the ability to call models. It never sees gold answers,
graders or unit tests. Escalation happens when Verdict.ok is False.

Extra model calls made by a verifier (self-consistency samples, judge) are returned in
Verdict.cost / Verdict.latency_s so they are charged to the strategy.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from .analyzer import detect_task
from .answers import (extract_code, final_answer, is_code_prompt, prompt_examples,
                      wants_answer_format)
from .verifier import UNSURE, verify as heuristic_verify


@dataclass
class Verdict:
    ok: bool
    reason: str
    cost: float = 0.0
    latency_s: float = 0.0


@dataclass
class Ctx:
    """Model access for verifiers. generate(tier, prompt, **kw) -> LLMResult; cost(tier, res) -> USD."""
    generate: Callable
    cost: Callable


class Verifier:
    name = "base"

    def check(self, prompt, res, tier: int, ctx: Optional[Ctx] = None) -> Verdict:  # pragma: no cover
        raise NotImplementedError


class HeuristicVerifier(Verifier):
    """(a) the original sanity check in tierroute/verifier.py."""
    name = "heuristic"

    def check(self, prompt, res, tier, ctx=None):
        ok, why = heuristic_verify(prompt, res.text, detect_task(prompt.lower()), res.error)
        return Verdict(ok, why)


def run_examples(code: str, asserts, timeout: float = 5.0):
    """Run model code against example asserts taken from the prompt. Subprocess + timeout only
    (no memory/filesystem isolation). Returns (ok, reason)."""
    if not asserts:
        return True, "no_examples"
    script = "import sys\n" + code + "\n" + "\n".join(asserts) + "\nprint('__EX_OK__')\n"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ex.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        try:
            p = subprocess.run([sys.executable, "-I", path], capture_output=True, timeout=timeout, text=True, cwd=d)
        except subprocess.TimeoutExpired:
            return False, "example_timeout"
    if p.returncode == 0 and "__EX_OK__" in p.stdout:
        return True, "examples_pass"
    return False, "example_fail"


class StrictFormatVerifier(Verifier):
    """(b) Answer: format, finish_reason != length, code parses and passes the examples shown in the prompt."""
    name = "strict"

    def check(self, prompt, res, tier, ctx=None):
        if res.error:
            return Verdict(False, "provider_error")
        text = res.text or ""
        if not text.strip():
            return Verdict(False, "empty")
        if res.finish_reason == "length":
            return Verdict(False, "finish_reason=length")
        if is_code_prompt(prompt):
            code = extract_code(text)
            try:
                ast.parse(code)
            except (SyntaxError, ValueError):
                return Verdict(False, "python_parse_failure")
            _, asserts = prompt_examples(prompt)
            ok, why = run_examples(code, asserts)
            return Verdict(ok, why)
        if wants_answer_format(prompt) and not re.search(r"answer\s*:", text, re.I):
            return Verdict(False, "missing_Answer_format")
        return Verdict(True, "ok")


class SelfConsistencyVerifier(Verifier):
    """(c) Draft from the local tier is re-sampled (2 extra samples at T=0.7, so 3 samples in total).
    Escalate unless >= min_agree samples share the same final answer and that answer is non-empty.
    Applies to tier-0 drafts; drafts from hosted tiers fall back to the strict-format check."""
    name = "self_consistency"

    def __init__(self, min_agree: int = 2, n_extra: int = 2, temperature: float = 0.7):
        self.min_agree, self.n_extra, self.temperature = min_agree, n_extra, temperature
        self.fallback = StrictFormatVerifier()

    def check(self, prompt, res, tier, ctx=None):
        first = self.fallback.check(prompt, res, tier)
        if tier != 0 or ctx is None:
            return first
        if not first.ok:
            return first
        answers, lat = [final_answer(prompt, res.text)], 0.0
        for i in range(self.n_extra):
            r = ctx.generate(0, prompt, sample=i + 1, temperature=self.temperature)
            lat += r.latency_s
            answers.append(final_answer(prompt, r.text) if not r.error else "")
        best = max((answers.count(a), a) for a in set(answers))
        if best[1] == "":
            return Verdict(False, "majority_empty_or_malformed", 0.0, lat)
        if best[0] < self.min_agree:
            return Verdict(False, f"disagree({best[0]}/{len(answers)})", 0.0, lat)
        return Verdict(True, f"agree({best[0]}/{len(answers)})", 0.0, lat)


JUDGE_RUBRIC = (
    "You are a strict grader of answers you cannot check against a key. Below is a TASK and a DRAFT ANSWER.\n"
    "Judge only whether the draft is correct and complete and follows the requested output format.\n"
    "Be skeptical: arithmetic slips, wrong function names, missing 'Answer:' line, hedging, and unverified "
    "guesses lower your confidence.\n"
    "Reply with ONLY a JSON object: {\"confidence\": <number between 0 and 1>} where 1 means certainly correct.\n\n"
    "=== TASK ===\n{prompt}\n\n=== DRAFT ANSWER ===\n{draft}\n"
)


class JudgeVerifier(Verifier):
    """(d) The mid model rates a tier-0 draft (confidence 0-1) with a fixed rubric; escalate below threshold.
    Judge cost is charged to the strategy. Hosted-tier drafts fall back to strict-format."""
    name = "judge"

    def __init__(self, threshold: float = 0.7, judge_tier: int = 1):
        self.threshold, self.judge_tier = threshold, judge_tier
        self.fallback = StrictFormatVerifier()

    def check(self, prompt, res, tier, ctx=None):
        if tier != 0 or ctx is None:
            return self.fallback.check(prompt, res, tier)
        if res.error or not (res.text or "").strip():
            return Verdict(False, "empty")
        jp = JUDGE_RUBRIC.replace("{prompt}", prompt).replace("{draft}", res.text[:6000])
        jr = ctx.generate(self.judge_tier, jp, judge=True)
        cost = ctx.cost(self.judge_tier, jr)
        m = re.search(r'"confidence"\s*:\s*([0-9]*\.?[0-9]+)', jr.text or "") or re.search(r"\b(0?\.\d+|1(?:\.0+)?|0)\b", jr.text or "")
        conf = min(1.0, float(m.group(1))) if m else 0.0
        return Verdict(conf >= self.threshold, f"judge_conf={conf:.2f}", cost, jr.latency_s)


def judge_confidence_from_verdict(v: Verdict) -> Optional[float]:
    m = re.match(r"judge_conf=([0-9.]+)", v.reason)
    return float(m.group(1)) if m else None


REGISTRY = {"heuristic": HeuristicVerifier, "strict": StrictFormatVerifier,
            "self_consistency": SelfConsistencyVerifier, "judge": JudgeVerifier}
# (e) Jev (OpenRouter typesafe/jev-1.13) is intentionally absent: needs OPENROUTER_API_KEY + docs access; see report.
