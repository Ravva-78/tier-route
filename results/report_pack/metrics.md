# Evaluation Metrics & Mathematical Definitions

This document details the exact definitions, formal mathematical equations, and operational computation methods for all metrics reported across the TierRoute evaluation framework and benchmark results.

---

## 1. Cost Saving vs. Strong Baseline

### Definition
Cost saving measures the relative percentage reduction in monetary expense achieved by a routing strategy compared to the monolithic `always_strong` baseline (which dispatches every request directly to the most expensive tier).

### Formula
$$\text{Cost Saving (\%)} = 100 \times \left(1 - \frac{\text{Cost}_{\text{strategy}}}{\text{Cost}_{\text{always\_strong}}}\right)$$

Where:
- $\text{Cost}_{\text{strategy}} = \sum_{i=1}^{N} \text{Cost}_i$ is the cumulative dollar cost across all $N$ evaluated sub-tasks under the evaluated strategy.
- $\text{Cost}_{\text{always\_strong}} = \sum_{i=1}^{N} \text{Cost}_{i, \text{strong}}$ is the cumulative dollar cost incurred by dispatching all $N$ sub-tasks to Tier 2 (`hosted-strong`).
- Per-call dollar cost is determined by token pricing defined in `config/models.yaml`:
  $$\text{Cost}_i = \left(\text{tokens\_in}_i \times \frac{P_{\text{in}}}{1{,}000{,}000}\right) + \left(\text{tokens\_out}_i \times \frac{P_{\text{out}}}{1{,}000{,}000}\right)$$
- Local tier inference (`local-small` on Ollama) has $P_{\text{in}} = 0$ and $P_{\text{out}} = 0$, contributing $\$0.00$ to API costs.

---

## 2. Quality Retention

### Definition
Quality retention assesses the extent to which a cost-optimized routing strategy preserves response accuracy relative to the ceiling established by the unconstrained `always_strong` tier.

### Formula
$$\text{Quality Retention} = \frac{\text{Quality}_{\text{strategy}}}{\text{Quality}_{\text{always\_strong}}}$$

Where:
- $\text{Quality}_{\text{strategy}} = \frac{1}{N} \sum_{i=1}^{N} y_i$ with $y_i \in \{0, 1\}$ denoting the binary correctness of sub-task $i$ according to ground-truth checkers.
- When `always_strong` achieves perfect accuracy on the benchmark suite ($\text{Quality}_{\text{always\_strong}} = 1.0$), Quality Retention simplifies directly to the absolute quality score of the strategy:
  $$\text{Quality Retention} = \text{Quality}_{\text{strategy}} = \frac{K_{\text{correct}}}{N}$$

---

## 3. Initial Routing Accuracy

### Definition
Initial routing accuracy quantifies the router's ability to classify and assign a prompt directly to its optimal ground-truth capability tier on the very first attempt (before any verification failure or escalation occurs).

### Formula
$$\text{Routing Accuracy} = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}\left(\text{first\_tier}_i = \text{gold\_tier}_i\right)$$

Where:
- $\mathbb{I}(\cdot)$ is the indicator function ($1$ if true, $0$ if false).
- $\text{first\_tier}_i \in \{0, 1, 2\}$ is the tier initially assigned to sub-task $i$.
- $\text{gold\_tier}_i \in \{0, 1, 2\}$ is the ground-truth tier assigned to sub-task $i$ based on intrinsic difficulty:
  - **Tier 0**: Low complexity (regex extraction, basic formatting, simple lookups)
  - **Tier 1**: Moderate complexity (math word problems, standard coding, concise explanations)
  - **Tier 2**: High complexity (multi-step logical deduction, formal proofs, intricate algorithmic analysis)

---

## 4. Under-Routing and Over-Routing

### Definition
When initial routing deviates from ground truth, it manifests as either an efficiency penalty (over-routing) or a potential quality hazard (under-routing).

### Formulas
- **Under-Routing Count & Rate**:
  Measures requests routed to a tier *lower* than the task's gold difficulty, risking failure on underpowered models:
  $$\text{Under-Routed Count} = \sum_{i=1}^{N} \mathbb{I}\left(\text{first\_tier}_i < \text{gold\_tier}_i\right)$$
  $$\text{Under-Routing Rate (\%)} = \frac{100}{N} \sum_{i=1}^{N} \mathbb{I}\left(\text{first\_tier}_i < \text{gold\_tier}_i\right)$$

- **Over-Routing Count & Rate**:
  Measures requests routed to a tier *higher* than necessary, incurring surplus financial cost without quality benefit:
  $$\text{Over-Routed Count} = \sum_{i=1}^{N} \mathbb{I}\left(\text{first\_tier}_i > \text{gold\_tier}_i\right)$$
  $$\text{Over-Routing Rate (\%)} = \frac{100}{N} \sum_{i=1}^{N} \mathbb{I}\left(\text{first\_tier}_i > \text{gold\_tier}_i\right)$$

