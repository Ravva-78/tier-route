# Evaluation Limitations

This document provides a factual, unsoftened catalog of methodology and evaluation limitations identifiable in the TierRoute codebase, test harness, configuration, and experimental data.

---

## 1. Tasks Written After the System Architecture and Routing Logic Were Established

- **Fact**: The benchmark task suite in `benchmark/tasks.json` (65 primary tasks, 75 sub-tasks) was hand-crafted by the system's authors after the router's heuristics, signal regexes, and cue word tables (`tierroute/analyzer.py`) were already written.
- **Consequence**: Tasks and cue terms naturally align with the exact patterns the analyzer is configured to detect (e.g., prompt phrases containing `"extract"`, `"uppercase"`, `"solve for x"`, `"prove step by step"`).
- **Implication**: The evaluation does not test arbitrary, messy, open-domain user queries or an independently gathered enterprise request trace. The observed routing accuracy reflects alignment with an author-designed synthetic workload rather than general uncalibrated traffic.

---

## 2. Lexical-Only Leakage Verification

- **Fact**: The train/test partition leakage test (`tierroute/classifier.py:check_no_leakage`) checks only:
  1. Exact string identity (`prompt_train == prompt_test`)
  2. Character 3-gram Jaccard similarity with a fixed threshold ($\text{similarity} \ge 0.65$)
- **Consequence**: The test is blind to semantic paraphrasing and synonym substitution. A prompt such as:
  - *Train*: `"Find the email address in this message: 'Reach out to support@test.com'"`
  - *Test*: `"Locate the contact electronic mail inside this snippet: 'Reach out to contact@sample.org'"`
  has low character 3-gram overlap and will pass `check_no_leakage`, despite posing an identical structural and semantic task.
- **Implication**: No dense vector embeddings (e.g., SBERT, text-embedding-3, or BGE) or semantic similarity metrics were computed to guarantee semantic orthogonality between training and held-out sets.

---

## 3. Lenient Keyword and Substring Checkers

- **Fact**: Ground-truth verification across the benchmark suite relies primarily on case-insensitive substring checks (`contains_any` or simple regular expressions in `benchmark/tasks.json`).
- **Consequence**:
  - Task `H7` (Dijkstra negative weights proof) accepts any generation containing `"bellman"` or `"cannot"` or `"wrong"`. A model that outputs a confused, logically incorrect argument but mentions the word `"Bellman-Ford"` is marked as $100\%$ correct (`correct = 1`).
  - Task `H12` (Floyd's cycle-finding) passes if the output contains `"slow"` or `"hare"` or `"tortoise"`.
  - Task `P5_p2` (Quicksort worst-case prevention) passes if the text contains `"random"` or `"arbitrar"` or `"median"`.
- **Implication**: Auto-check success scores overestimate reasoning quality. Shallow keyword presence is treated as equivalent to rigorous, logically sound proof generation.

---

## 4. Local Model Inference Cost Modeled as Zero

- **Fact**: In `config/models.yaml` and `tierroute/models.py`, `price_in_per_m` and `price_out_per_m` for `local-small` (`llama3.2:3b`) are set to `0.0`.
- **Consequence**: The reported cost savings ($36.8\%$ for classifier, $24.8\%$ for rules, and $100\%$ for always_cheap) count local inference as completely free.
- **Implication**: This ignores real-world operational costs:
  1. Capital expenditure for local host hardware (GPU/VRAM/CPU)
  2. Electricity consumption under persistent inference loads
  3. Server provisioning, memory reservation, and deployment maintenance overhead
  In production environments where infrastructure is rented (e.g., AWS EC2 instances or on-premise clusters), local tier execution has non-zero marginal cost.

---

## 5. Small Evaluation Sample Size ($N = 36$ Held-Out Sub-Tasks)

- **Fact**: The final held-out test set consists of only 36 sub-tasks (13 Tier 0, 13 Tier 1, 10 Tier 2).
- **Consequence**:
  - Statistical resolution is coarse: a single failure shifts the accuracy metric by $\Delta = \frac{1}{36} \approx 2.78\%$.
  - 95% Wilson confidence intervals are wide:
    - Observed $36/36$ ($100\%$) yields a confidence band of $[90.4\%, 100.0\%]$.
    - Observed $32/36$ ($88.9\%$) yields a confidence band of $[74.7\%, 95.6\%]$.
- **Implication**: Because the confidence interval of `always_cheap` ($[74.7\%, 95.6\%]$) overlaps substantially with that of `always_strong` ($[90.4\%, 100.0\%]$), performance differences under $\sim 15\%$ cannot be claimed with high statistical confidence.

---

## 6. Temperature-0 Repeats Are Not Independent Statistical Samples

- **Fact**: Multi-run repetitions (`run_idx = 1, 2, ...`) were executed with greedy decoding / deterministic sampling (`temperature = 0.0` or `0.2` with low entropy).
- **Consequence**: Submitting identical prompts to identical model weights under deterministic decoding yields identical outputs and identical correctness values across runs.
- **Implication**: Replicates generated under deterministic settings are not independent identically distributed (i.i.d.) random samples. Aggregating them as though they were $N \times R$ independent trials would artificially shrink confidence intervals and report false statistical power.

---

## 7. Offline Local Tier Failover in Earlier Development Runs

- **Fact**: In an earlier development benchmark run prior to launching the local Ollama daemon, calls directed to `local-small` failed with socket connection errors:
  ```text
  [WinError 10061] No connection could be made because the target machine actively refused it
  ```
- **Consequence**: The verifier interpreted socket refusal as a failed check (`ok = False`) and triggered the fallback loop, escalating those requests to Tier 1 (`hosted-mid`), which succeeded.
- **Implication**:
  - In those earlier runs, the system appeared to achieve high quality, but local inference was never executed—the work was silently offloaded to cloud APIs.
  - While this was remedied in the final live run by starting the Ollama daemon and adding the `--require-all-tiers` health check, the artifact remains documented in historical decision logs (`results/test_live.db`). If an operator fails to monitor escalation causes, silent failover masks offline local infrastructure while inflating cloud API bills.
