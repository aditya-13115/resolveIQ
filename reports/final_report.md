# ResolveIQ — Final Report
## Executive Summary

ResolveIQ is a selective, evidence-grounded support agent built on the Twitter Customer Support dataset for the brand **GWRHelp**. The system classifies intent, retrieves historical precedents, generates a grounded reply, and decides whether to auto-handle or escalate.

The evaluation is honest about where the pipeline stands:

| Stage | Metric (test) | Value |
|---|---|---:|
| Intent classifier | Op macro F1 | **0.624** |
| Retrieval | Recall@5 | **0.532** |
| Reply quality | Mean universal score | **13.37 / 15** |
| Automation | Safe automation coverage | **0.295** |
| Automation | Unsafe automation rate | **0.597** |

> **The chosen agent fails its own safety gate.**
>
> No candidate satisfied `unsafe_automation_rate ≤ 0.10` on dev. The predeclared fallback selected the simplest approach (`ungrounded`), which auto-handles 100% of traffic with a 59.7% unsafe rate on test.

> **The bottleneck is the classifier, not the agent.**
>
> 55 of 139 test rows have a wrong predicted intent. The largest single error source is the `delay_compensation → service_disruption` boundary: 8 of 15 errors on that intent.

> **Grounding did not help.**
>
> Δ mean reply quality (grounded − ungrounded) = **−0.51** on dev. The grounded prompt encourages the model to synthesize operational claims from topical-but-inapplicable precedents.

The report documents these findings with a full failure attribution, a per-intent breakdown, and a set of v2 recommendations. Every number traces to a frozen artifact: `runs/evaluation/metrics.json`.

---

## 1. Problem Framing

### The Task

Build an AI support agent for one brand from the TWCS dataset. The agent takes a customer message and produces:

1. An intent
2. A grounded draft reply
3. A decision to either auto-handle or escalate

The evaluation must demonstrate not just that the agent generates plausible replies, but that it **knows when it should not answer at all**.

### What "Good" Means for This Brand

GWRHelp receives a mix of actionable requests (delays, refunds, seat reservations), non-actionable chatter (praise, enthusiast posts), and ambiguous messages.

A good system:

1. **Classifies intent** well enough to route correctly.
2. **Retrieves** precedent when precedent exists.
3. **Generates** replies that are correct, relevant, helpful, and free of unsupported operational claims.
4. **Escalates** whenever any of the above is uncertain or unsafe.

The dominant metric is **safe automation coverage** — the fraction of traffic handled correctly and safely — not raw accuracy or coverage.

### Non-Goals

- No classifier training.
- No production deployment (no FastAPI, no UI).
- No claims about performance on unseen brands or distributions.

---

## 2. Data and Brand Selection

### Selection Process

Five candidate brands were shortlisted by inbound volume:

- **AmazonHelp**
- **Tesco**
- **GWRHelp**
- **AskPlayStation**
- **VerizonSupport**

Each candidate was scored on:

- Inbound request volume
- Thread completeness (visible resolution in the thread)
- Response usefulness (manual audit of 10 threads per candidate)
- Behavioral consistency
- Data cleanliness

