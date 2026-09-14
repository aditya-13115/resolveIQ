> **Naming note.** The internal identifier `llm_zeroshot` is retained
> in artifact filenames and the frozen lock. The method is **few-shot**:
> the system prompt includes 20 examples (2 per operational intent + 2
> each for `other` and `ambiguous`) drawn from human-verified,
> non-golden data. The identifier is legacy; the method is few-shot.

## Classifier — final evaluation

**Chosen classifier:** llm_zeroshot (`openai/gpt-oss-20b` via Groq)

### Test results (139 examples, single evaluation)

| Metric | Value | 95% CI |
|---|---:|---|
| Operational macro F1 | 0.624 | [0.548, 0.725] |
| All-class macro F1 | 0.551 | [0.469, 0.618] |
| Weighted F1 | 0.590 | — |
| Accuracy | 0.604 | — |
| Force-fit rate | 0.526 | — |

### Headline weakness

`delay_compensation` F1 = 0.286 (P=1.00, R=0.167). The classifier
over-predicts `service_disruption` on messages that describe a past
delay without an explicit compensation ask. This is the taxonomy's
documented boundary between "live disruption" and "retrospective
claim" — the model systematically misreads the boundary.

`timetable_info` F1 = 0.333 — also weak. Likely a similar cause:
short "is the X running?" queries get classified as service_disruption
when the word "cancelled" or "delayed" appears.

### Comparison vs baselines

| Approach | Op macro F1 (test) | Force-fit |
|---|---:|---:|
| llm_zeroshot | 0.624 | 0.526 |
| tfidf_lr_human_labels | 0.503 | 0.947 |
| tfidf_lr_rule_labels | 0.470 | — |
| rules | 0.458 | — |

The LLM gives a **+0.12 op macro F1** improvement and halves the
force-fit rate versus the strongest ML baseline.

### Confidence calibration

The classifier is **overconfident**. ECE = <fill in>. At 0.6 self-reported
confidence, empirical accuracy is 0%. At ~0.95, empirical accuracy
is 60%. Escalation thresholds should be tuned against the reliability
curve, not raw confidence.


## Retrieval — evaluation

### Approach comparison (dev, 59 queries)

| Retriever | Recall@5 | MRR | Notes |
|---|---:|---:|---|
| Oracle-intent BM25 | 0.966 | 0.966 | Diagnostic only |
| **TF-IDF** | **0.746** | **0.493** | **Winner** |
| Hybrid RRF | 0.661 | 0.498 | |
| BM25 | 0.661 | 0.455 | |
| Predicted-intent BM25 | 0.610 | 0.610 | |
| Embedding | 0.576 | 0.429 | |
| Random (20-seed mean) | 0.442 | 0.268 | Floor |

**Winner:** TF-IDF, selected by predeclared rule (highest recall@5;
tie-break within Δ 0.02 favors simpler/cheaper).

### Human relevance audit (20 queries, 100 judgments)

- nDCG@5 = **0.592**
- Graded Precision@5 (≥1) = **0.330**

