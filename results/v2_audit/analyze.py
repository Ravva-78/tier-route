"""Replay routers over the real response matrices. Writes markdown tables to results/v2_audit/tables.md."""
import csv, json, random, sys, io
sys.path.insert(0, "."); sys.path.insert(0, "results/v2_audit")
from collections import Counter
from tierroute.config import load_config
from tierroute.analyzer import analyze
from tierroute.classifier_v2 import ComplexityClassifierV2
from audit_lib import grade_robust as _gr, verify_deploy
from tierroute.grading_v2 import grade_task_v2 as _g
_C = {}
def _memo(fn, tag):
    def f(t, text):
        k = (tag, t["id"], text)
        if k not in _C:
            _C[k] = fn(t, text)
        return _C[k]
    return f
grade_task_v2 = _memo(_g, "o")  # memoised: code grading spawns a subprocess per call
grade_robust = _memo(_gr, "r")

specs = {m.tier: m for m in load_config().models}
tasks = {t["id"]: t for t in json.load(open("benchmark/tasks_v2.json", encoding="utf-8"))}
ids = json.load(open("benchmark/split_v2.json"))["test_ids"]
clf = ComplexityClassifierV2(auto_train=True)
CFGS = ["A_1024_default", "B_4096_default", "C_4096_low"]
STRATS = ["always_strong", "always_cheap", "random", "cascade", "rules", "classifier"]
out = io.StringIO()


def P(*a):
    print(*a, file=out)
    print(*a)


def load(c):
    return json.load(open(f"results/v2_audit/responses_{c}.json", encoding="utf-8"))


def first_tier(strat, tid, rnd):
    p = tasks[tid]["prompt"]
    if strat == "always_strong":
        return 2
    if strat in ("always_cheap", "cascade"):
        return 0
    if strat == "random":
        return rnd.randint(0, 2)
    if strat == "rules":
        return sum(1 for th in (0.50, 0.74) if analyze(p)["score"] >= th)
    return clf.predict(p, bias=0.5)["tier"]


def run(M, strat, esc):
    """esc: none | leaky (original grader: gold + unit tests) | deploy (gold-free verifier)"""
    rnd = random.Random(42)
    rows = []
    for tid in ids:
        t = tasks[tid]
        ft = first_tier(strat, tid, rnd)
        cur, cost, att = ft, 0.0, 0
        while True:
            r = M[f"{tid}|{cur}"]
            att += 1
            cost += specs[cur].cost(r["tokens_in"], r["tokens_out"])
            if esc == "leaky":
                ok = grade_task_v2(t, r["text"])[0]
            else:
                ok = verify_deploy(t["prompt"], r["text"], r["finish_reason"])[0]
            if esc == "none" or ok or cur == 2:
                break
            cur += 1
        rows.append(dict(tid=tid, first=ft, final=cur, cost=cost, esc=int(att > 1), att=att,
                         q_orig=int(grade_task_v2(t, r["text"])[0]), q_rob=int(grade_robust(t, r["text"])[0])))
    return rows


def agg(rows, sub=None):
    rs = [r for r in rows if sub is None or r["tid"] in sub]
    return dict(n=len(rs), qo=sum(r["q_orig"] for r in rs), qr=sum(r["q_rob"] for r in rs),
                cost=sum(r["cost"] for r in rs), esc=sum(r["esc"] for r in rs),
                wl="/".join(str(sum(1 for r in rs if r["final"] == t)) for t in (0, 1, 2)))


def oracle(M, gname, kind):
    """kind prev: lowest passing tier, unsolved -> tier 2. true: cheapest passing by $, unsolved -> cheapest by $."""
    rows = []
    for tid in ids:
        t = tasks[tid]
        cand = []
        for k in (0, 1, 2):
            r = M[f"{tid}|{k}"]
            g = (grade_task_v2 if gname == "orig" else grade_robust)(t, r["text"])[0]
            cand.append((specs[k].cost(r["tokens_in"], r["tokens_out"]), k, g))
        passing = [x for x in cand if x[2]]
        if kind == "prev":
            pick = min(passing, key=lambda x: x[1]) if passing else cand[2]
        else:
            pick = min(passing, key=lambda x: x[0]) if passing else min(cand, key=lambda x: x[0])
        r = M[f"{tid}|{pick[1]}"]
        rows.append(dict(tid=tid, first=pick[1], final=pick[1], cost=pick[0], esc=0, att=1,
                         q_orig=int(grade_task_v2(t, r["text"])[0]), q_rob=int(grade_robust(t, r["text"])[0])))
    return rows


allrows, res = [], {}
for c in CFGS:
    M = load(c)
    for s in STRATS:
        for esc in (["none"] if s.startswith(("always", "random")) else ["leaky", "deploy"]):
            rows = run(M, s, esc)
            res[(c, s, esc)] = rows
            allrows += [dict(config=c, strategy=s, escalation=esc, **r) for r in rows]
    for gname in ("orig", "robust"):
        for kind, lab in (("prev", "previous oracle (unsolved->tier2)"), ("true", "TRUE cost-min oracle (unsolved->cheapest)")):
            res[(c, f"ORACLE[{gname}-pass] {lab}", "none")] = oracle(M, gname, kind)

