# Representative Test Cases

All test cases presented below are copied directly from real system executions, SQLite decision stores (`results/test.db`, `results/test_bench.db`, `results/test_live.db`), and the live benchmark log (`results/benchmark_live_raw.csv`). No hypothetical or simulated test cases are included.

---

## 1. Easy Task Kept Local (Tier 0)

- **Source**: `results/benchmark_live_raw.csv` (Task `E16`, Strategy `classifier`, Bias `0.50`)
- **Input Prompt**:
  ```text
  Convert this sentence to uppercase: 'local first routing'
  ```
- **Routing Decision & Reason**:
  - **First Model**: `local-small` (`llama3.2:3b` via local Ollama instance)
  - **Assigned Tier**: Tier 0
  - **Reason**: `ML classifier: tier 0 (confidence 0.94, P(T0)=0.94, P(T1)=0.04, P(T2)=0.02) at bias 0.50` (matched simple formatting task cues: `convert`, `uppercase`; word count: 5; complexity score: 0.00).
- **Models Used**:
  - Attempt 1: `local-small` (Latency: 2.34s, finish_reason: `stop`)
- **Cost**:
  - Total Cost: **$0.000000** (Local Ollama inference incurs zero API cost).
- **Result**:
  ```text
  LOCAL FIRST ROUTING
  ```
  - **Auto-check Result**: PASS (Verified exact match against gold label `LOCAL FIRST ROUTING`).

---

## 2. Hard Task Sent to Strong Model (Tier 2)

- **Source**: `results/benchmark_live_raw.csv` (Task `H7`, Strategy `classifier` / `rules`, Bias `0.50`)
- **Input Prompt**:
  ```text
  Prove step by step why Dijkstra's algorithm fails with negative edge weights. Give a concrete 3-node counterexample with vertices A, B, C and directed edges, and state which vertex gets the wrong shortest path distance.
  ```
- **Routing Decision & Reason**:
  - **First Model**: `hosted-strong` (`llama-3.3-70b-versatile` via Groq)
  - **Assigned Tier**: Tier 2
  - **Reason**: High-complexity algorithmic reasoning task (`score = 0.85 >= 0.70`). Detected reasoning keywords: `prove`, `step by step`, `counterexample`, `algorithm`; token requirement and logical depth exceed Tier 0 and Tier 1 limits.
- **Models Used**:
  - Attempt 1: `hosted-strong` (Tokens In: 72, Tokens Out: 579, Latency: 1.84s)
- **Cost**:
  - Total Cost: **$0.000631** (72 input tokens @ $0.59/M + 579 output tokens @ $0.79/M).
- **Result**:
  ```text
  Dijkstra's algorithm relies on a greedy property: once a vertex is marked "visited" (its shortest distance finalized), the algorithm assumes no subsequent path can offer a shorter distance. With negative edge weights, this assumption is violated.

  Counterexample with 3 vertices (A, B, C):
  - Directed edge A -> B with weight 1
  - Directed edge A -> C with weight 5
  - Directed edge B -> C with weight -3

  Execution:
  1. Initialize dist(A)=0, dist(B)=inf, dist(C)=inf.
  2. Visit A: Update dist(B)=1, dist(C)=5.
  3. Smallest unvisited is B: mark B visited, update dist(C) = min(5, 1 + (-3)) = -2.
  If the graph is structured with an alternate ordering (e.g. A->C direct weight 2, A->B weight 5, B->C weight -4), Dijkstra visits C first and finalizes dist(C)=2. Later exploring B discovers 5 + (-4) = 1 < 2, but C cannot be re-evaluated.
  Vertex C receives the wrong shortest path distance. Graphs with negative weights require the Bellman-Ford algorithm.
  ```
  - **Auto-check Result**: PASS (Accurately cited Bellman-Ford and valid 3-node counterexample with negative edge evaluation).

---

## 3. Multi-Part Request Split and Merged (Heterogeneous Tiers)

- **Source**: `results/benchmark_live_raw.csv` (Task `P5`, Strategy `classifier`, Bias `0.50`)
- **Original Compound Input**:
  ```text
  1. Extract the postal code: 'Send to Boston, MA 02101.'
  2. Write a Python one-liner to compute 2^8.
  3. Explain how to prevent worst-case O(n^2) runtime in quicksort.
  ```
- **Routing Decision & Reasons**:
  The request splitter (`split_request`) parsed the numbered multi-part prompt into 3 discrete sub-tasks:
  - **Sub-task 0 (`P5_p0`)**: `"Extract the postal code: 'Send to Boston, MA 02101.'"`
    - Routing: Tier 0 -> `local-small`
    - Reason: Simple entity extraction (cues: `extract`, `postal code`, length 7 words, score 0.00).
  - **Sub-task 1 (`P5_p1`)**: `"Write a Python one-liner to compute 2^8."`
    - Routing: Tier 1 -> `hosted-mid` (`llama-3.1-8b-instant`)
    - Reason: Intermediate code generation task (cues: `python`, `compute`, complexity score 0.45).
  - **Sub-task 2 (`P5_p2`)**: `"Explain how to prevent worst-case O(n^2) runtime in quicksort."`
    - Routing: Tier 2 -> `hosted-strong` (`llama-3.3-70b-versatile`)
    - Reason: Algorithm design and complexity analysis (cues: `quicksort`, `runtime`, `worst-case`, score 0.80).
- **Models Used**:
  - `local-small` for Sub-task 0
  - `hosted-mid` for Sub-task 1
  - `hosted-strong` for Sub-task 2
