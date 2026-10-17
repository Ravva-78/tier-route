"""Trainable and pre-calibrated ML Classifier for prompt complexity routing.
Fulfills the academic requirement for comparing Rule-Based vs Machine Learning routing.
Uses TF-IDF feature extraction combined with structural complexity cues to predict:
  Tier 0 (Local/Edge), Tier 1 (Mid-tier), or Tier 2 (Frontier Reasoning).
"""
import math
import re
from typing import Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Training seed dataset covering diverse intent types and difficulties
SEED_TRAINING_DATA = [
    # Tier 0: Simple extraction, formatting, basic QA, classification (Local model)
    ("Extract the email address from this text: contact support@example.com", 0, "extraction"),
    ("Extract the date from: Meeting held on 15 August 2025", 0, "extraction"),
    ("Convert to uppercase: hello world", 0, "formatting"),
    ("Convert this string to lowercase: HELLO THERE", 0, "formatting"),
    ("Sort these numbers in ascending order: 9, 3, 5, 1", 0, "formatting"),
    ("Classify the sentiment: This is absolutely wonderful and great!", 0, "classification"),
    ("Classify this email as spam or not spam: You won a million dollars click here", 0, "classification"),
    ("What is the capital of France?", 0, "qa"),
    ("What is the capital of Germany?", 0, "qa"),
    ("Reformat this phone number with dashes: 9876543210", 0, "formatting"),
    ("Is this review positive or negative: The food was cold and service was bad.", 0, "classification"),
    ("Extract all names from: Alice and Bob went to the market.", 0, "extraction"),
    ("List 3 primary colors.", 0, "qa"),
    ("What is the currency of Japan?", 0, "qa"),

    # Tier 1: Intermediate QA, basic math, translation, simple programming (Mid model)
    ("Translate to French: Good morning, how are you today?", 1, "translation"),
    ("Translate to Spanish: Where is the nearest train station?", 1, "translation"),
    ("A pen costs 15 rupees. What is the cost of 12 pens after a 10% discount?", 1, "math"),
    ("What is the sum of the first 15 positive odd numbers?", 1, "math"),
    ("Calculate the total if 4 items cost 250 each with 18% tax.", 1, "math"),
    ("Explain the difference between a list and a tuple in Python.", 1, "code"),
    ("Write a Python function to check if a string is a palindrome.", 1, "code"),
    ("What does len([1, 2, 3][1:]) return in Python?", 1, "code"),
    ("Explain in 2 sentences why binary search is O(log n).", 1, "reasoning"),
    ("Summarize the key events of the Industrial Revolution in 3 bullet points.", 1, "qa"),
    ("Solve for x: 3x + 12 = 33.", 1, "math"),
    ("Explain how DNS resolution works at a high level.", 1, "qa"),
    ("What is the difference between TCP and UDP?", 1, "qa"),

    # Tier 2: Deep multi-step reasoning, mathematical proof, complex algorithm design (Frontier model)
    ("Alice is twice as old as Bob. In 6 years the sum of their ages will be 48. How old is Alice now?", 2, "reasoning"),
    ("Prove step by step why quicksort has O(n^2) worst case but O(n log n) average case complexity.", 2, "reasoning"),
    ("A train travels at 60 km/h and another leaves 1 hour later at 90 km/h. When do they meet?", 2, "reasoning"),
    ("How many ways can 5 people be seated in a row if two specific people refuse to sit adjacent?", 2, "reasoning"),
    ("Design a distributed rate-limiting architecture handling 100k requests per second with high availability.", 2, "code"),
    ("Derive the time and space complexity of Dijkstra's algorithm using a min-heap.", 2, "reasoning"),
    ("If 3 machines make 3 widgets in 3 minutes, how many minutes do 100 machines need for 100 widgets?", 2, "reasoning"),
    ("Analyze the architectural trade-offs between monolithic and microservice architectures for fintech.", 2, "reasoning"),
    ("A bag has 4 red and 6 blue balls. What is the probability that 2 randomly drawn balls are both red?", 2, "reasoning"),
    ("Write an optimal algorithm in Python to find the longest substring with at most k distinct characters.", 2, "code"),
    ("Critique the security vulnerabilities in this smart contract and propose remediation.", 2, "code"),
]