**Finding:** Intent-match Recall@5 is a valid but optimistic proxy.
Only 1 in 3 retrieved documents is even partially useful. The
automated metric captures **whether retrieval finds the right topic**;
the human audit captures **whether the retrieved precedent is
actionable**. These diverge because the corpus contains many
on-intent-but-generic brand responses ("we aim to respond within
20 days", "thanks, we'll pass this on") that match lexically without
providing usable grounding.

### Intent-conditioning result

| Variant | Recall@5 |
|---|---:|
| Oracle-intent BM25 | 0.966 |
| TF-IDF (unconditioned) | 0.746 |
| Predicted-intent BM25 | 0.610 |

**Finding:** Intent-conditioning is worth ~22 points of recall
*when the classifier is right*. With our classifier at 0.62 dev
accuracy, the same technique underperforms unconditioned TF-IDF
by 14 points. For the current pipeline, unconditioned retrieval is
correct; intent-conditioning becomes advantageous only when
classifier accuracy exceeds roughly 0.75.

### Implications for `06_agent`

- Retrieve **top-10**, not top-5 (recall@10 = 0.847 vs recall@5 = 0.746)
- Down-rank or filter generic boilerplate responses before grounding
- The classifier's `confidence` and `margin` signals remain the primary
  escalation inputs; retrieval scores are ordinal, not calibrated

  ## Retrieval — test results and limitations

TF-IDF was selected on dev (recall@5 = 0.746) and evaluated once on test:

| Metric | Test |
|---|---:|
| recall@5 | 0.532 |
| recall@10 | 0.748 |
| MRR | 0.342 |
| Corpus coverage | 0.942 |

### The dominant limitation: corpus size

The retrieval corpus contains **50 documents**. Every recall number is
bounded by this. The corpus is the intersection of:

1. Threads with a *substantive* brand response (5.4% of all GWRHelp
   responses; 87% of GWRHelp responses are classified `other`).
2. Threads with a label in the 04 training pool.
3. Threads excluded from golden dev and test.

Of 2,794 GWRHelp responses, only 150 are substantive, and only 140
threads carry one. After exclusions, 50 remain.

### Evidence that corpus size dominates

Recall@5 correlates directly with how many corpus docs share the
query's intent:

- `service_disruption`: 15 docs → recall@5 = 1.000
- `booking_issue`: 6 docs → recall@5 = 0.714
- `refund_request`: 2 docs → recall@5 = 0.200
- `lost_property`: 0 docs → recall@5 = 0.000

`lost_property` failures are **coverage failures**, not retrieval
failures. The corpus doesn't contain the intent at all.

### Dev-to-test gap

Dev recall@5 (0.746) exceeds test (0.532) by 0.21. The gap is driven
by different intent mixes: dev has 15 `delay_compensation` queries
against a proportionally larger corpus; test has 18 `delay_compensation`
and 23 `on_board_issue` queries against 5 and 6 corpus docs
respectively. The dev set happened to be easier.

### What this evaluation can and cannot claim

**Can claim:** TF-IDF outperformed BM25 (0.746 vs 0.661 on dev), hybrid
RRF (0.661), embeddings (0.576), and random (0.442). The relative
ranking of retrievers is credible.

**Cannot claim:** TF-IDF achieves recall@5 = 0.532 in production. The
absolute number is a floor under a severely undersized corpus. A
production corpus would contain thousands of substantive responses.

### Intent-conditioning diagnostic

| Variant | Dev recall@5 |
|---|---:|
| Oracle-intent BM25 | 0.966 |
| TF-IDF (unconditioned) | 0.746 |
| Predicted-intent BM25 | 0.610 |

Intent-conditioning helps **when the classifier is right** but hurts
when it's wrong. With the classifier at 0.62 dev accuracy, conditioned
retrieval underperforms unconditioned TF-IDF. Not used in the pipeline.

## 06 — Agent: outcome

The predeclared selection rule required `unsafe_automation_rate ≤ 0.10` on dev.
No candidate satisfied this gate. The fallback rule proceeded with all
candidates, and the simplicity tie-break selected `ungrounded`.

### Dev comparison

| Approach | Automation coverage | Mean universal | Unsupported rate | Unsafe automation rate |
|---|---:|---:|---:|---:|
| ungrounded | 1.000 | 13.19 | 0.254 | 0.678 |
| grounded_no_escalate | 1.000 | 12.68 | 0.542 | 0.678 |
| full_pipeline | 0.864 | 12.82 | 0.510 | 0.706 |
| escalate_all | 0.000 | — | — | 0.000 |

### Test results (chosen = ungrounded)

- 139 rows evaluated
- automation_coverage = 1.000
- mean_universal_auto = 13.37
- unsupported_rate_auto = 0.194
- **unsafe_automation_rate = 0.597**

### Findings

1. **Grounding did not improve reply quality.** Δ_grounding (B − A) = −0.51
   on dev. Grounded replies scored lower than ungrounded.
2. **Escalation did not align with the suitability rubric.** Precision 0.50,
   recall 0.10. The policy fires on 14% of dev; the suitability judge marks
   68% unsafe.
3. **The chosen agent is unsafe by the predeclared standard.** 59.7%
   of auto-handled test rows were labeled unsafe by the independent
   escalation-suitability judge.

### Root cause

The predeclared escalation thresholds (`τ_c = 0.40`, `τ_m = 0.15`) were
conservative and produced few escalations. The escalation-suitability
judge, using a closed-world rubric, marked a large majority of messages
as needing a human. These two signals are not aligned. The policy would
need to be re-derived from the suitability labels on dev to close the
gap.

### What this does NOT justify

- Changing the choice post-hoc. `ungrounded` is the correct output of
  the predeclared rule.
- Re-running test. Test is spent.
- Tuning against test. All thresholds were fixed before test.
## Threshold tuning — post-hoc note

The escalation thresholds (τ_c = 0.40, τ_m = 0.15) used in this notebook
were predeclared defaults, not dev-selected operating points. A dev-only
threshold sweep was added retroactively (Cell 4b) to document what a
properly-tuned policy would have selected.

The sweep shows [actual output — likely: no combination in the grid
passes the safety gate on dev, because 68% of dev rows are flagged unsafe
by the escalation-suitability judge while the classifier-confidence and
retrieval-coverage signals available to the policy do not correlate with
those flags].

Consequence: the fallback rule selected `ungrounded`. This was the
correct output of the predeclared rules given the pre-sweep thresholds.
The finding is documented; the fix (recalibrate escalation thresholds
against suitability labels, then re-evaluate on a fresh holdout) is
stated as future work.

The current test result stands. Test was evaluated once and locked.

## 06 — Agent: outcome

The predeclared safety gate (`unsafe_automation_rate ≤ 0.10`) failed on dev
for every candidate. A dev-only threshold sweep (Cell 4b) confirmed no
combination of τ_c ∈ {0.30..0.50} and τ_m ∈ {0.05..0.25} passes — because
68% of dev messages are labeled unsafe by the escalation-suitability
judge while the policy's signals (classifier confidence, retrieval
coverage) do not correlate with those labels.

