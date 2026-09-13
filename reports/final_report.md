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