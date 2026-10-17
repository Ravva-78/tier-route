"""Strategy evaluation core. Routing is done by tierroute.strategies (prompt-only); grading is applied afterwards,
to the final answer only, and never feeds back. Shared by DEV verifier selection and the final v3 run."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tierroute.strategies import run_strategy  # noqa: E402
from evaluation.grading_robust import grade_robust  # noqa: E402  (evaluation only)
from evaluation.grading_v2 import grade_task_v2  # noqa: E402  (evaluation only)

STRATEGIES = ["always_strong", "always_cheap", "random", "cascade", "rules", "classifier"]
NO_VERIFIER = ("always_strong", "always_cheap", "random")


def evaluate(tasks, strategy, verifier, ctx, classifier=None, bias=0.5, seed=42):
    """Returns one row per task. The random baseline uses its own seeded stream (same as v2)."""
    rnd, rows = random.Random(seed), []
    for t in tasks:
        v = None if strategy in NO_VERIFIER else verifier
        out = run_strategy(strategy, t["prompt"], ctx, v, bias=bias, rnd=rnd, classifier=classifier)
        text, fin = out.final.res.text, out.final
        rows.append(dict(
            task_id=t["id"], strategy=strategy, bias=bias, first_tier=out.first_tier, final_tier=fin.tier,
            escalated=int(out.escalated), attempts=len(out.attempts), cost=out.cost, latency_s=out.latency_s,
            tokens_out=sum(a.res.tokens_out for a in out.attempts), finish_reason=fin.res.finish_reason,
            verdict=fin.verdict.reason, correct_orig=int(grade_task_v2(t, text)[0]),
            correct_robust=int(grade_robust(t, text)[0])))
    return rows


def summarize(rows, key="correct_robust"):
    n = len(rows)
    lat = sorted(r["latency_s"] for r in rows)
    return dict(n=n, quality=sum(r[key] for r in rows), cost=sum(r["cost"] for r in rows),
                escalations=sum(r["escalated"] for r in rows),
                workload=[sum(1 for r in rows if r["final_tier"] == k) for k in (0, 1, 2)],
                mean_latency=sum(lat) / n, median_latency=(lat[(n - 1) // 2] + lat[n // 2]) / 2)
