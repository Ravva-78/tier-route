"""One provider class: every endpoint (Ollama, Groq, Gemini, OpenRouter, Colab tunnel)
speaks the OpenAI-compatible /chat/completions API, so swapping models is a config change."""
import hashlib
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_s: float
    error: Optional[str] = None
    finish_reason: Optional[str] = "stop"


def est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


MOCK_LATENCY = {0: 0.9, 1: 0.5, 2: 1.6}


class Provider:
    def __init__(self, spec, mode: str):
        self.spec = spec
        self.mode = mode

    def generate(self, prompt, system=None, max_tokens=1024, temperature=0.2, meta=None, extra_body=None) -> LLMResult:
        if self.mode == "mock":
            return self._mock(prompt, meta)
        return self._live(prompt, system, max_tokens, temperature, extra_body=extra_body)


    # --- mock: only for testing the router logic offline; results are SIMULATED ---
    def _mock(self, prompt, meta):
        meta = meta or {}
        difficulty = float(meta.get("difficulty", 0.5))
        gold = meta.get("answer")
        if gold is not None and self.spec.capability >= difficulty:
            text = str(gold)
        else:
            style = meta.get("wrong_style")  # "unsure" | "confident" | None (random but repeatable)
            if style is None:
                h = int(hashlib.md5((prompt + self.spec.name).encode()).hexdigest(), 16)
                style = "unsure" if h % 2 == 0 else "confident"
            text = "I'm not sure about this one." if style == "unsure" else "The answer is 42."
        t_in, t_out = est_tokens(prompt), est_tokens(text) + 20
        return LLMResult(text, t_in, t_out, MOCK_LATENCY.get(self.spec.tier, 1.0) + 0.002 * t_out)

    # --- live ---
    def _live(self, prompt, system, max_tokens, temperature, extra_body=None) -> LLMResult:
        key = os.getenv(self.spec.api_key_env, "") if self.spec.api_key_env else ""
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.spec.model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        if extra_body:
            body.update(extra_body)
        url = self.spec.base_url.rstrip("/") + "/chat/completions"
        is_local = "localhost" in url or "127.0.0.1" in url
        if is_local:
            timeout_s = httpx.Timeout(120.0, connect=5.0)
        else:
            timeout_s = httpx.Timeout(45.0, connect=10.0)
        t0 = time.time()

        err = None
        max_attempts = 1 if is_local else 4

        for attempt in range(max_attempts):
            try:
                r = httpx.post(url, json=body, headers=headers, timeout=timeout_s, verify=False)
                # Rate limit (429) backoff handling
                if r.status_code == 429:
                    if attempt < max_attempts - 1:
                        retry_after = r.headers.get("retry-after")
                        try:
                            wait_s = float(retry_after) if retry_after else float(2 ** (attempt + 1))
                        except ValueError:
                            wait_s = float(2 ** (attempt + 1))
                        wait_s = min(max(wait_s, 1.5), 15.0)
                        time.sleep(wait_s)
                        continue
                    else:
                        err = f"HTTP 429: Rate limit exceeded after {max_attempts} attempts"
                        break

                r.raise_for_status()
                d = r.json()
                choice = d.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content") or ""
                finish_reason = choice.get("finish_reason") or "stop"
                u = d.get("usage") or {}
                if not is_local:
                    time.sleep(0.2)
                return LLMResult(
                    text=text,
                    tokens_in=u.get("prompt_tokens") or est_tokens(prompt),
                    tokens_out=u.get("completion_tokens") or est_tokens(text),
                    latency_s=time.time() - t0,
                    error=None,
                    finish_reason=finish_reason
                )
            except (httpx.ConnectError, httpx.ConnectTimeout):
                err = f"Connection failed to {url}. Endpoint may be offline."
                break
            except httpx.TimeoutException:
                err = f"Request timed out after {timeout_s}s at {url}"
                if attempt < 2 and not is_local:
                    time.sleep(1.0)
                    continue
                break
            except Exception as e:  # noqa: BLE001
                err = f"Provider error: {type(e).__name__} - {str(e)[:160]}"
                break

        return LLMResult(
            text="",
            tokens_in=est_tokens(prompt),
            tokens_out=0,
            latency_s=time.time() - t0,
            error=err,
            finish_reason="error"
        )