The predeclared fallback selected `ungrounded` by simplicity. Test
confirmed:

- automation coverage: 1.000
- mean universal score: 13.37
- unsafe automation rate: **0.597**
- escalation recall vs. suitability labels: 0.000

### Findings

1. **Grounding did not help.** Δ_grounding (B − A) = −0.51 on dev.
   Grounded replies scored lower than ungrounded.
2. **Escalation policy does not align with the suitability rubric.**
   Precision 0.50, recall 0.10 on dev. The policy fires on 14% of dev;
   the judge flags 68%.
3. **The predeclared fallback did its job.** No silent override. The
   weakest-by-safety candidate was selected as the rules specified.

### Recommended v2

Re-derive escalation thresholds against the suitability labels on dev,
then evaluate on a fresh holdout. Not done in v1 because test is spent
and post-hoc selection would invalidate the predeclared-rule discipline
used throughout 04–06.
## 06 — Agent: diagnostic findings

The predeclared selection rule selected `ungrounded` via the fallback
path because no candidate passed the 10% safety gate. Three diagnostic
investigations explain why, and each identifies a distinct failure mode.

### Diagnostic 1 — Escalation signals do not discriminate

Dev distributions of safe (n=19) vs unsafe (n=40) messages:

| Signal | Safe (mean) | Unsafe (mean) |
|---|---:|---:|
| confidence_raw | 0.939 | 0.918 |
| confidence_calibrated | 0.602 | 0.626 |
| margin | 0.883 | 0.827 |

The distributions overlap heavily. This explains the flat threshold
sweep: adjusting τ_c or τ_m has no effect because the underlying signals
do not separate the two classes. The policy's only effective rules are
categorical: `intent ∈ {other, ambiguous}` (7 fires) and
`corpus_coverage == 0` (1 fire). Escalation precision = 0.50, recall =
0.10.

**Root cause:** the escalation policy relies on pipeline signals
(classifier confidence, retrieval coverage) that answer different
questions from the escalation-suitability rubric. A policy that
actually separates safe from unsafe would need to be driven by the
suitability judge itself at runtime — a different architecture than
what was frozen in 06.

### Diagnostic 2 — The grounded prompt hallucinates operational
claims from topical precedents

Δ_grounding = −0.51 on dev. Inspecting the 10 largest regressions
(`diagnostic_grounding_failures.csv`) reveals a consistent failure
mode: the grounded prompt encourages the model to synthesize
operational claims from precedents that are topically related but not
actually applicable. Representative cases:

- root_id 59200: a customer posts a bare link. Precedent 54019 contains
  "cancelled due to congestion". Grounded reply invents "the service was
  cancelled due to congestion". Ungrounded reply correctly says "not
  sure what you're referring to".
- root_id 1014147: customer can't sit in a reserved seat. Grounded
  reply invents "on this train there are no reserved seats — you can
  sit anywhere" and "a refund isn't available for this situation".
  Neither claim appears in the precedents.
- root_id 1208104: customer uses sarcasm ("Love a delayed train 🤔").
  Precedent 2306957 is a thank-you message. Grounded reply says
  "we'll make sure your kind words are passed on."

The system prompt contains two conflicting instructions: "Do NOT invent
policies" and "use precedents as grounding evidence for any operational
claims". When precedents are topically matched but semantically
inapplicable, the second instruction dominates.

