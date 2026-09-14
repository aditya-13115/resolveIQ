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