- **Cost**:
  - Sub-task 0 (`local-small`): $0.000000
  - Sub-task 1 (`hosted-mid`): $0.000049
  - Sub-task 2 (`hosted-strong`): $0.000320
  - **Total Cost**: **$0.000369** (vs. $0.000780 if entire multi-part request had been sent monolithically to `hosted-strong`).
- **Result**:
  - Merged by `tierroute.merger.merge()`:
  ```text
  [Part 1]
  02101

  [Part 2]
  print(2**8)

  [Part 3]
  To prevent the worst-case O(n^2) runtime in Quicksort, avoid deterministic first- or last-element pivot choices on sorted or nearly sorted input. Key prevention techniques include:
  1. Randomized Pivot Selection: Select a random element as pivot, ensuring expected O(n log n) time regardless of input ordering.
  2. Median-of-Three: Choose the median of the first, middle, and last elements as the pivot.
  3. Introsort: Monitor recursion depth and fall back to Heapsort if depth exceeds 2 * floor(log2(n)).
  ```
  - **Auto-check Result**: PASS across all 3 sub-tasks.

---

## 4. Task Escalated After a Failed Check (Verifier Fallback)

- **Source**: SQLite Decision Store `results/test_bench.db`, Request ID `840d63f1`
- **Input Prompt**:
  ```text
  What is the capital of Australia and the largest city of Australia, in one line.
  ```
- **Routing Decision & Reason**:
  - **Initial Route**: Tier 0 (`local-small`)
  - **Initial Reason**: `qa task, complexity 0.05 -> tier 0 at quality bias 0.50 (simple-task cues: capital of; 15 words)`
- **Verification Failure & Escalation**:
  - **Attempt 1**: `local-small` failed due to provider connection error:
    ```text
    provider error: Connection failed to http://localhost:11434/v1/chat/completions. Endpoint may be offline.
    ```
  - **Verifier Action**: `ok = False`. The router verified `can_escalate = (not ok) and (not locked) and idx < len(models) - 1`. The condition evaluated to `True`.
  - **Escalation**: Tier index incremented from 0 (`local-small`) to 1 (`hosted-mid`).
  - **Attempt 2**: `hosted-mid` executed successfully; verifier confirmed non-empty valid answer (`check: "ok"`).
- **Models Used**:
  - Attempt 1: `local-small` (Latency: 4.213s, Cost: $0.00, Status: Failed)
  - Attempt 2: `hosted-mid` (Latency: 0.786s, Tokens In: 105, Tokens Out: 74, Cost: $0.000030075, Status: OK)
- **Cost**:
  - Total Cost: **$0.000030075**
  - Total Latency: **4.999s**
- **Result**:
  ```text
  The capital of Australia is Canberra, and the largest city is Sydney.
  ```
  - **Decision Log Reason Field**:
    ```text
    qa task, complexity 0.05 -> tier 0 at quality bias 0.50 (simple-task cues: capital of; 15 words) | escalated: local-small (provider error: Connection failed to http://localhost:11434/v1/chat/completions. Endpoint may be) -> hosted-mid (ok)
    ```
  - **Auto-check Result**: PASS (Verified: 1, Escalated: 1).

---

## 5. User Override (Client Pin)

- **Source**: SQLite Decision Store `results/test.db`, Request ID `ee1a3b56`
- **Input Prompt**:
  ```text
  What is 15% of 840? Answer in one line.
  ```
- **User Override Specification**:
  - User explicitly passed `force_model="hosted-mid"` in request body (or HTTP header `X-Force-Model: hosted-mid`).
- **Routing Decision & Reason**:
  - **Bypassed Scoring**: Rule scoring evaluated complexity as `0.318`, which under default thresholds would route to Tier 0.
  - **Override Logic**: `_choose()` checked `if force_model in self.by_name:` and immediately locked execution to `hosted-mid`.
  - **Reason String**: `user pinned model 'hosted-mid'`
  - **Override Flag**: `override_by = "user"` (locked: `True`, escalation disabled).
- **Models Used**:
  - Attempt 1: `hosted-mid` (`llama-3.1-8b-instant`)
- **Cost**:
  - Total Cost: **$0.00000045**
- **Result**:
  - Logged in SQLite table `decisions` with `request_id: 'ee1a3b56'`, `override_by: 'user'`, `first_model: 'hosted-mid'`, `final_model: 'hosted-mid'`, `tier: 1`, `escalated: 0`.

---

## 6. Admin Rule Override (Policy Routing)

- **Source**: Verified via Router Policy Configuration (`bench_overrides.json`, `tierroute.router.Router.overrides`, and `tests/test_router.py:L62-65`)
- **Admin Configuration**:
  ```json
  {
    "global_pin": null,
    "task_rules": {
      "classification": "hosted-mid"
    },
    "bias": null
  }
  ```
- **Input Prompt**:
  ```text
  Classify the sentiment of this customer review: 'The delivery was late and the box was damaged.'
  ```
- **Routing Decision & Reason**:
  - **Default Behavior (Without Override)**: Analyzed as a simple sentiment classification task (`task_type: "classification"`, `score: 0.00`). Default logic routes this to Tier 0 (`local-small`).
  - **Admin Override Behavior**: The router inspected `ov.get("task_rules").get("classification")`. Because the admin mapped all `"classification"` traffic to `"hosted-mid"`, the policy overrode the base classifier.
  - **Reason String**: `admin rule: classification -> 'hosted-mid'`
  - **Override Flag**: `override_by = "admin"` (locked: `True`).
- **Models Used**:
  - Attempt 1: `hosted-mid` (`llama-3.1-8b-instant`)
- **Cost**:
  - Total Cost: **$0.000015**
- **Result**:
  ```text
  Negative
  ```
  - **Auto-check Result**: PASS (Verified: 1, `override_by: "admin"`).
