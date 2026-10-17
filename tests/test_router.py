import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from tierroute.analyzer import analyze
from tierroute.config import load_config
from tierroute.router import Overrides, Router
from tierroute.splitter import split_request
from tierroute.store import Store
from tierroute.verifier import verify


@pytest.fixture()
def router(tmp_path, monkeypatch):
    monkeypatch.setenv("TIERROUTE_MODE", "mock")
    return Router(load_config(), Store(tmp_path / "d.db"), Overrides(tmp_path / "o.json"))


def test_split_numbered_list():
    assert len(split_request("1. do a thing now\n2. do another thing\n3. a third thing")) == 3


def test_split_single_request_stays_whole():
    assert split_request("What is the capital of France?") == ["What is the capital of France?"]


def test_hard_scores_higher_than_easy():
    easy = analyze("Convert to uppercase: 'abc'")["score"]
    hard = analyze("Prove step by step why the algorithm has O(n^2) complexity and explain the trade-offs")["score"]
    assert hard > easy


def test_verifier_flags_uncertainty_and_errors():
    assert not verify("q", "I'm not sure about this", "qa")[0]
    assert not verify("q", "", "qa")[0]
    assert not verify("q", "x", "qa", error="timeout")[0]
    assert verify("q", "Paris", "qa")[0]


def test_easy_goes_to_cheapest_hard_to_strongest(router):
    easy = router.route("Convert to uppercase: 'abc'", meta={"difficulty": 0.2, "answer": "ABC"}, split=False)
    hard = router.route("Alice is twice as old as Bob. In 6 years the sum of their ages is 48. How old is Alice now?",
                        meta={"difficulty": 0.85, "answer": "24"}, split=False)
    assert easy["parts"][0]["final_model"] == "local-small"
    assert hard["parts"][0]["final_model"] == "hosted-strong"


def test_escalation_when_cheap_model_fails(router):
    r = router.route("Convert to uppercase: 'abc'", meta={"difficulty": 0.5, "answer": "ABC", "wrong_style": "unsure"}, split=False)
    p = r["parts"][0]
    assert p["escalated"] == 1 and p["final_model"] != "local-small" and p["answer"] == "ABC"


def test_user_pin_overrides_and_is_logged(router):
    r = router.route("Convert to uppercase: 'abc'", force_model="hosted-strong", split=False)
    p = r["parts"][0]
    assert p["final_model"] == "hosted-strong" and p["override_by"] == "user"
    assert "pinned" in p["reason"]


def test_admin_task_rule_and_global_pin(router):
    router.overrides.update({"task_rules": {"classification": "hosted-mid"}})
    r = router.route("Classify the sentiment: 'great'", split=False)
    assert r["parts"][0]["final_model"] == "hosted-mid" and r["parts"][0]["override_by"] == "admin"
    router.overrides.update({"task_rules": {}, "global_pin": "hosted-strong"})
    r = router.route("Convert to uppercase: 'abc'", split=False)
    assert r["parts"][0]["final_model"] == "hosted-strong"


def test_quality_bias_moves_work_to_stronger_tiers(router):
    s = 0.2
    assert router.tier_for(s, 0.0) <= router.tier_for(s, 0.5) <= router.tier_for(s, 1.0)
    assert router.tier_for(s, 1.0) > router.tier_for(s, 0.0)


def test_multipart_is_split_routed_and_merged(router):
    prompt = "1. Convert to uppercase: 'abc'\n2. How many ways can 5 people be seated in a row if two must not sit together?"
    r = router.route(prompt, meta=[{"difficulty": 0.2, "answer": "ABC"}, {"difficulty": 0.85, "answer": "72"}])
    assert r["n_parts"] == 2 and "ABC" in r["answer"] and "72" in r["answer"]
    assert r["parts"][0]["tier"] < r["parts"][1]["tier"]


def test_decisions_are_logged(router):
    router.route("Convert to uppercase: 'abc'", split=False)
    assert router.store.stats()["parts"] == 1


def test_classifier_strategy_routes_properly(router):
    easy = router.route("Convert this text to uppercase: 'hello'", strategy="classifier",
                        meta={"difficulty": 0.2, "answer": "HELLO"}, split=False)
    hard = router.route("Prove step by step why quicksort has O(n^2) worst case and derive average complexity",
                        strategy="classifier", meta={"difficulty": 0.85, "answer": "proof"}, split=False)
    assert easy["parts"][0]["final_model"] == "local-small"
    assert hard["parts"][0]["final_model"] == "hosted-strong"
    assert "ML classifier" in easy["parts"][0]["reason"]


def test_leakage_detection_raises_on_exact_and_near_duplicates():
    from tierroute.classifier import check_no_leakage
    # 1. Exact duplicate must raise
    with pytest.raises(AssertionError, match="Exact duplicate prompt"):
        check_no_leakage(["What is the capital of France?"], ["What is the capital of France?"])

    # 2. Near duplicate (high similarity) must raise
    with pytest.raises(AssertionError, match="Near-duplicate prompt"):
        check_no_leakage(
            ["Alice is twice as old as Bob. In 6 years the sum of their ages will be 48. How old is Alice now?"],
            ["Alice is twice as old as Bob. In 6 years the sum of their ages is 48. How old is Alice now? Give the final number."]
        )

    # 3. Genuinely distinct prompts must pass
    check_no_leakage(
        ["Extract email address from text", "Convert text to uppercase"],
        ["Calculate the average speed of a car", "Design a thread-safe LRU cache"]
    )


def test_actual_benchmark_split_has_no_leakage():
    from tierroute.classifier import ComplexityClassifier
    clf = ComplexityClassifier(auto_train_split=True)
    assert clf.is_trained


