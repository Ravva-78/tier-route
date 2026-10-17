MBPP test tasks (8): ['V2-071', 'V2-072', 'V2-073', 'V2-074', 'V2-075', 'V2-076', 'V2-079', 'V2-080']
MBPP tasks with NameError at >=1 tier (cfg A): 8 ['V2-071', 'V2-072', 'V2-073', 'V2-074', 'V2-075', 'V2-076', 'V2-079', 'V2-080']
MBPP tasks with NameError at ALL tiers (cfg A): 2 ['V2-071', 'V2-080']

#### A_1024_default - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/60 | 48/60 | 0.014849 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 41/60 | 41/60 | 0.005299 | 64.3% | - | 25/15/20 |
| cascade | leaky | 48/60 | 48/60 | 0.010386 | 30.1% | 26 | 34/13/13 |
| cascade | deploy | 35/60 | 35/60 | 0.000046 | 99.7% | 1 | 59/1/0 |
| rules | leaky | 48/60 | 48/60 | 0.011629 | 21.7% | 19 | 26/19/15 |
| rules | deploy | 42/60 | 42/60 | 0.002265 | 84.7% | 1 | 43/15/2 |
| classifier | leaky | 48/60 | 48/60 | 0.008970 | 39.6% | 15 | 34/13/13 |
| classifier | deploy | 38/60 | 38/60 | 0.004932 | 66.8% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 48/60 | 48/60 | 0.007897 | 46.8% | - | 34/13/13 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/60 | 48/60 | 0.001711 | 88.5% | - | 46/13/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 48/60 | 48/60 | 0.007897 | 46.8% | - | 34/13/13 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/60 | 48/60 | 0.001711 | 88.5% | - | 46/13/1 |

#### A_1024_default - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/52 | 48/52 | 0.010315 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 41/52 | 41/52 | 0.004043 | 60.8% | - | 22/11/19 |
| cascade | leaky | 48/52 | 48/52 | 0.004436 | 57.0% | 18 | 34/13/5 |
| cascade | deploy | 35/52 | 35/52 | 0.000046 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 48/52 | 48/52 | 0.005678 | 45.0% | 11 | 26/19/7 |
| rules | deploy | 42/52 | 42/52 | 0.002265 | 78.0% | 1 | 35/15/2 |
| classifier | leaky | 48/52 | 48/52 | 0.004436 | 57.0% | 15 | 34/13/5 |
| classifier | deploy | 38/52 | 38/52 | 0.000398 | 96.1% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 48/52 | 48/52 | 0.003362 | 67.4% | - | 34/13/5 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/52 | 48/52 | 0.001711 | 83.4% | - | 38/13/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 48/52 | 48/52 | 0.003362 | 67.4% | - | 34/13/5 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 48/52 | 48/52 | 0.001711 | 83.4% | - | 38/13/1 |

#### B_4096_default - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/60 | 49/60 | 0.015110 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 40/60 | 41/60 | 0.006276 | 58.5% | - | 25/15/20 |
| cascade | leaky | 49/60 | 49/60 | 0.011991 | 20.6% | 26 | 34/14/12 |
| cascade | deploy | 35/60 | 35/60 | 0.000046 | 99.7% | 1 | 59/1/0 |
| rules | leaky | 49/60 | 49/60 | 0.013233 | 12.4% | 19 | 26/20/14 |
| rules | deploy | 42/60 | 42/60 | 0.002258 | 85.1% | 1 | 43/15/2 |
| classifier | leaky | 49/60 | 49/60 | 0.010401 | 31.2% | 15 | 34/14/12 |
| classifier | deploy | 38/60 | 38/60 | 0.005117 | 66.1% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.007802 | 48.4% | - | 34/14/12 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.002120 | 86.0% | - | 45/14/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.007802 | 48.4% | - | 34/14/12 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.002120 | 86.0% | - | 45/14/1 |

#### B_4096_default - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 46/52 | 49/52 | 0.010391 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 40/52 | 41/52 | 0.004960 | 52.3% | - | 22/11/19 |
| cascade | leaky | 49/52 | 49/52 | 0.005682 | 45.3% | 18 | 34/14/4 |
| cascade | deploy | 35/52 | 35/52 | 0.000046 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 49/52 | 49/52 | 0.006925 | 33.4% | 11 | 26/20/6 |
| rules | deploy | 42/52 | 42/52 | 0.002258 | 78.3% | 1 | 35/15/2 |
| classifier | leaky | 49/52 | 49/52 | 0.005682 | 45.3% | 15 | 34/14/4 |
| classifier | deploy | 38/52 | 38/52 | 0.000398 | 96.2% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.003083 | 70.3% | - | 34/14/4 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.002120 | 79.6% | - | 37/14/1 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.003083 | 70.3% | - | 34/14/4 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.002120 | 79.6% | - | 37/14/1 |

