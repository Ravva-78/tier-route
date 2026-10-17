"""Routing strategies as pure functions of (prompt, model outputs). No grader, gold or tests in here.

choose_first_tier: where a strategy starts, from the prompt only.
run_ladder: call a tier, ask the verifier, climb one tier on failure.
"""
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .analyzer import analyze
from .verifiers import Ctx, Verdict, Verifier

# Tuned on the v2 DEV set (unchanged); used by the benchmark. The live app keeps its own BASE_THRESHOLDS.
V2_THRESHOLDS = (0.50, 0.74)
ESCALATING = ("cascade", "rules", "classifier")


def choose_first_tier(strategy: str, prompt: str, *, bias: float = 0.5, n_tiers: int = 3, rnd=None,
                      classifier=None, thresholds=V2_THRESHOLDS) -> int:
    if strategy == "always_strong":
        return n_tiers - 1
    if strategy in ("always_cheap", "cascade"):
        return 0
    if strategy == "random":
        return rnd.randint(0, n_tiers - 1)
    if strategy == "rules":
        shift = (bias - 0.5) * 0.5
        score = analyze(prompt)["score"]
        return sum(1 for th in thresholds if score >= th - shift)
    if strategy == "classifier":
        return classifier.predict(prompt, bias=bias)["tier"]
    raise ValueError(f"unknown strategy {strategy}")


@dataclass
class Attempt:
    tier: int
    res: object
    verdict: Verdict
    cost: float = 0.0  # model cost + verifier extra cost
    latency_s: float = 0.0


@dataclass
class Outcome:
    first_tier: int
    attempts: List[Attempt] = field(default_factory=list)

    @property
    def final(self) -> Attempt:
        return self.attempts[-1]

    @property
    def cost(self) -> float:
        return sum(a.cost for a in self.attempts)

    @property
    def latency_s(self) -> float:
        return sum(a.latency_s for a in self.attempts)

    @property
    def escalated(self) -> bool:
        return len(self.attempts) > 1


def run_ladder(first_tier: int, prompt: str, ctx: Ctx, verifier: Optional[Verifier], *, escalate: bool,
               max_tier: int = 2) -> Outcome:
    out, tier = Outcome(first_tier), first_tier
    while True:
        res = ctx.generate(tier, prompt)
        cost, lat = ctx.cost(tier, res), res.latency_s
        if verifier is not None:
            v = verifier.check(prompt, res, tier, ctx)
            cost, lat = cost + v.cost, lat + v.latency_s
        else:
            v = Verdict(True, "not_checked")
        out.attempts.append(Attempt(tier, res, v, cost, lat))
        if v.ok or not escalate or tier >= max_tier:
            return out
        tier += 1


def run_strategy(strategy: str, prompt: str, ctx: Ctx, verifier: Optional[Verifier], *, bias=0.5, rnd=None,
                 classifier=None) -> Outcome:
    first = choose_first_tier(strategy, prompt, bias=bias, rnd=rnd, classifier=classifier)
    return run_ladder(first, prompt, ctx, verifier, escalate=strategy in ESCALATING)
