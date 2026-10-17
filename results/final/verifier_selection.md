# Verifier selection (v2 DEV set only, 60 tasks)

Rule fixed before running: maximise mean DEV quality (formatting-robust grader) over the cascade, rules and classifier routers, subject to mean router cost <= 80% of DEV always_strong cost; ties -> lowest cost. Classifier scored with 5-fold cross-validation on DEV. Hosted calls: max_tokens=4096, reasoning_effort=low; local: max_tokens=1024. Test split and v3 were not used.

always_strong on DEV: 53/60 (robust grader), cost $0.009822, mean latency 7.12s. always_cheap: 41/60; random: 49/60.

| verifier | params | mean quality /60 | mean cost $ | saving vs strong | mean escalations | mean latency s | feasible |
|---|---|---|---|---|---|---|---|
| heuristic | {} | 43.33 | 0.003313 | 66.3% | 2.7 | 4.98 | True |
| strict | {} | 44.67 | 0.002645 | 73.1% | 2.0 | 4.92 | True |
| self_consistency | {'min_agree': 2} | 45.33 | 0.004153 | 57.7% | 12.0 | 13.34 | True |
| self_consistency | {'min_agree': 3} | 47.67 | 0.004724 | 51.9% | 20.0 | 13.53 | True |
| judge | {'threshold': 0.5} | 52.33 | 0.006715 | 31.6% | 16.3 | 6.99 | True |
| judge | {'threshold': 0.6} | 52.33 | 0.006715 | 31.6% | 16.3 | 6.99 | True |
| judge | {'threshold': 0.7} | 52.33 | 0.006731 | 31.5% | 17.3 | 7.01 | True |
| judge | {'threshold': 0.8} | 52.33 | 0.006731 | 31.5% | 17.3 | 7.01 | True |
| judge | {'threshold': 0.9} | 52.33 | 0.006731 | 31.5% | 17.3 | 7.01 | True |

Per-router DEV detail (quality robust / original, cost, escalations):

| verifier | params | cascade | rules | classifier(CV) |
|---|---|---|---|---|
| heuristic | {} | 42/42, $0.00134, 4 esc | 45/45, $0.00348, 1 esc | 43/43, $0.00512, 3 esc |
| strict | {} | 43/43, $0.00023, 2 esc | 47/47, $0.00261, 2 esc | 44/44, $0.00510, 2 esc |
| self_consistency | {'min_agree': 2} | 44/44, $0.00281, 17 esc | 47/47, $0.00404, 11 esc | 45/45, $0.00562, 8 esc |
| self_consistency | {'min_agree': 3} | 47/47, $0.00350, 27 esc | 48/48, $0.00443, 16 esc | 48/48, $0.00624, 17 esc |
| judge | {'threshold': 0.5} | 52/52, $0.00574, 20 esc | 52/52, $0.00585, 14 esc | 53/53, $0.00855, 15 esc |
| judge | {'threshold': 0.6} | 52/52, $0.00574, 20 esc | 52/52, $0.00585, 14 esc | 53/53, $0.00855, 15 esc |
| judge | {'threshold': 0.7} | 52/52, $0.00576, 21 esc | 52/52, $0.00587, 15 esc | 53/53, $0.00857, 16 esc |
| judge | {'threshold': 0.8} | 52/52, $0.00576, 21 esc | 52/52, $0.00587, 15 esc | 53/53, $0.00857, 16 esc |
| judge | {'threshold': 0.9} | 52/52, $0.00576, 21 esc | 52/52, $0.00587, 15 esc | 53/53, $0.00857, 16 esc |

**Selected: `judge` {'threshold': 0.5}**

Option (e), Jev (OpenRouter `typesafe/jev-1.13`, Decisions API): **not run** - no `OPENROUTER_API_KEY` is configured, so the optional flag-gated verifier was skipped.

Live API calls made in this stage: 301; wall time 2191s.