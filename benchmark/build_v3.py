"""Build benchmark/tasks_v3.json: 60 NEW held-out tasks, seed 7, excluding every v2 task id / near-duplicate.

Composition mirrors v2 TEST: 17 GSM8K, 17 ARC-Challenge, 8 MBPP, 8 HumanEval, 10 hand-written messy extraction.
No model is called here. Public data is fetched from the HuggingFace datasets-server; the file and its SHA-256 are
written, then committed, BEFORE any model sees the tasks.
MBPP prompts include one example assert so the function name is known (standard MBPP practice).
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tierroute.classifier import SEED_TRAINING_DATA  # noqa: E402
from tierroute.classifier_v2 import strip_benchmark_boilerplate  # noqa: E402
from difflib import SequenceMatcher  # noqa: E402

SEED = 7
HF = "https://datasets-server.huggingface.co/rows"
QUOTA = {"GSM8K": 17, "ARC-Challenge": 17, "MBPP": 8, "HumanEval": 8}


def fetch(dataset, config, split):
    rows, off = [], 0
    while True:
        for wait in (5, 15, 30, 60, 90, 120, 120, 120):  # 429 rate limits / intermittent TLS errors: back off, keep verification on
            try:
                r = httpx.get(HF, params=dict(dataset=dataset, config=config, split=split, offset=off, length=100), timeout=60)
            except httpx.ConnectError:
                time.sleep(wait)
                continue
            if r.status_code != 429:
                break
            time.sleep(wait)
        r.raise_for_status()
        d = r.json()
        rows += [x["row"] for x in d["rows"]]
        off += 100
        if off >= d["num_rows_total"]:
            return rows


v2 = json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))
v2_sample_ids = {t["sample_id"] for t in v2}
v2_prompts = [t["prompt"] for t in v2]
train_prompts = [x[0] for x in SEED_TRAINING_DATA] + v2_prompts  # seeds + all v2 (dev and test)


def too_similar(prompt, thr=0.80):
    c = strip_benchmark_boilerplate(prompt).lower().strip()
    return any(SequenceMatcher(None, c, strip_benchmark_boilerplate(p).lower().strip()).ratio() >= thr for p in train_prompts)


rng = random.Random(SEED)
skipped_similar = []
tasks = []


def pick(name, cands, n, make):
    idx = list(range(len(cands)))
    rng.shuffle(idx)
    got = 0
    for i in idx:
        t = make(cands[i], i)
        if t is None or t["sample_id"] in v2_sample_ids:
            continue
        if too_similar(t["prompt"]):
            skipped_similar.append(t["sample_id"])
            continue
        tasks.append(t)
        got += 1
        if got == n:
            return
    raise RuntimeError(f"not enough candidates for {name}")


def gsm(r, i):
    return dict(dataset="GSM8K", license="MIT", sample_id=f"gsm8k_test_{i}", category="math",
                prompt="Solve the following math word problem step by step. Provide your final numerical answer on the last line "
                       f"strictly in the format 'Answer: X'.\n\nProblem: {r['question']}",
                answer=r["answer"].split("####")[-1].strip().replace(",", ""), grader={"type": "numeric"})


def arc(r, i):
    labels = r["choices"]["label"]
    if labels != ["A", "B", "C", "D"]:
        return None
    ch = "\n".join(f"({l}) {t}" for l, t in zip(labels, r["choices"]["text"]))
    return dict(dataset="ARC-Challenge", license="CC BY-SA 4.0", sample_id=f"arc_{r['id']}", category="multiple_choice",
                prompt="Answer the following multiple-choice science question. Provide your final choice letter on the last line "
                       f"strictly in the format 'Answer: X'.\n\nQuestion: {r['question']}\nChoices:\n{ch}",
                answer=r["answerKey"], grader={"type": "multiple_choice"})


def mbpp(r, i):
    tl = r["test_list"]
    setup = r.get("test_setup_code") or ""
    return dict(dataset="MBPP", license="CC-BY-4.0", sample_id=f"mbpp_{r['task_id']}", category="code",
                prompt=f"Write a Python function to solve the following task.\nTask: {r['text']}\n\n"
                       f"Your function must satisfy this example (one of the tests):\n{tl[0]}\n\n"
                       "Your code should be complete, correct, and self-contained. Provide your code inside a ```python ... ``` block.",
                answer=r["code"], grader={"type": "code", "test_code": (setup + "\n" if setup else "") + "\n".join(tl)})


def humaneval(r, i):
    return dict(dataset="HumanEval", license="MIT", sample_id=r["task_id"], category="code",
                prompt="Complete the following Python function definition according to its docstring.\n\n"
                       f"```python\n{r['prompt'].rstrip()}\n```\n\nProvide your complete function code inside a ```python ... ``` block.",
                answer=r["canonical_solution"],
                grader={"type": "code", "test_code": r["test"].rstrip() + f"\ncheck({r['entry_point']})"})


# Hand-written (by the project author), CC0-1.0. Gold answers are unambiguous by construction.
MESSY = [
    ("Extract the invoice number from this garbled scan text:\n'BILL TO: Acme Ltd // Cust. ref 55-1190 // I N V O I C E  # :  I N V - 7 3 0 4 - Q  // due 12 Dec'\n"
     "Remove the spaces inside it. Provide your final answer on the last line as 'Answer: <invoice_number>'.", "INV-7304-Q"),
    ("From this signature block, give the UK office number in E.164 format (+ and digits only, no spaces):\n"
     "'Tel (office): (+44) 20 7946 0958 | Mobile: 07700 900123'\nProvide your final answer on the last line as 'Answer: <number>'.", "+442079460958"),
    ("The email address in this text is obfuscated. Reconstruct it:\n'reach support at  helpdesk [at] northwind-supply [dot] co [dot] uk  (no spam please)'\n"
     "Provide your final answer on the last line as 'Answer: <email>'.", "helpdesk@northwind-supply.co.uk"),
    ("Extract the delivery ETA as YYYY-MM-DD. Dates in this message are written DD/MM/YY.\n"
     "'Shipped on 03/03/27 from the depot; delivery ETA 09/04/27; returns accepted until 09/05/27.'\n"
     "Provide your final answer on the last line as 'Answer: YYYY-MM-DD'.", "2027-04-09"),
    ("Extract the amount due as digits and a decimal point only (no currency symbol, no thousands separator):\n"
     "'Subtotal  $1,240.00  | Discount  -$124.00 | Shipping  $18.50 | TOTAL DUE  $1,134.50 | Paid to date  $0.00'\n"
     "Provide your final answer on the last line as 'Answer: <amount>'.", "1134.50"),
    ("Extract the source IP address (the value after src=, without the port) from this log line:\n"
     "'2027-01-08 03:11:52 WARN auth fail user=root src=203.0.113.77:50122 dst=10.0.0.5:22 attempts=14'\n"
     "Provide your final answer on the last line as 'Answer: <ip>'.", "203.0.113.77"),
    ("Extract the UPS tracking number, written without spaces:\n"
     "'Order #884120 has shipped. Tracking: 1Z 999 AA1 01 2345 6784 (UPS). Support case 55-2281 is closed.'\n"
     "Provide your final answer on the last line as 'Answer: <tracking_number>'.", "1Z999AA10123456784"),
    ("Extract the SKU from this product feed row:\n'Blue widget (large) -- SKU: WD-4412-BL-L -- lot 2207 -- qty 12 -- bin C7'\n"
     "Provide your final answer on the last line as 'Answer: <sku>'.", "WD-4412-BL-L"),
    ("Extract the sender's family name (surname only) from this email signature:\n'Thanks!!\n--\nDr. Priya R. Venkataraman, PhD\nSenior Analyst | Halden Analytics'\n"
     "Provide your final answer on the last line as 'Answer: <surname>'.", "Venkataraman"),
    ("Extract the gross weight in kilograms, with its unit, from this label:\n'Net wt. 12.5 kg (27.6 lb); gross wt. 14.1 kg (31.1 lb); pallet 3 of 8'\n"
     "Provide your final answer on the last line as 'Answer: <value> kg'.", "14.1 kg"),
]


def build():
    pick("GSM8K", fetch("openai/gsm8k", "main", "test"), QUOTA["GSM8K"], gsm)
    pick("ARC", fetch("allenai/ai2_arc", "ARC-Challenge", "test"), QUOTA["ARC-Challenge"], arc)
    pick("MBPP", fetch("google-research-datasets/mbpp", "full", "test"), QUOTA["MBPP"], mbpp)
    pick("HumanEval", fetch("openai/openai_humaneval", "openai_humaneval", "test"), QUOTA["HumanEval"], humaneval)
    ext = [dict(dataset="MessyExtraction-v3", license="CC0-1.0", sample_id=f"messy_v3_{k + 1:02d}", category="extraction",
                prompt=p, answer=a, grader={"type": "exact"}) for k, (p, a) in enumerate(MESSY)]
    for t in ext:
        assert not too_similar(t["prompt"]), t["sample_id"]
    tasks.extend(ext)


if __name__ == "__main__":
    build()
    for n, t in enumerate(tasks, 1):
        t["id"] = f"V3-{n:03d}"
    assert len(tasks) == 60 and len({t["sample_id"] for t in tasks}) == 60
    assert not ({t["sample_id"] for t in tasks} & v2_sample_ids)
    out = Path("benchmark/tasks_v3.json")
    out.write_text(json.dumps(tasks, indent=1, ensure_ascii=False), encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    Path("benchmark/tasks_v3.sha256").write_text(f"{sha}  tasks_v3.json\n")
    json.dump(dict(seed=SEED, description="v3 held-out test: nothing is tuned on it", test_ids=[t["id"] for t in tasks],
                   skipped_as_near_duplicate=skipped_similar, sha256=sha), open("benchmark/split_v3.json", "w"), indent=1)
    from collections import Counter
    print(Counter(t["dataset"] for t in tasks), "sha256", sha, "skipped_similar", skipped_similar)