from difflib import SequenceMatcher
import json
from pathlib import Path


def check_no_leakage(train_prompts, test_prompts, max_similarity: float = 0.80):
    """
    Fails if any test prompt is an exact match or near-duplicate (similarity >= max_similarity)
    of any prompt in the training set (seeds + dev set).
    """
    for test_p in test_prompts:
        t_clean = test_p.lower().strip()
        for train_p in train_prompts:
            tr_clean = train_p.lower().strip()
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


class ComplexityClassifier:
    """Supervised ML model for LLM tier classification with confidence probabilities."""

    def __init__(self, auto_train_split: bool = True):
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=1000, lowercase=True)),
            ("clf", LogisticRegression(C=2.0, max_iter=200, class_weight="balanced"))
        ])
        self.is_trained = False
        if auto_train_split:
            self._train_from_split_or_default()
        else:
            self._train_default()

    def _train_default(self):
        texts = [x[0] for x in SEED_TRAINING_DATA]
        labels = [x[1] for x in SEED_TRAINING_DATA]
        self.pipeline.fit(texts, labels)
        self.is_trained = True

    def train_on_split(self, root_dir: Path = None):
        """
        Trains classifier strictly on seed prompts + dev set tasks.
        Validates that NO held-out test prompt leaks into the training data.
        """
        root = root_dir or Path(__file__).resolve().parent.parent
        split_path = root / "benchmark" / "split.json"
        tasks_path = root / "benchmark" / "tasks.json"

        if not split_path.exists() or not tasks_path.exists():
            self._train_default()
            return

        split_info = json.loads(split_path.read_text(encoding="utf-8"))
        all_tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        by_id = {t["id"]: t for t in all_tasks}

        dev_ids = set(split_info.get("dev_task_ids", []))
        test_ids = set(split_info.get("test_task_ids", []))

        dev_texts, dev_labels = [], []
        for did in dev_ids:
            t = by_id.get(did)
            if not t:
                continue
            if "parts" in t:
                for p in t["parts"]:
                    dev_texts.append(p["prompt"])
                    dev_labels.append(p["tier"])
            else:
                dev_texts.append(t["prompt"])
                dev_labels.append(t["tier"])

        test_texts = []
        for tid in test_ids:
            t = by_id.get(tid)
            if not t:
                continue
            if "parts" in t:
                for p in t["parts"]:
                    test_texts.append(p["prompt"])
            else:
                test_texts.append(t["prompt"])

        all_train_texts = [x[0] for x in SEED_TRAINING_DATA] + dev_texts
        all_train_labels = [x[1] for x in SEED_TRAINING_DATA] + dev_labels

        # Enforce zero evaluation leakage against test set
        check_no_leakage(all_train_texts, test_texts, max_similarity=0.80)

        self.pipeline.fit(all_train_texts, all_train_labels)
        self.is_trained = True

    def _train_from_split_or_default(self):
        try:
            self.train_on_split()
        except Exception:
            self._train_default()

    def train(self, texts, labels):
        self.pipeline.fit(texts, labels)
        self.is_trained = True

    def predict(self, text: str, bias: float = 0.5) -> Dict:
        """
        Predicts tier (0, 1, or 2), raw probabilities, and a normalized continuous complexity score.
        quality_bias shifts probabilities toward higher tiers.
        """
        probs = self.pipeline.predict_proba([text])[0]  # [P(T0), P(T1), P(T2)]
        
        # Apply quality_bias shift: higher bias increases weight of Tier 1 & 2
        shift = (bias - 0.5)
        adjusted = [
            max(0.01, probs[0] - max(0.0, shift)),
            probs[1] + (shift * 0.2 if shift > 0 else -shift * 0.1),
            max(0.01, probs[2] + max(0.0, shift))
        ]
        # Re-normalize
        total = sum(adjusted)
        norm_probs = [p / total for p in adjusted]

        predicted_tier = int(norm_probs.index(max(norm_probs)))
        
        # Continuous complexity score: Expected tier value / 2.0 -> range [0.0, 1.0]
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
                "tier_2": round(float(norm_probs[2]), 3),
            },
            "strategy": "classifier"
        }


# Singleton instance ready for import
classifier = ComplexityClassifier(auto_train_split=True)

