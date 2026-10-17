"""Cached live model access for benchmarks. Every distinct call (tier, sample, settings, prompt) is made once, for real,
and stored; strategies that need the same draft therefore share one real sample (identical to a replay).
Nothing is ever filled in by hand: a failed call (e.g. Groq HTTP 429, incl. the 200k tokens/day cap) is retried with long backoff until it succeeds,
and an error is never written to the cache."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tierroute.providers import LLMResult, Provider  # noqa: E402
from tierroute.verifiers import Ctx  # noqa: E402

PROBLEM_LOG = Path("results/final/problems.log")


def log_problem(msg: str):
    PROBLEM_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROBLEM_LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


class CachedLive:
    def __init__(self, cfg, cache_path, hosted_max_tokens=4096, hosted_extra=None, local_max_tokens=1024,
                 retries=100000, wait_s=60):
        self.specs = {m.tier: m for m in cfg.models}
        self.providers = {t: Provider(m, mode="live") for t, m in self.specs.items()}
        self.path, self.hmt, self.hx, self.lmt = Path(cache_path), hosted_max_tokens, hosted_extra, local_max_tokens
        self.retries, self.wait_s = retries, wait_s
        self.cache = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.live_calls = 0

    def _key(self, tier, prompt, sample, temperature, judge):
        mt, ex = (self.lmt, None) if tier == 0 else (self.hmt, self.hx)
        raw = f"{tier}|{sample}|{int(judge)}|{temperature}|{mt}|{json.dumps(ex, sort_keys=True)}|{prompt}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def generate(self, tier, prompt, sample=0, temperature=0.0, judge=False):
        if judge:
            temperature = 0.0
        k = self._key(tier, prompt, sample, temperature, judge)
        if k in self.cache:
            return LLMResult(**self.cache[k])
        mt, ex = (self.lmt, None) if tier == 0 else (self.hmt, self.hx)
        for attempt in range(self.retries):
            res = self.providers[tier].generate(prompt, max_tokens=mt, temperature=temperature, extra_body=ex)
            self.live_calls += 1
            if not res.error:
                break
            if attempt % 5 == 0:  # Groq free tier: 200k tokens/day per model (rolling window) -> long waits are expected
                log_problem(f"tier {tier} call failed (attempt {attempt + 1}): {res.error[:120]}")
            time.sleep(self.wait_s if "429" in res.error else 15)
        else:
            raise RuntimeError(f"tier {tier} call kept failing: {res.error}")
        self.cache[k] = dict(text=res.text, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                             latency_s=res.latency_s, error=None, finish_reason=res.finish_reason)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)
        if tier > 0:
            time.sleep(0.5)
        return res

    def ctx(self) -> Ctx:
        return Ctx(self.generate, lambda tier, r: self.specs[tier].cost(r.tokens_in, r.tokens_out))