#### C_4096_low - all 60 tasks

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 47/60 | 48/60 | 0.010194 | 0.0% | - | 0/0/60 |
| always_cheap | none | 34/60 | 34/60 | 0.000000 | 100.0% | - | 60/0/0 |
| random | none | 39/60 | 39/60 | 0.003319 | 67.4% | - | 25/15/20 |
| cascade | leaky | 49/60 | 49/60 | 0.006920 | 32.1% | 26 | 34/13/13 |
| cascade | deploy | 35/60 | 35/60 | 0.000023 | 99.8% | 1 | 59/1/0 |
| rules | leaky | 49/60 | 49/60 | 0.007841 | 23.1% | 19 | 26/19/15 |
| rules | deploy | 42/60 | 42/60 | 0.001555 | 84.8% | 1 | 43/15/2 |
| classifier | leaky | 49/60 | 49/60 | 0.006136 | 39.8% | 15 | 34/13/13 |
| classifier | deploy | 38/60 | 38/60 | 0.003869 | 62.0% | 1 | 48/4/8 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.005573 | 45.3% | - | 34/13/13 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.001221 | 88.0% | - | 45/13/2 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/60 | 49/60 | 0.005573 | 45.3% | - | 34/13/13 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/60 | 49/60 | 0.001221 | 88.0% | - | 45/13/2 |

#### C_4096_low - 52 tasks (excl. MBPP NameError)

| strategy | escalation signal | quality (orig grader) | quality (robust grader) | cost $ | saving vs always_strong | escalations | final workload L/M/S |
|---|---|---|---|---|---|---|---|
| always_strong | none | 47/52 | 48/52 | 0.006609 | 0.0% | - | 0/0/52 |
| always_cheap | none | 34/52 | 34/52 | 0.000000 | 100.0% | - | 52/0/0 |
| random | none | 39/52 | 39/52 | 0.002493 | 62.3% | - | 22/11/19 |
| cascade | leaky | 49/52 | 49/52 | 0.002551 | 61.4% | 18 | 34/13/5 |
| cascade | deploy | 35/52 | 35/52 | 0.000023 | 99.6% | 1 | 51/1/0 |
| rules | leaky | 49/52 | 49/52 | 0.003472 | 47.5% | 11 | 26/19/7 |
| rules | deploy | 42/52 | 42/52 | 0.001555 | 76.5% | 1 | 35/15/2 |
| classifier | leaky | 49/52 | 49/52 | 0.002551 | 61.4% | 15 | 34/13/5 |
| classifier | deploy | 38/52 | 38/52 | 0.000283 | 95.7% | 1 | 48/4/0 |
| ORACLE[orig-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.001988 | 69.9% | - | 34/13/5 |
| ORACLE[orig-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.001221 | 81.5% | - | 37/13/2 |
| ORACLE[robust-pass] previous oracle (unsolved->tier2) | none | 49/52 | 49/52 | 0.001988 | 69.9% | - | 34/13/5 |
| ORACLE[robust-pass] TRUE cost-min oracle (unsolved->cheapest) | none | 49/52 | 49/52 | 0.001221 | 81.5% | - | 37/13/2 |

#### Escalations vs under-routed (cfg A; under-routed = first tier < previous-oracle tier)

| router | escalation signal | escalations | under-routed | sets identical |
|---|---|---|---|---|
| rules | leaky | 19 | 19 | True |
| rules | deploy | 1 | 19 | False |
| classifier | leaky | 15 | 15 | True |
| classifier | deploy | 1 | 15 | False |
| cascade | leaky | 26 | 26 | True |
| cascade | deploy | 1 | 26 | False |

#### Deployable-verifier outcomes on every response

| config | tier | verifier reasons |
|---|---|---|
| A_1024_default | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| A_1024_default | 1 | {'ok': 56, 'empty': 3, 'finish_reason=length': 1} |
| A_1024_default | 2 | {'ok': 53, 'finish_reason=length': 6, 'python_parse_failure': 1} |
| B_4096_default | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| B_4096_default | 1 | {'ok': 58, 'empty': 2} |
| B_4096_default | 2 | {'ok': 56, 'python_parse_failure': 4} |
| C_4096_low | 0 | {'ok': 59, 'missing_Answer_format': 1} |
| C_4096_low | 1 | {'ok': 60} |
| C_4096_low | 2 | {'ok': 58, 'python_parse_failure': 2} |

#### Verifier vs original grader (all responses)

| config | tier | pass & correct | pass & WRONG (missed) | fail & correct (wasted esc.) | fail & wrong |
|---|---|---|---|---|---|
| A_1024_default | 0 | 34 | 25 | 0 | 1 |
| A_1024_default | 1 | 47 | 9 | 0 | 4 |
| A_1024_default | 2 | 46 | 7 | 0 | 7 |
| B_4096_default | 0 | 34 | 25 | 0 | 1 |
| B_4096_default | 1 | 48 | 10 | 0 | 2 |
| B_4096_default | 2 | 46 | 10 | 0 | 4 |
| C_4096_low | 0 | 34 | 25 | 0 | 1 |
| C_4096_low | 1 | 47 | 13 | 0 | 0 |
| C_4096_low | 2 | 47 | 11 | 0 | 2 |

#### Per-tier standalone quality (60 tasks)

| config | tier | orig | robust | cost $ | finish=length |
|---|---|---|---|---|---|
| A_1024_default | 0 | 34 | 34 | 0.000000 | 0 |
| A_1024_default | 1 | 47 | 47 | 0.006847 | 4 |
| A_1024_default | 2 | 46 | 48 | 0.014849 | 6 |
| B_4096_default | 0 | 34 | 34 | 0.000000 | 0 |
| B_4096_default | 1 | 48 | 48 | 0.008955 | 2 |
| B_4096_default | 2 | 46 | 49 | 0.015110 | 0 |
| C_4096_low | 0 | 34 | 34 | 0.000000 | 0 |
| C_4096_low | 1 | 47 | 47 | 0.003883 | 0 |
| C_4096_low | 2 | 47 | 48 | 0.010194 | 0 |
