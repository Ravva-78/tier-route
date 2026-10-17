import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from tierroute.analyzer import TASK_TYPES
from tierroute.config import ROOT, load_config
from tierroute.router import Overrides, Router
from tierroute.store import Store
from tierroute.verifiers import REGISTRY

cfg = load_config()
store = Store(ROOT / "results" / "decisions.db")
overrides = Overrides(ROOT / "results" / "overrides.json")
router = Router(cfg, store, overrides, verifier=REGISTRY[cfg.verifier["name"]](**cfg.verifier.get("params", {})))
app = FastAPI(title="TierRoute API Gateway", version="1.0.0")


class RouteReq(BaseModel):
    prompt: str
    bias: Optional[float] = None
    force_model: Optional[str] = None
    split: bool = True
    strategy: Optional[str] = "rules"


class OpenAIChatMessage(BaseModel):
    role: str
    content: str


class OpenAIChatCompletionReq(BaseModel):
    model: Optional[str] = "tierroute"
    messages: List[OpenAIChatMessage]
    temperature: Optional[float] = 0.2
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False


class OverrideReq(BaseModel):
    global_pin: Optional[str] = None
    task_rules: Optional[dict] = None
    bias: Optional[float] = None


@app.get("/")
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/api/route")
def route(req: RouteReq):
    return router.route(req.prompt, bias=req.bias, force_model=req.force_model or None,
                        split=req.split, strategy=req.strategy or "rules")


@app.post("/v1/chat/completions")
def chat_completions(req: OpenAIChatCompletionReq):
    """OpenAI-compatible drop-in proxy endpoint for enterprise client libraries."""
    prompt = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    force = req.model if req.model in router.by_name else None
    out = router.route(prompt, force_model=force, split=True, strategy="rules")
    
    total_tokens_in = sum(p["tokens_in"] for p in out["parts"])
    total_tokens_out = sum(p["tokens_out"] for p in out["parts"])
    savings = round(100 * (1 - out["total_cost"] / out["est_strong_cost"]), 1) if out["est_strong_cost"] > 0 else 0.0

    return {
        "id": f"chatcmpl-{out['request_id']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": out["parts"][-1]["final_model"] if out["parts"] else "tierroute",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": out["answer"]},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": total_tokens_in,
            "completion_tokens": total_tokens_out,
            "total_tokens": total_tokens_in + total_tokens_out
        },
        "tierroute_meta": {
            "cost_usd": out["total_cost"],
            "saved_vs_strong_pct": savings,
            "parts_routed": out["n_parts"],
            "escalated": any(p["escalated"] for p in out["parts"]),
            "tiers_used": [p["tier"] for p in out["parts"]]
        }
    }


@app.get("/api/models")
def models():
    return {"mode": cfg.mode, "task_types": TASK_TYPES, "default_bias": cfg.default_bias,
            "models": [{"name": m.name, "tier": m.tier, "model": m.model,
                        "price_in_per_m": m.price_in_per_m, "price_out_per_m": m.price_out_per_m}
                       for m in cfg.models]}


@app.get("/api/logs")
def logs(limit: int = 40):
    return store.recent(limit)


@app.get("/api/stats")
def stats():
    return store.stats()


@app.get("/api/overrides")
def get_overrides():
    return overrides.data


@app.post("/api/overrides")
def set_overrides(req: OverrideReq):
    return overrides.update(req.model_dump(exclude_unset=True))


@app.post("/api/reset")
def reset():
    store.clear()
    return {"ok": True}