MA = load("A_1024_default")
mbpp = sorted(t for t in ids if tasks[t]["dataset"] == "MBPP")
ne = sorted(t for t in mbpp if any("NameError" in grade_task_v2(tasks[t], MA[f"{t}|{k}"]["text"])[1] for k in (0, 1, 2)))
ne_all = sorted(t for t in mbpp if all("NameError" in grade_task_v2(tasks[t], MA[f"{t}|{k}"]["text"])[1] for k in (0, 1, 2)))
P(f"MBPP test tasks ({len(mbpp)}): {mbpp}")
P(f"MBPP tasks with NameError at >=1 tier (cfg A): {len(ne)} {ne}")
P(f"MBPP tasks with NameError at ALL tiers (cfg A): {len(ne_all)} {ne_all}")
sub52 = set(ids) - set(ne)
json.dump(ne, open("results/v2_audit/nameerror_tasks.json", "w"))


def table(c, sub, label):
    P(f"\n#### {c} - {label}\n")
    P("| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |")
    P("|---|---|---|---|---|---|---|---|")
    base = agg(res[(c, "always_strong", "none")], sub)["cost"]
    for (cc, s, e), rows in res.items():
        if cc != c:
            continue
        a = agg(rows, sub)
        P(f"| {s} | {e} | {a['qo']}/{a['n']} | {a['qr']}/{a['n']} | {a['cost']:.6f} | {100*(1-a['cost']/base):.1f}% | {a['esc'] if e != 'none' else '-'} | {a['wl']} |")


for c in CFGS:
    table(c, None, "all 60 tasks")
    table(c, sub52, f"{len(sub52)} tasks (excl. MBPP NameError)")

P("\n#### Escalations vs under-routed (cfg A; under-routed = first tier < previous-oracle tier)\n")
P("| router | escalation signal | escalations | under-routed | sets identical |\n|---|---|---|---|---|")
orc = {r["tid"]: r["final"] for r in res[("A_1024_default", "ORACLE[orig-pass] previous oracle (unsolved->tier2)", "none")]}
for s in ("rules", "classifier", "cascade"):
    for e in ("leaky", "deploy"):
        rows = res[("A_1024_default", s, e)]
        E = {r["tid"] for r in rows if r["esc"]}
        U = {r["tid"] for r in rows if r["first"] < orc[r["tid"]]}
        P(f"| {s} | {e} | {len(E)} | {len(U)} | {E == U} |")

P("\n#### Deployable-verifier outcomes on every response\n\n| config | tier | verifier reasons |\n|---|---|---|")
for c in CFGS:
    M = load(c)
    for k in (0, 1, 2):
        cnt = Counter(verify_deploy(tasks[t]["prompt"], M[f"{t}|{k}"]["text"], M[f"{t}|{k}"]["finish_reason"])[1] for t in ids)
        P(f"| {c} | {k} | {dict(cnt)} |")

P("\n#### Verifier vs original grader (all responses)\n\n| config | tier | pass & correct | pass & WRONG (missed) | fail & correct (wasted esc.) | fail & wrong |\n|---|---|---|---|---|---|")
for c in CFGS:
    M = load(c)
    for k in (0, 1, 2):
        cc = Counter((verify_deploy(tasks[t]["prompt"], M[f"{t}|{k}"]["text"], M[f"{t}|{k}"]["finish_reason"])[0],
                      grade_task_v2(tasks[t], M[f"{t}|{k}"]["text"])[0]) for t in ids)
        P(f"| {c} | {k} | {cc[(True, True)]} | {cc[(True, False)]} | {cc[(False, True)]} | {cc[(False, False)]} |")

P("\n#### Per-tier standalone quality (60 tasks)\n\n| config | tier | orig | robust | cost $ | finish=length |\n|---|---|---|---|---|---|")
for c in CFGS:
    M = load(c)
    for k in (0, 1, 2):
        qo = sum(grade_task_v2(tasks[t], M[f"{t}|{k}"]["text"])[0] for t in ids)
        qr = sum(grade_robust(tasks[t], M[f"{t}|{k}"]["text"])[0] for t in ids)
        cost = sum(specs[k].cost(M[f"{t}|{k}"]["tokens_in"], M[f"{t}|{k}"]["tokens_out"]) for t in ids)
        ln = sum(M[f"{t}|{k}"]["finish_reason"] == "length" for t in ids)
        P(f"| {c} | {k} | {qo} | {qr} | {cost:.6f} | {ln} |")

json.dump(allrows, open("results/v2_audit/per_task_rows.json", "w"))
with open("results/v2_audit/per_task_rows.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(allrows[0]))
    w.writeheader()
    w.writerows(allrows)
open("results/v2_audit/tables.md", "w", encoding="utf-8").write(out.getvalue())
