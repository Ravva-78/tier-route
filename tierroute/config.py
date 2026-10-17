import os
from dataclasses import dataclass
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file():
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k not in os.environ or not os.environ[k]:
                        os.environ[k] = v
        except Exception:
            pass


_load_env_file()


@dataclass
class ModelSpec:
    name: str
    tier: int
    base_url: str
    model: str
    api_key_env: str = ""
    price_in_per_m: float = 0.0
    price_out_per_m: float = 0.0
    capability: float = 0.5  # used by mock mode only

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.price_in_per_m + tokens_out * self.price_out_per_m) / 1_000_000


@dataclass
class Config:
    mode: str
    default_bias: float
    models: list


def load_config(path=None) -> Config:
    _load_env_file()
    path = Path(path or os.getenv("TIERROUTE_CONFIG", ROOT / "config" / "models.yaml"))
    raw = yaml.safe_load(path.read_text())
    models = sorted((ModelSpec(**m) for m in raw["models"]), key=lambda m: m.tier)

    # Allow local model's base_url to be overridden via environment variable (e.g. for Colab/Kaggle tunnels)
    local_url_override = os.getenv("TIERROUTE_LOCAL_BASE_URL") or os.getenv("LOCAL_MODEL_BASE_URL")
    if local_url_override:
        for m in models:
            if m.tier == 0:
                m.base_url = local_url_override.strip()

    mode = os.getenv("TIERROUTE_MODE", raw.get("mode", "mock"))
    return Config(mode, float(raw.get("default_quality_bias", 0.5)), models)

