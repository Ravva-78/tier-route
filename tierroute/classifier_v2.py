"""Supervised ML Classifier for Benchmark V2.
Trained strictly on SEED_TRAINING_DATA plus the 60 DEV tasks with their oracle tier labels.
Held-out test set prompts are validated with check_no_leakage to ensure zero leakage.
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from tierroute.classifier import SEED_TRAINING_DATA

ROOT = Path(__file__).resolve().parent.parent


def strip_benchmark_boilerplate(p: str) -> str:
    """Isolate core problem statement from standardized benchmark instruction wrappers."""
    p = re.sub(r"Solve the following math word problem step by step\. Provide your final numerical answer on the last line strictly in the format 'Answer: X'\.\s*Problem:\s*", "", p)
    p = re.sub(r"Answer the following multiple-choice science question\. Provide your final choice letter on the last line strictly in the format 'Answer: X'\.\s*", "", p)
    p = re.sub(r"Write a Python function to solve the following task\.\s*Task:\s*", "", p)
    p = re.sub(r"Complete the following Python function definition according to its docstring\.\s*", "", p)
    p = re.sub(r"Your code should be complete, correct, and self-contained\. Provide your code inside a ```python \.\.\. ``` block\.", "", p)
    p = re.sub(r"Provide your complete function code inside a ```python \.\.\. ``` block\.", "", p)
    p = re.sub(r"Provide your final answer on the last line as 'Answer: [^']+'\.", "", p)
    return p.strip()


def check_no_leakage_v2(train_prompts, test_prompts, max_similarity: float = 0.80):
    """
    Fails if any core test prompt is an exact match or near-duplicate (similarity >= max_similarity)
    of any core prompt in the training set (seeds + dev set).
    """
    for test_p in test_prompts:
        t_clean = strip_benchmark_boilerplate(test_p).lower().strip()
        for train_p in train_prompts:
            tr_clean = strip_benchmark_boilerplate(train_p).lower().strip()
            if t_clean == tr_clean:
                raise AssertionError(
                    f"Evaluation leakage detected: Exact duplicate prompt found in test and train sets!\n"
                    f"Test prompt:  '{test_p}'\nTrain prompt: '{train_p}'"
                )
            ratio = SequenceMatcher(None, t_clean, tr_clean).ratio()
            if ratio >= max_similarity:
                raise AssertionError(
                    f"Evaluation leakage detected: Near-duplicate prompt found in test and train sets (similarity {ratio:.2f} >= {max_similarity})!\n"
                    f"Test prompt:  '{test_p}'\nTrain prompt: '{train_p}'"
                )


class ComplexityClassifierV2:
    def __init__(self, auto_train: bool = False):
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=1500, lowercase=True)),
            ("clf", LogisticRegression(C=2.0, max_iter=300, class_weight="balanced"))
        ])
        self.is_trained = False
        if auto_train:
            self.train_on_v2_dev()

    def train_on_v2_dev(self, root_dir: Path = None):
        root = root_dir or ROOT
        dev_profile_path = root / "results" / "benchmark_v2_dev_profile.json"
        tasks_path = root / "benchmark" / "tasks_v2.json"
        split_path = root / "benchmark" / "split_v2.json"

        if not dev_profile_path.exists():
            raise FileNotFoundError(f"Dev profile not found at {dev_profile_path}")

        with open(dev_profile_path, "r", encoding="utf-8") as f:
            dev_profile = json.load(f)

        with open(tasks_path, "r", encoding="utf-8") as f:
            all_tasks = {t["id"]: t for t in json.load(f)}

        with open(split_path, "r", encoding="utf-8") as f:
            split_info = json.load(f)

        test_ids = set(split_info.get("test_ids", []))
        test_prompts = [all_tasks[tid]["prompt"] for tid in test_ids if tid in all_tasks]

        dev_texts = []
        dev_labels = []
        for tid, data in dev_profile.items():
            dev_texts.append(data["prompt"])
            dev_labels.append(data["oracle_tier"])

        all_train_texts = [x[0] for x in SEED_TRAINING_DATA] + dev_texts
        all_train_labels = [x[1] for x in SEED_TRAINING_DATA] + dev_labels

        # Verify zero evaluation leakage against held-out test set
        check_no_leakage_v2(all_train_texts, test_prompts, max_similarity=0.80)

        self.pipeline.fit(all_train_texts, all_train_labels)
        self.is_trained = True
        return len(all_train_texts), len(test_prompts)

    def predict(self, text: str, bias: float = 0.5) -> Dict:
        if not self.is_trained:
            raise RuntimeError("Classifier V2 is not trained yet!")
        probs = self.pipeline.predict_proba([text])[0]
        classes = list(self.pipeline.classes_)

        p_map = {0: 0.0, 1: 0.0, 2: 0.0}
        for c, p in zip(classes, probs):
            p_map[int(c)] = float(p)

        p0, p1, p2 = p_map[0], p_map[1], p_map[2]

        shift = (bias - 0.5)
        adjusted = [
            max(0.01, p0 - max(0.0, shift)),
            p1 + (shift * 0.2 if shift > 0 else -shift * 0.1),
            max(0.01, p2 + max(0.0, shift))
        ]
        total = sum(adjusted)
        norm_probs = [p / total for p in adjusted]

        predicted_tier = int(norm_probs.index(max(norm_probs)))
        expected_val = (0 * norm_probs[0]) + (1 * norm_probs[1]) + (2 * norm_probs[2])
        continuous_score = round(float(expected_val / 2.0), 3)
        confidence = round(float(max(norm_probs)), 3)

        return {
            "tier": int(predicted_tier),
            "confidence": confidence,
            "score": continuous_score,
            "probabilities": {
                "tier_0": round(float(norm_probs[0]), 3),
                "tier_1": round(float(norm_probs[1]), 3),
                "tier_2": round(float(norm_probs[2]), 3)
            }
        }
