

## Final Brand Selection

- **Selected brand:** GWRHelp
- **Runner-up:** Tesco
- **Quantitative winner:** AmazonHelp
- **Audit winner:** GWRHelp
- **Final-score winner:** GWRHelp
- **Gap (top two):** 0.0137
- **Rule applied:** gap 0.0137 < 0.10 -> audit winner
- **Quantitative score:** 0.4058
- **Audit mean:** 4.12/5
- **Combined score:** 0.5935
- **Manual audit:** 10 threads per candidate from a 50-thread stratified pool

### Decision

GWRHelp won the manual audit (4.12/5), leading on response usefulness (5/5),
resolution evidence (4/5), behavioral consistency (5/5), and data cleanliness
(5/5). Five of ten reviewed threads showed a visible resolution, compared to
almost zero for AmazonHelp. The quantitative winner (AmazonHelp) had roughly
7x more threads but a reply pattern dominated by link/DM handoffs (29.3% vs
3.6% for GWRHelp) and a lower manual audit score (3.00 vs 4.12).

The top two candidates (GWRHelp 0.5935, Tesco 0.5798) are separated by only
0.014 in the combined score. The predefined tie-break rule — when the
quantitative and audit winners differ and the gap is below 0.10, select the
audit winner — therefore applies. GWRHelp is selected. For an assignment
where proof matters more than system size, the cleaner, higher-quality corpus
is the better choice.

### Tradeoffs accepted

- **Volume:** 1,612 threads vs AmazonHelp's 12,250. Still well above the
  minimum needed for a 6-9 intent taxonomy and a 150-250 example golden set.
- **Intent diversity:** narrower (mostly trains, bookings, cancellations),
  but each intent is well-represented and clean.
- **Fewer ambiguous cases:** some, but fewer than AmazonHelp. Compensated
  by higher per-case clarity and stronger behavioral consistency.

### Rejected candidates

- **AmazonHelp:** Volume leader but reply pattern dominated by link/DM
  handoffs. Almost no visible resolutions. Hard to demonstrate safe
  auto-handling when the ground truth says "escalate."
- **Tesco:** Strong runner-up (gap 0.014). Slightly noisier data and lower
  consistency rating, but otherwise defensible.
- **AskPlayStation:** High ambiguity is useful for failure analysis, but
  high-risk intents (account access, refunds) make auto-handling unsafe.
- **VerizonSupport:** Inconsistent tone, misrouted replies, generic
  handoffs. Weakest candidate.

### Limitations of the EDA Response Classifier

The response classifier used during the EDA is a heuristic, not human ground
truth. It is intentionally strict: brand replies must match positive evidence
patterns to be classified as `informational`, `investigation`, or
`resolution`. Replies that don't match any pattern fall into the `other`
bucket.

Observed distribution across the sampled brand replies:

- `other`: 58.76%
- `link_handoff`: 16.72%
- `handoff_dm`: 14.17%
- `informational`: 3.31%
- `info_request`: 3.20%
- `empathy_only`: 3.04%
- `investigation`: 0.64%
- `resolution`: 0.18%

Implications:

- The `substantive_response_rate` metric used in the quantitative brand
  score is a coarse signal, not a high-fidelity quality measure. It is one
  input to candidate ranking, not a benchmark.
- Brand selection did not depend on this metric alone. The final choice
  (GWRHelp) was validated by a manual audit of 10 threads per candidate.
- This classifier must not be reused as-is for the intent taxonomy or the
  golden evaluation set. Those will be built through manual annotation on
  the selected brand only.

## Key Decisions

### Rule 1 — Sample the unit you evaluate

> If the evaluation unit is a conversation, sample conversations — not individual tweets.

### Rule 2 — Every score component must discriminate

> A metric that is constant or tautological across candidates should not influence ranking.

### Rule 3 — Name proxies honestly

> A keyword-based topic proxy is not an intent taxonomy.

### Rule 4 — Separate routing from substantive support

> A brand response existing does not mean the issue was meaningfully addressed.

### Rule 5 — Quantitative ranking is not the final decision

> Use metrics to shortlist candidates; use manual audit to validate the final brand.

### Rule 6 — Heuristic classifiers are bounded tools

> A regex-based classifier is a ranking signal, not a quality benchmark. Its coverage and error rate must be reported alongside its outputs.


## Golden set construction (03_golden_set.ipynb)

**Decision:** Coverage-oriented sampling, not prevalence-representative.

**Rationale:** Rare intents (`lost_property`) would be severely
underrepresented in a purely random sample. Targeted supplementation
brings each operational intent to a minimum of 8 examples. The `_source`
column preserves the natural/targeted distinction so metrics can be
reported both ways.

**Decision:** Human confirmation of every annotation-pool row.

**Rationale:** A rule + TF-IDF cascade auto-suggested labels, but every
row in the 310-row annotation pool was human-confirmed. Cascade
agreement was ~53%. This satisfies the requirement that the golden set
is human-verified, not machine-labeled.

**Decision:** Fall back to random split when stratified split fails.

**Rationale:** `ambiguous` has only 1 example, below the stratified
minimum. Random split is used and the constraint is documented. An
alternative (dropping `ambiguous`) was rejected because the residual
class must be evaluated.

**Decision:** Exclude the 300-message coverage sample from the golden set.

**Rationale:** Coverage labels were rule-generated. Reusing them as
golden-set labels would leak the taxonomy's own rules into the
evaluation and inflate classifier scores.