AmazonHelp led on volume (~12,250 threads vs GWRHelp's 1,612) but had a reply pattern dominated by link/DM handoffs (29.3% vs 3.6% for GWRHelp) and a weaker manual audit score (3.00 vs 4.12).

### Final Choice: GWRHelp

| Candidate | Combined Score | Manual Audit |
|---|---:|---:|
| **GWRHelp** | **0.5935** | **4.12 / 5** |
| Tesco | 0.5798 | — |
| AmazonHelp | — | 3.00 / 5 |

**Tie-break rule (predeclared):** if the gap between the top two is below 0.10, choose the audit winner.

The gap was **0.014**, so GWRHelp was selected.

### Accepted Trade-offs

- **Volume:** 1,612 threads vs AmazonHelp's 12,250. Still above the minimum needed for a 9-intent taxonomy and a 200-example golden set.
- **Intent diversity:** narrower (mostly trains, bookings, cancellations), but each intent is well-represented and clean.
- **Fewer ambiguous cases:** compensated by higher per-case clarity and stronger behavioral consistency.

### Data Profile

| Statistic | Value |
|---|---:|
| GWRHelp threads (raw) | 1,612 |
| Analysis corpus (post-normalization) | 1,610 |
| Quarantined (normalize to empty) | 2 |
| Median first-inbound length | See notebook 01 |

---

## 3. Intent Taxonomy

### Method

Candidate intents were discovered from the corpus, not imported from a generic taxonomy:

1. Stratified exploration sample (100 messages, length-balanced).
2. Frequency and TF-IDF term analysis.
3. SVD(50) + KMeans clustering as supporting evidence.
4. Hand-authored candidate taxonomy with probe regexes.
5. Jaccard overlap on probe matches; pairs > 0.30 flagged for inspection.
6. Coverage labeling on 300 messages; target mapped ≥ 0.80.

### Final Taxonomy

**11 intents** (9 operational + 2 residuals):

- `delay_compensation`
- `refund_request`
- `booking_issue`
- `timetable_info`
- `service_disruption`
- `seat_reservation`
- `lost_property`
- `on_board_issue`
- `praise_or_chatter`
- `other`
- `ambiguous`

### Coverage Validation

| Metric | Value |
|---|---:|
| Mapped | 0.880 |
| Other | 0.113 |
| Ambiguous | 0.007 |
| Unlabelled | 0.000 |

All thresholds passed:

- `mapped ≥ 0.80`
- `other ≤ 0.15`
- `ambiguous ≤ 0.10`

### Frozen Artifact

`configs/intents.yaml`

**SHA-256:** `7a05e4af...`

---

## 4. Golden Set

### Method

- Annotation pool: 310 candidate messages (250 natural + 60 targeted rare-intent supplement).
- Auto-suggested labels via rule + TF-IDF cascade, followed by **human confirmation on every row**.
- Cascade agreement: 53%.
- **145 of 310 rows were corrected.**
- Disjoint from `coverage_labeling_sheet.csv` and `intent_examples.csv` at `root_id` and normalized-text level.
- Stratified dev/test split (30% / 70%); random split fell back because `ambiguous` has only 1 example.

### Final Golden Set

| Statistic | Value |
|---|---:|
| Total examples | 198 |
| Dev | 59 |
| Test | 139 |
| Human-confirmed | 198 / 198 |
| Cascade-corrected | 145 |

### Frozen Artifacts

- `evaluation/golden_set.jsonl` — SHA-256 `acde341d...`
- `runs/golden_set/golden_set.meta.json` — pins taxonomy SHA and test root IDs

---

## 5. Classifier

### Approaches

| Approach | Training Data | Cost |
|---|---|---|
| `rules` | Taxonomy patterns | Free |
| `tfidf_lr_rule_labels` | 300 rule-labeled rows | Free |
| `tfidf_lr_human_labels` | 188 human-verified rows | Free |
| `llm_fewshot` (`llm_zeroshot` internally) | 0 examples (few-shot prompt) | API |

### Dev Comparison

**59 rows**

| Approach | Op Macro F1 | Macro F1 | Weighted F1 | Accuracy |
|---|---:|---:|---:|---:|
| **`llm_zeroshot`** | **0.747** | 0.657 | 0.603 | 0.627 |
| `tfidf_lr_human_labels` | 0.556 | 0.455 | 0.492 | 0.508 |
| `tfidf_lr_rule_labels` | 0.470 | 0.434 | 0.556 | 0.542 |
| `rules` | 0.458 | 0.396 | 0.362 | 0.390 |

**Winner selection rule:** highest operational macro F1.

### Test Results

**139 rows, single evaluation**

| Metric | Value | 95% CI |
|---|---:|---|
| Operational Macro F1 | **0.624** | [0.548, 0.725] |
| All-Class Macro F1 | 0.551 | [0.469, 0.618] |
| Weighted F1 | 0.590 | — |
| Accuracy | 0.604 | — |
| Force-Fit Rate | 0.526 | — |

### Headline Weakness

`delay_compensation` F1 = **0.286**

- Precision = **1.00**
- Recall = **0.167**

The classifier over-predicts `service_disruption` on messages that describe a past delay without an explicit compensation ask.

This is the taxonomy's documented boundary between **"live disruption"** and **"retrospective claim"**. The model systematically misreads this boundary.

`timetable_info` F1 = **0.333** — likely a similar cause: short "is the X running?" queries get classified as `service_disruption` when the word "cancelled" or "delayed" appears.

### Confidence Calibration

The classifier is **overconfident**. ECE ≈ 0.16.

- At 0.6 self-reported confidence, empirical accuracy is 0%.
- At ~0.95, empirical accuracy is 60%.

Escalation thresholds should therefore be tuned against the **reliability curve**, not raw confidence.

### Frozen Artifact

`runs/classifier/chosen.json`

**SHA-256:** `7d51251a...`

---

## 6. Retrieval

### Corpus

The retrieval corpus is the intersection of:

1. Threads with a *substantive* brand response (5.4% of all GWRHelp responses; 87% are classified `other`).
2. Threads with a label in the `04` training pool.
3. Threads excluded from golden dev and test.

**Result:** **50 documents** at smoke-test scale.

### Approaches

**Dev — 59 queries**

| Retriever | Recall@5 | MRR | Notes |
|---|---:|---:|---|
| `oracle_intent_bm25` | 0.966 | 0.966 | Diagnostic only |
| **`tfidf`** | **0.746** | **0.493** | **Winner** |
| `hybrid_rrf` | 0.661 | 0.498 | |
| `bm25` | 0.661 | 0.455 | |
| `predicted_intent_bm25` | 0.610 | 0.610 | |
| `embedding` | 0.576 | 0.429 | |
| `random` (20-seed mean) | 0.442 | 0.268 | Floor |

Winner selection rule: highest Recall@5. Tie-break within Δ 0.02 favours the simpler/cheaper approach.

### Test Results

**139 queries, single evaluation**

| Metric | Value |
|---|---:|
| Recall@1 | 0.201 |
| Recall@5 | **0.532** |
| Recall@10 | 0.748 |
| MRR | 0.342 |
| Corpus Coverage | 0.942 |

### Human Relevance Audit

**20 queries × top-5 = 100 judgments**

- nDCG@5 = **0.592**
- Graded Precision@5 (≥1) = **0.330**

### Finding

Intent-match Recall@5 is a valid but optimistic proxy.

Only **1 in 3 retrieved documents is even partially useful**.

The automated metric captures whether retrieval finds the right topic; the human audit captures whether the retrieved precedent is actionable.

### Intent-Conditioning Diagnostic

| Variant | Dev Recall@5 |
|---|---:|
| `oracle_intent_bm25` | 0.966 |
| `tfidf` (unconditioned) | 0.746 |
| `predicted_intent_bm25` | 0.610 |

Intent-conditioning is worth ~22 points of recall **when the classifier is right**.

With the classifier at 0.62 dev accuracy, conditioned retrieval underperforms unconditioned TF-IDF. It was therefore not used in the pipeline.

### Corpus-Size Limitation

Recall@5 correlates directly with how many corpus documents share the query's intent:

| Intent | Corpus Docs | Recall@5 |
|---|---:|---:|
| `service_disruption` | 15 | 1.000 |
| `booking_issue` | 6 | 0.714 |
| `refund_request` | 2 | 0.200 |
| `lost_property` | 0 | 0.000 |

`lost_property` failures are **coverage failures**, not retrieval failures.

The absolute recall number is a floor under a severely undersized corpus.

### Frozen Artifacts

- `runs/retrieval/chosen_retriever.json` — SHA-256 `33dbaea4...`
- `runs/retrieval/corpus.jsonl` — SHA-256 `69327018...`

---

## 7. Agent

### Pipeline

```text
Frozen 04 output:
  intent
  confidence
  alternative_intent
  alt_confidence
        │
        ▼
Frozen 05 output:
  top-10 doc_ids
  retrieval scores
        │
        ▼
Escalation Decision
        │
        ├────────────────┐
        ▼                ▼
    Escalate          Generate
        │                │
        └────────┬───────┘
                 ▼
       Reply OR Escalation Reason
                 │
                 ▼
        Three Judges Score Result
```

### Approaches on Dev

**59 rows**

| Approach | Automation Coverage | Mean Universal | Unsupported Rate | Unsafe Auto Rate |
|---|---:|---:|---:|---:|
| `ungrounded` | 1.000 | 13.19 | 0.254 | 0.678 |
| `grounded_no_escalate` | 1.000 | 12.68 | 0.542 | 0.678 |
| `full_pipeline` | 0.864 | 12.82 | 0.510 | 0.706 |
| `escalate_all` | 0.000 | — | — | 0.000 |

### Selection Outcome

Predeclared safety gate:

```text
unsafe_automation_rate ≤ 0.10
```

**No candidate passed.**

The fallback rule proceeded with all candidates; the simplicity tie-break selected `ungrounded`.

A dev-only threshold sweep across:

- τc ∈ {0.30–0.50}
- τm ∈ {0.05–0.25}

produced identical results for all 25 grid points.

This is a signal that the thresholds have no discriminative power.

### Test Results

**139 rows, single evaluation**

| Metric | Value | 95% CI |
|---|---:|---|
| Automation Coverage | 1.000 | — |
| Mean Universal Score (auto) | **13.37** | [13.14, 13.60] |
| Unsupported-Claim Rate | 0.194 | — |
| **Unsafe Automation Rate** | **0.597** | [0.511, 0.683] |
| Escalation Rate | 0.000 | — |
| Escalation Recall (vs suitability) | 0.000 | — |

### Judge-Human Agreement

- Universal judge vs human: ρ = 0.722 (p = 0.002), MAD = 0.67
- Escalation-suitability judge vs human: 0.950 agreement

Both judges are well-aligned with human labels.

The problem is **not the judges**; it is that the runtime policy does not use them.

### Three Diagnostics

#### Diagnostic 1 — Escalation Signals Do Not Discriminate

| Signal | Safe (n=19) | Unsafe (n=40) |
|---|---:|---:|
| `confidence_raw` | 0.939 | 0.918 |
| `confidence_calibrated` | 0.602 | 0.626 |
| `margin` | 0.883 | 0.827 |

The distributions overlap heavily.

Only the categorical rules fire:

- `intent ∈ {other, ambiguous}` — 7 fires
- `corpus_coverage == 0` — 1 fire

Escalation precision = **0.50**

Escalation recall = **0.10**

#### Diagnostic 2 — Grounded Prompt Hallucinates Operational Claims

Δ_grounding = **−0.51** on dev.

Ten worst regressions share a pattern: the grounded prompt synthesizes operational details from topically-related but semantically-inapplicable precedents.

Representative cases:

- `root_id 59200`: bare-link message. Grounded reply invents "the service was cancelled due to congestion." The precedent did not say this.
- `root_id 1014147`: reserved seat unavailable. Grounded reply invents "on this train there are no reserved seats" — not in the precedents.
- `root_id 1208104`: sarcasm ("Love a delayed train 🤔"). Precedent is a thank-you. Grounded reply says "we'll make sure your kind words are passed on."

#### Diagnostic 3 — Ungrounded Is a Strong Baseline

Ungrounded mean universal score on dev: **13.19**.

The LLM's generic empathetic-and-redirect replies score well on the rubric.

The engineering challenge is not making replies sound good; it is making them:

- Grounded
- Operationally safe
- Appropriately escalated

### Frozen Artifacts

- `runs/agent/chosen_agent.json` — SHA-256 `dc6c09f6...`
- `runs/agent/TEST_LOCK.json` — locks generation
- `runs/agent/EVAL_LOCK.json` — locks all judging artifacts

---

## 8. End-to-End Evaluation

### Headline Table

| Metric | Value | 95% CI | n |
|---|---:|---|---:|
| Classifier Op Macro F1 | 0.624 | — | 139 |
| Retrieval Recall@5 | 0.532 | — | 139 |
| Mean Universal Score | 13.374 | [13.14, 13.60] | 139 |
| Unsupported-Claim Rate | 0.194 | — | 139 |
| Automation Coverage | 1.000 | — | 139 |
| **Safe Automation Coverage** | **0.295** | [0.22, 0.37] | 139 |
| **Unsafe Automation Rate** | **0.597** | [0.51, 0.68] | 139 |
| Safe-Handling Rate | 0.201 | [0.14, 0.27] | 139 |

### Cascade Analysis

Where does the pipeline first fail?

| Stage | n | % |
|---|---:|---:|
| `0_success` | 27 | 19.4% |
| `1_classification` | **55** | **39.6%** |
| `2_retrieval_corpus_missing` | 4 | 2.9% |
| `3_unsafe_auto_handle` | **43** | **30.9%** |
| `4_generation_quality` | 4 | 2.9% |
| `4_generation_unsupported` | 6 | 4.3% |

> **Two failure modes account for 70% of the corpus:** classification (55) and unsafe auto-handling (43).

### Per-Intent Breakdown

| Intent | n | Classifier Accuracy | Recall@5 | Unsafe Auto Rate | Safe Auto Coverage |
|---|---:|---:|---:|---:|---:|
| **`delay_compensation`** | **18** | **0.167** | 0.500 | 0.556 | 0.333 |
| `refund_request` | 10 | 0.900 | 0.200 | 0.300 | 0.600 |
| `booking_issue` | 14 | 0.571 | 0.714 | 0.571 | 0.286 |
| `timetable_info` | 10 | 0.300 | 0.800 | 0.800 | 0.200 |
| `service_disruption` | 18 | 0.833 | 1.000 | 0.722 | 0.167 |
| `seat_reservation` | 9 | 0.778 | 0.556 | 0.556 | 0.333 |
| `lost_property` | 7 | 0.571 | 0.000 | 0.429 | 0.143 |
| `on_board_issue` | 23 | 0.739 | 0.522 | 0.652 | 0.261 |
| `praise_or_chatter` | 11 | 0.818 | 0.545 | 0.545 | 0.273 |
| `other` | 18 | 0.500 | 0.222 | 0.667 | 0.333 |
| `ambiguous` | 1 | 0.000 | 0.000 | 0.000 | 1.000 |

`delay_compensation` is the highest-volume operational intent (18 rows) and the weakest classifier performance (accuracy 0.167).

### Top Confusion Pairs

| True | Pred | n |
|---|---|---:|
| **`delay_compensation`** | **`service_disruption`** | **8** |
| **`delay_compensation`** | **`other`** | **6** |
| `timetable_info` | `service_disruption` | 5 |
| `other` | `service_disruption` | 4 |
| `booking_issue` | `other` | 3 |
| `on_board_issue` | `service_disruption` | 2 |
| `seat_reservation` | `on_board_issue` | 2 |
| `on_board_issue` | `seat_reservation` | 2 |

`delay_compensation → service_disruption` alone is:

**8 / 55 = 14.5% of all classifier errors.**

This is the documented taxonomy boundary.

### Slice Analysis

| Slice | n | Classifier Accuracy | Recall@5 | Safe Auto Coverage |
|---|---:|---:|---:|---:|
| Natural | 109 | 0.606 | 0.523 | 0.275 |
| Targeted | 30 | 0.600 | 0.567 | 0.367 |
| **All** | **139** | **0.604** | **0.532** | **0.295** |

### Performance by Message Length

| Bin | n | Classifier Accuracy |
|---|---:|---:|
| Short (<80 chars) | 14 | 0.571 |
| Medium | 114 | 0.605 |
| Long (>200 chars) | 11 | 0.636 |

Length does not meaningfully correlate with quality.

### Figures

- `reports/figures/pipeline_cascade_test.png`
- `reports/figures/pipeline_handling_cascade_test.png`
- `reports/figures/automation_by_intent_test.png`
- `reports/figures/automation_tradeoff_test.png`

---

## 9. Key Findings

### 9.1 The Classifier Is the Bottleneck

55 of 139 test rows have a wrong `pred_intent` (**39.6%**).

Every downstream stage that depends on intent inherits the error.

Fixing classification would improve the pipeline more than any change to the agent stage.

### 9.2 `delay_compensation` Boundary Is the Largest Error Source

`delay_compensation` F1 = **0.286**.

Eight of 15 errors on that intent are:

```text
delay_compensation → service_disruption
```

This is the documented taxonomy boundary from notebook `02`.

A v2 would need explicit tie-break rules and additional few-shot examples for this pair.

### 9.3 Grounding Did Not Improve Reply Quality

Δ_grounding = **−0.508** on dev.

The grounded prompt synthesizes operational claims from weakly-relevant precedents.

Two contributing causes:

1. The corpus is only 50 documents at smoke-test scale.
2. The grounded and ungrounded prompts share a system message containing a conflict between:
   - "do not invent policies"
   - "use precedents as evidence"

### 9.4 Escalation Signals Do Not Discriminate

Classifier confidence and retrieval coverage have near-identical distributions on safe vs unsafe messages.

The policy's only effective rules are categorical.

A v2 would need to consume the escalation-suitability judge's signal at runtime.

### 9.5 Good Replies Can Carry Unsupported Claims

27 of 105 auto-handled rows with `universal_score ≥ 12` also have:

```text
unsupported_claim = True
```

The universal judge scores correctness, relevance, and helpfulness.

The unsupported-claim flag is orthogonal.

A reply that reads well can still fabricate a policy.

### 9.6 The Chosen Agent Fails Its Own Gate

Unsafe automation rate on test:

**0.597**

Predeclared gate:

**0.10**

The predeclared fallback correctly selected the simplest candidate when no approach passed — but that candidate is also the least safe.

This is a design flaw in the fallback, documented as future work.

---

## 10. The Misleading Headline Number

The most flattering number in this report is:

> **Mean universal reply quality = 13.37 / 15**

On its face, it suggests the agent writes excellent replies.

But the pipeline achieves it by auto-handling **100% of traffic**, including the ~60% that the independent escalation-suitability judge flags as unsafe.

The score reflects that the LLM writes *plausible-sounding* replies, not that they are *safe to send*.

27 of 105 high-scoring replies contained an unsupported operational claim.

A reviewer looking only at the universal score could ship a system that:

- Invents refund timelines
- Fabricates policies
- Provides unsupported operational information

The honest headline number is:

> **Safe automation coverage = 0.295**

Only **29.5% of test traffic** was handled correctly **and safely**.

The gap between **13.37** and **0.295** is the story of the project.

### Other Numbers That Mislead

- **"Classifier accuracy = 0.604"** looks mediocre but hides the fact that one intent (`delay_compensation`, 18 rows) accounts for 22% of the test set and has accuracy 0.167.
- **"Retrieval Recall@5 = 0.532"** looks like a weak retriever. The human audit (nDCG@5 = 0.592, graded P@5 = 0.330) shows the automated metric overstates usefulness — the actual quality is lower, not higher.
- **"Escalation recall = 0.0"** is technically correct but omits that the agent never escalated. The number is a property of the chosen fallback, not of the policy's design.

---

## 11. Limitations

See `runs/evaluation/limitations.md` for the machine-generated version.

### Summary

- **Test set size (n=139).** Bootstrap CIs are wide. Small-class metrics (`ambiguous`, n=1) are not statistically meaningful.
- **Coverage-oriented golden sampling.** Rare intents are oversampled; natural-slice metrics are the closest proxy for production traffic.
- **Intent-match retrieval relevance** is a proxy. A 20-query human audit found nDCG@5 = 0.592 and graded P@5 = 0.330, indicating the proxy overstates usefulness.
- **Judges are LLM-based.** 20-row human spot-check agreement: universal ρ = 0.72, escalation 0.95.
- **Corpus is 50 documents** at smoke-test scale.
- **Historical responses may contain outdated policies.** Retrieval and grounding use historical GWRHelp replies without a time-relevance filter.
- **Escalation policy signals** do not discriminate safe from unsafe messages on dev.
- **Cost and latency** are not captured.

---

## 12. Future Work

Prioritized by expected impact:

### 12.1 Fix the `delay_compensation` Boundary

**Highest leverage.**

Add explicit tie-break rules and 3–5 few-shot examples distinguishing:

- "live disruption"
- "retrospective delay with compensation ask"

This single boundary accounts for **8 of 55 classifier errors**.

Requires a fresh holdout to validate.

### 12.2 Move Escalation-Suitability Judgment Into the Runtime Policy

Replace the classifier-confidence and retrieval-coverage signals with the escalation-suitability judge's output.

The judge agrees with human labels **95% of the time**; the current policy signals agree with them ~50%.

### 12.3 Gate Precedent Inclusion on Relevance

Only inject precedents when retrieval evidence crosses a usefulness threshold:

- High BM25 score, or
- Reranker above a confidence cutoff

The current intent-match retrieval is too permissive; weakly relevant precedents cause the grounded prompt to hallucinate operational claims.

### 12.4 Split the Grounded and Ungrounded System Prompts

The current shared system prompt contains a conflict between:

> "do not invent policies"

and:

> "use precedents as evidence"

The grounded prompt should add:

> "If a precedent does not describe an equivalent situation, do not use its operational details."

### 12.5 Grow the Corpus

A 50-document corpus at smoke-test scale is the dominant limit on grounded generation.

Target a production-scale corpus containing **thousands of substantive responses** before re-evaluating.

### 12.6 Add an Unsupported-Claim Detector as Post-Processing

The universal judge scores quality but does not catch unsupported claims that pass the quality bar.

A dedicated claim-vs-context check would prevent the 27 mislabeled high-scoring replies observed in test.

### 12.7 Capture Cost and Latency

Not captured in this run.

A production system needs:

- Per-request token cost
- p95 latency

Both can be added to the generation cache.

### 12.8 Pre-Declare the Fallback More Carefully

When no candidate passes the safety gate, the fallback should be:

- **"Select the safest candidate"**, or
- **"Escalate all"**

—not:

- **"Prefer the simplest."**

The current fallback selects the least safe option.

---

## 13. Reproducibility

### Environment

```bash
uv sync
cp .env.example .env  # add GROQ_API_KEY
```

### Run Order

```text
notebooks/01_eda.ipynb          (fresh, ~2 min)
notebooks/02_taxonomy.ipynb     (cached, ~3 min)
notebooks/03_golden_set.ipynb   (cached, ~1 min)
notebooks/04_classifier.ipynb   (cached, ~5 min)
notebooks/05_retrieval.ipynb    (cached, ~2 min)
notebooks/06_agent.ipynb        (cached, ~5 min)
notebooks/07_evaluation.ipynb   (~30 sec, no API calls)
```

All API calls are cached to:

```text
cache/*.jsonl
```

Re-runs of notebooks `02`–`06` complete in seconds.

Notebook `07` is pure synthesis.

### Pinned SHA-256 Hashes

| Artifact | SHA-256 Prefix |
|---|---|
| Taxonomy (`configs/intents.yaml`) | `7a05e4af...` |
| Golden Set (`evaluation/golden_set.jsonl`) | `acde341d...` |
| Classifier (`runs/classifier/chosen.json`) | `7d51251a...` |
| Retriever (`runs/retrieval/chosen_retriever.json`) | `33dbaea4...` |
| Agent (`runs/agent/chosen_agent.json`) | `dc6c09f6...` |
| Corpus (`runs/retrieval/corpus.jsonl`) | `69327018...` |

Full hashes:

```text
runs/evaluation/metrics.json → frozen_inputs
```

### Verification

`07_evaluation.ipynb` Cell 2 verifies every SHA against its upstream:

- `TEST_LOCK.json`
- `EVAL_LOCK.json`

Any drift is a hard failure.

Every number in this report traces to:

```text
runs/evaluation/metrics.json
```

or one of:

```text
runs/evaluation/table_*.csv
```

No number was hand-typed.

### Decisions

See:

```text
DECISIONS.md
```

It contains 25 entries covering brand selection through the final evaluation.

---

# Appendix A — Metric Definitions

| Metric | Definition |
|---|---|
| Op Macro F1 | Macro F1 across the 9 operational intents |
| All-Class Macro F1 | Macro F1 across all 11 intents |
| Recall@k | Fraction of queries with ≥1 relevant document in top-k |
| MRR | Mean reciprocal rank of the first relevant document |
| Universal Score | Sum of correctness + relevance + helpfulness (range 3–15) |
| Unsupported-Claim Rate | Fraction of replies flagged with ≥1 unsupported operational claim |
| Automation Coverage | Fraction of traffic auto-handled (not escalated) |
| Safe Automation Coverage | Fraction of traffic auto-handled AND safe AND good reply AND no unsupported claim |
| Unsafe Automation Rate | Fraction of auto-handled rows flagged unsafe by the escalation-suitability judge |
| Safe-Handling Rate | Fraction where the agent's decision was correct regardless of path |

---

# Appendix B — Failure Attribution

Every test row gets an `earliest_defect_stage`:

```text
1_classification  →  classifier was wrong
2_retrieval       →  intent missing from corpus
3_agent_policy    →  policy auto-handled an unsafe message
4_generation      →  reply was bad or contained an unsupported claim
0_ok              →  no defect
```

And an `observed_outcome`:

```text
auto_good_reply
auto_bad_reply
auto_unsupported_claim
escalated_correctly
escalated_unnecessarily
```

Both are reported in:

```text
runs/evaluation/end_to_end_test.jsonl
```