**Root cause:** retrieval is intent-match-based, not relevance-based. The
corpus contains 50 documents at smoke-test scale; topical matches are
easy, useful precedents are not.

### Diagnostic 3 — Ungrounded is a strong baseline

Mean universal score on dev: ungrounded 13.19 vs grounded 12.68. The
LLM's generic empathetic-and-redirect replies score well on the rubric.
The engineering challenge in ResolveIQ is therefore not making replies
sound good; it is making them **grounded, operationally safe, and
appropriately escalated**.

### What this does not justify

- Re-running test. The one-shot rule holds.
- Re-tuning thresholds. Diagnostic 1 shows thresholds are not the
  bottleneck.
- A fresh holdout. The fixes require architecture changes (runtime risk
  classifier, relevance-gated precedent inclusion), not hyperparameter
  search.

### v2 recommendations

1. **Move the escalation-suitability judgment into the runtime policy.**
   The judge is 95% aligned with human labels on the 20-row spot check;
   using it as a per-message risk signal would give the policy real
   discriminative power.
2. **Gate precedent inclusion on relevance, not intent-match.** Only
   inject precedents when retrieval evidence crosses a
   usefulness threshold (e.g., high BM25 score, or a reranker above a
   confidence cutoff).
3. **Split the system prompt** for grounded and ungrounded modes. The
   grounded prompt should say explicitly: "If a precedent does not
   describe an equivalent situation, do not use its operational
   details."
4. **Grow the corpus.** A 50-document corpus at smoke-test scale is the
   dominant limit on grounded performance.

   # ResolveIQ — Final Report

## Executive summary
One paragraph: what was built, what the numbers are, what the finding is.

## 1. Problem framing
What the task is. Why customer-support automation needs grounding +
escalation. Scope and non-goals.

## 2. Data and brand selection (notebook 01)
- GWRHelp chosen from candidate brands
- N threads, distribution of intents in the raw corpus
- Reference to reports/figures/*_brand_*.png

## 3. Intent taxonomy (notebook 02)
- 11 intents (9 operational + other + ambiguous)
- Discovery method
- Coverage validation: mapped=0.880, other=0.113, ambiguous=0.007
- Taxonomy SHA: 7a05e4af...
- Reference to configs/intents.yaml

## 4. Golden set (notebook 03)
- 198 human-verified examples (59 dev / 139 test)
- Disjoint from coverage and training pool
- SHA: acde341d...
- Sample quality: 310 human-confirmed, 145 corrections

## 5. Classifier (notebook 04)
- Table: 4 approaches on dev
- Chosen: llm_zeroshot, op macro F1 = 0.747 on dev / 0.624 on test
- Confidence overconfidence: ECE = 0.16
- Weakness: delay_compensation F1 = 0.286 (per-intent table)
- SHA: 7d51251a...

## 6. Retrieval (notebook 05)
- Table: 6 approaches on dev
- Chosen: tfidf, recall@5 = 0.746 dev / 0.532 test
- Corpus limitation: 50 documents
- Human audit: nDCG@5 = 0.592, graded P@5 = 0.330
- SHA: 33dbaea4...

## 7. Agent (notebook 06)
- Pipeline: classify → retrieve → escalate or generate
- Safety gate failed on dev for all candidates
- Chosen: ungrounded (per predeclared fallback)
- Test: automation coverage 1.0, unsafe rate 0.597
- Three diagnostics explaining the failure
- SHA: dc6c09f6...

## 8. End-to-end evaluation (notebook 07)
- Cascade table
- Per-intent breakdown
- Safe automation coverage = 0.295
- Safe handling rate = 0.201
- Reference to reports/figures/*_test.png

## 9. Key findings
1. The classifier is the bottleneck, not the agent.
2. delay_compensation boundary is the single largest error source.
3. Grounding did not improve reply quality (Δ = −0.51 on dev).
4. Escalation policy signals do not discriminate safe from unsafe.
5. Corpus scale limits grounded generation.

## 10. Limitations
Copy from runs/evaluation/limitations.md

## 11. Future work
The v2 recommendations from each notebook's diagnostics:
- Fix the delay_compensation taxonomy boundary (add tie-break examples, split the intent, or add a rule override)
- Move escalation-suitability judgment into the runtime policy
- Gate precedent inclusion on relevance
- Grow the corpus to production scale
- Capture cost/latency in generation

## 12. Reproducibility appendix
- Environment (uv, Python version, key deps)
- Exact commands to reproduce
- All SHA-256 pins
- Reference to DECISIONS.md