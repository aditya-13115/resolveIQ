

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
7x more threads but ~30 pp lower substantive response behavior and a reply
pattern dominated by link/DM handoffs.

The top two candidates (GWRHelp 0.5935, Tesco 0.5798) are within 0.014,
statistically indistinguishable at this sample size. The tie-break rule
(audit winner when gap < 0.10) selects GWRHelp, which also wins on audit
mean. For an assignment where proof matters more than system size, the
cleaner, higher-quality corpus is the better choice.

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