---

## 5. Escalation Rate

### Definition
The escalation rate tracks the proportion of requests that failed initial verification (due to provider connection timeout, empty output, or invalid formatting) and were dynamically recovered by stepping up execution to the next higher tier.

### Formula
$$\text{Escalation Rate (\%)} = \frac{100}{N} \sum_{i=1}^{N} \mathbb{I}\left(\text{escalated}_i = 1\right) = \frac{100}{N} \sum_{i=1}^{N} \mathbb{I}\left(\text{final\_tier}_i > \text{first\_tier}_i\right)$$

Where:
- $\text{escalated}_i = 1$ if the execution loop completed more than 1 attempt ($\text{attempts}_i > 1$) for sub-task $i$.

---

## 6. Latency Metrics

### Definitions & Formulas
Latency represents end-to-end wall-clock time elapsed from dispatching prompt text to receiving the model provider's complete response.

- **Per-Subtask Mean Latency ($\bar{L}$)**:
  $$\bar{L} = \frac{1}{N} \sum_{i=1}^{N} L_i$$
- **Per-Subtask Median Latency ($L_{\text{p50}}$)**:
  For ordered latencies $L_{(1)} \le L_{(2)} \le \dots \le L_{(N)}$:
  $$L_{\text{p50}} = \begin{cases} L_{\left(\frac{N+1}{2}\right)} & \text{if } N \text{ is odd} \\ \frac{1}{2}\left(L_{\left(\frac{N}{2}\right)} + L_{\left(\frac{N}{2}+1\right)}\right) & \text{if } N \text{ is even} \end{cases}$$
- **Total Strategy Wall-Clock Time ($T_{\text{total}}$)**:
  $$T_{\text{total}} = \sum_{i=1}^{N} L_i$$
- **Model-Specific Latency**:
  Latencies are partitioned by executing model $m \in \{\text{local-small}, \text{hosted-mid}, \text{hosted-strong}\}$ to report distinct local inference vs. hosted cloud API latency profiles:
  $$\bar{L}_m = \frac{1}{N_m} \sum_{i \in \mathcal{S}_m} L_i, \quad L_{\text{p50}, m} = \text{median}\left(\{L_i : i \in \mathcal{S}_m\}\right)$$

---

## 7. Wilson Score 95% Confidence Interval

### Definition
The Wilson score interval is an asymmetric confidence interval for binomial success proportions. It provides reliable coverage for small sample sizes ($N=36$) and avoids the catastrophic failure modes of the standard Wald normal approximation ($\hat{p} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n}}$), which degenerates to a zero-width interval when $\hat{p} = 1.0$ or $\hat{p} = 0.0$.

### Mathematical Formulation
Given $n$ trials and $k$ successes, let the empirical proportion be:
$$\hat{p} = \frac{k}{n}$$
For a $95\%$ two-sided confidence level, the standard normal critical value is:
$$z = 1.95996 \approx 1.96$$

The Wilson score interval is centered at adjusted proportion $p_{\text{center}}$ with margin of error $p_{\text{margin}}$:

$$p_{\text{center}} = \frac{\hat{p} + \frac{z^2}{2n}}{1 + \frac{z^2}{n}}$$

$$p_{\text{margin}} = \frac{z}{1 + \frac{z^2}{n}} \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}$$

The lower and upper bounds of the interval are:
$$\text{CI}_{\text{lower}} = \max\left(0.0, \; p_{\text{center}} - p_{\text{margin}}\right)$$
$$\text{CI}_{\text{upper}} = \min\left(1.0, \; p_{\text{center}} + p_{\text{margin}}\right)$$

### Operational Example from TierRoute Live Benchmark
On the 36-subtask test set ($n = 36$):
1. **$k = 36 / 36$ (100.0% observed, e.g. `always_strong`, `rules`, `classifier`)**:
   $$\hat{p} = 1.0, \quad z = 1.95996$$
   $$p_{\text{center}} = \frac{1.0 + \frac{1.95996^2}{72}}{1 + \frac{1.95996^2}{36}} = \frac{1.05335}{1.10671} \approx 0.95179$$
   $$p_{\text{margin}} = \frac{1.95996}{1.10671} \sqrt{0 + \frac{1.95996^2}{4 \times 36^2}} = 1.77098 \times \frac{1.95996}{72} \approx 0.04821$$
   $$\text{CI}_{95\%} = [0.95179 - 0.04821, \, 0.95179 + 0.04821] = [0.9036, \, 1.0000] \implies \mathbf{[90.4\%, 100.0\%]}$$

2. **$k = 32 / 36$ (88.9% observed, e.g. `always_cheap`)**:
   $$\hat{p} = \frac{32}{36} \approx 0.8889 \implies \mathbf{[74.7\%, 95.6\%]}$$
