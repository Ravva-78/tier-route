"""TierRoute core: analyse -> split -> pick tier -> call -> verify -> escalate -> merge -> log."""
import json
import random
import time
import uuid
from pathlib import Path

from .analyzer import analyze, TASK_TYPES
from .classifier import classifier
from .merger import merge
from .providers import Provider
from .splitter import split_request
from .strategies import ESCALATING, run_ladder
from .verifiers import Ctx, HeuristicVerifier

SYSTEM = "Answer concisely and directly. Follow any requested output format exactly."
# Tier cut-offs on the 0..1 complexity score (tier 0|1 and tier 1|2).
# Tuned strictly on the 70% dev set (yielding 87.2% accuracy on dev). Held-out test set is unobserved.
BASE_THRESHOLDS = (0.14, 0.32)




class Overrides:
    """Admin controls, persisted to a JSON file so they survive restarts."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"global_pin": None, "task_rules": {}, "bias": None}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except Exception:  # noqa: BLE001
                pass

    def update(self, new: dict):
        for k in ("global_pin", "task_rules", "bias"):
            if k in new:
                self.data[k] = new[k]
        self.path.write_text(json.dumps(self.data, indent=2))
        return self.data


class Router:
    def __init__(self, cfg, store, overrides, verifier=None):
        self.cfg, self.store, self.overrides = cfg, store, overrides
        self.verifier = verifier or HeuristicVerifier()  # gold-free; see tierroute/verifiers.py
        self.models = cfg.models
        self.by_name = {m.name: m for m in self.models}
        self.index = {m.name: i for i, m in enumerate(self.models)}
        self.providers = {m.name: Provider(m, cfg.mode) for m in self.models}
        self.strong = self.models[-1]

    # tier choice: higher quality_bias lowers the thresholds, so more work goes to stronger tiers
    def tier_for(self, score: float, bias: float) -> int:
        shift = (bias - 0.5) * 0.5
        n = len(self.models)
        thresholds = [BASE_THRESHOLDS[0] + i * (BASE_THRESHOLDS[1] - BASE_THRESHOLDS[0]) - shift for i in range(n - 1)]
        return sum(1 for t in thresholds if score >= t)

    def _choose(self, feat, bias, force_model, strategy, text=""):
        ov = self.overrides.data
        n = len(self.models)
        if force_model in self.by_name:
            return self.index[force_model], f"user pinned model '{force_model}'", "user", True, feat["score"]
        if ov.get("global_pin") in self.by_name:
            return self.index[ov["global_pin"]], f"admin pinned all traffic to '{ov['global_pin']}'", "admin", True, feat["score"]
        rule = (ov.get("task_rules") or {}).get(feat["task_type"])
        if rule in self.by_name:
            return self.index[rule], f"admin rule: {feat['task_type']} -> '{rule}'", "admin", True, feat["score"]
        if strategy == "always_strong":
            return n - 1, "baseline: always strongest", None, False, 1.0
        if strategy == "always_cheap":
            return 0, "baseline: always cheapest", None, False, 0.0
        if strategy == "cascade":
            return 0, "cascade: start at cheapest, escalate on failed verification", None, False, 0.0
        if strategy == "random":
            return random.randrange(n), "baseline: random", None, False, 0.5
        if strategy == "classifier":
            clf_res = classifier.predict(text, bias=bias)
            idx = min(n - 1, max(0, clf_res["tier"]))
            why = (f"ML classifier: tier {idx} (confidence {clf_res['confidence']:.2f}, "
                   f"P(T0)={clf_res['probabilities']['tier_0']}, P(T1)={clf_res['probabilities']['tier_1']}, "
                   f"P(T2)={clf_res['probabilities']['tier_2']}) at bias {bias:.2f}")
            return idx, why, None, False, clf_res["score"]

        idx = self.tier_for(feat["score"], bias)
        why = (f"{feat['task_type']} task, complexity {feat['score']:.2f} -> tier {idx} "
               f"at quality bias {bias:.2f} ({feat['signals']})")
        return idx, why, None, False, feat["score"]

    def _handle_part(self, rid, i, text, bias, force_model, strategy, meta, temperature=0.2, max_tokens=4096, verifier=None):
        feat = analyze(text)
        idx, reason, override_by, locked, score_used = self._choose(feat, bias, force_model, strategy, text=text)
        first_idx = idx

        def gen(tier, prompt, sample=0, temperature=temperature, judge=False):
            m = self.models[tier]
            kw = {"max_tokens": max_tokens, "temperature": temperature}
            if judge:  # reasoning judge needs room to think, same settings as the benchmark (see benchmark/live_ctx.py)
                kw.update(max_tokens=4096, temperature=0.0, extra_body={"reasoning_effort": "low"})
            if tier > 0 and not judge:  # same hosted settings as the evaluated configuration (reasoning models need token room)
                kw.update(extra_body={"reasoning_effort": "low"})
            if not judge and not sample:
                kw.update(system=SYSTEM, meta=meta)
            return self.providers[m.name].generate(prompt, **kw)

        ctx = Ctx(gen, lambda tier, r: self.models[tier].cost(r.tokens_in, r.tokens_out))
        outcome = run_ladder(idx, text, ctx, verifier or self.verifier,
                             escalate=(not locked) and strategy in ESCALATING, max_tier=len(self.models) - 1)
        attempts, total_cost, total_lat = [], outcome.cost, outcome.latency_s
        for a in outcome.attempts:
            m, r = self.models[a.tier], a.res
            attempts.append({"model": m.name, "tier": m.tier, "ok": a.verdict.ok, "check": a.verdict.reason,
                             "cost": a.cost, "latency_s": round(a.latency_s, 3), "tokens_in": r.tokens_in,
                             "tokens_out": r.tokens_out, "finish_reason": r.finish_reason})
        res = outcome.final.res
        last = attempts[-1]
        row = {
            "request_id": rid, "ts": time.time(), "part_idx": i, "part_text": text,
            "task_type": feat["task_type"], "score": score_used, "strategy": strategy,
            "first_model": self.models[first_idx].name, "final_model": last["model"], "tier": last["tier"],
            "reason": reason + ("" if len(attempts) == 1 else
                                " | escalated: " + " -> ".join(f"{a['model']} ({a['check']})" for a in attempts)),
            "tokens_in": sum(a["tokens_in"] for a in attempts), "tokens_out": sum(a["tokens_out"] for a in attempts),
            "cost": total_cost, "est_strong_cost": self.strong.cost(res.tokens_in, res.tokens_out),
            "latency_s": total_lat, "escalated": int(len(attempts) > 1), "verified": int(last["ok"]),
            "finish_reason": last.get("finish_reason", "stop"),
            "truncated": int(last.get("finish_reason") == "length"),
            "override_by": override_by, "attempts": attempts,
        }
        return row, res.text, first_idx

    def route(self, prompt, bias=None, force_model=None, split=True, strategy="rules", meta=None, log=True, temperature=0.2, max_tokens=4096, verifier=None):
        rid = uuid.uuid4().hex[:8]
        ov_bias = self.overrides.data.get("bias")
        if bias is None:
            bias = ov_bias if ov_bias is not None else self.cfg.default_bias
        parts = split_request(prompt) if split else [prompt.strip()]
        if isinstance(meta, list) and len(meta) == len(parts):
            metas = meta
        else:
            metas = [meta if isinstance(meta, dict) else None] * len(parts)
        rows, answers, first_idxs = [], [], []
        for i, p in enumerate(parts):
            row, ans, fi = self._handle_part(rid, i, p, bias, force_model, strategy, metas[i], temperature=temperature, max_tokens=max_tokens, verifier=verifier)
            rows.append(row)
            answers.append(ans)
            first_idxs.append(fi)

        if log:
            self.store.log(rows)
        return {
            "request_id": rid, "answer": merge(parts, answers), "n_parts": len(parts),
            "parts": [{**r, "answer": a, "first_tier": fi} for r, a, fi in zip(rows, answers, first_idxs)],
            "total_cost": sum(r["cost"] for r in rows),
            "est_strong_cost": sum(r["est_strong_cost"] for r in rows),
            "total_latency_s": sum(r["latency_s"] for r in rows),
            "mode": self.cfg.mode,
        }
