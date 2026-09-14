# Decision Log

Chronological record of non-obvious choices across the project. Each entry
states the decision, the rationale, and the consequence. Decisions are
listed in the order they were made.

---

## Day 1 — Brand selection

### D1. Sample the unit you evaluate

**Decision.** Sample and evaluate at the thread level, not the tweet level.

**Rationale.** The evaluation unit is a customer conversation. Sampling
individual tweets would break the reconstruction of a thread and make
response attribution ambiguous.

**Consequence.** All downstream artifacts use `root_id` as the primary key.

---

### D2. Never let volume alone decide the brand

**Decision.** Use a two-stage selection: quantitative shortlist, then
manual audit of 10 threads per candidate.

**Rationale.** AmazonHelp had ~7× more threads than GWRHelp but a reply
pattern dominated by link/DM handoffs (29.3% vs 3.6%). A larger corpus
with worse evidence is not a better corpus.

**Consequence.** GWRHelp selected (audit 4.12/5, combined 0.5935 vs
Tesco's 0.5798). Tie-break rule: gap < 0.10 → audit winner.

---

### D3. Heuristic response classifiers are ranking signals, not benchmarks

**Decision.** Use the EDA response classifier only for brand scoring. Do
not reuse it as ground truth for the taxonomy or the golden set.

**Rationale.** The classifier is regex-based. 58.76% of all brand replies
land in `other`. It is a coarse quality signal, not a labeled dataset.

**Consequence.** Taxonomy and golden set are built through manual
annotation only. The classifier's outputs are documented but not reused.

---

## Day 2 — Taxonomy

### D4. Derive intents from the corpus, not from an LLM

**Decision.** Discover candidate intents from frequency, TF-IDF, and
SVD/KMeans clustering on GWRHelp first-inbound messages. Do not import a
generic taxonomy.

**Rationale.** A generic customer-service taxonomy (refund / booking /
complaint) would misrepresent GWRHelp's actual distribution, which is
dominated by delays and on-board conditions.

**Consequence.** 9 operational intents + `other` + `ambiguous`. Coverage
validation on a 300-message sample: mapped = 0.880, other = 0.113,
ambiguous = 0.007.

---

### D5. `other` and `ambiguous` are first-class intents

**Decision.** Include both as named intents with include/exclude rules,
not as a residual catch-all.

**Rationale.** The classifier must be able to say "nothing fits" or
"two fit equally" without forcing a wrong label. This is more honest and
simpler to evaluate.

**Consequence.** The intent count is 11 (9 + 2). The classifier's
force-fit rate is measured explicitly (test: 0.526).

---

### D6. Quarantine, don't crash, on uninformative messages

**Decision.** Messages that normalize to empty (bare mentions, bare URLs)
are excluded from analysis but written to
`excluded_uninformative_messages.csv`.

**Rationale.** These are real data, but they carry no intent signal. A
hard assertion would force us to keep them; deletion would lose the audit
trail.

**Consequence.** 2 of 1,612 GWRHelp messages are quarantined. Analysis
corpus is 1,610.

---

## Day 3 — Golden set

### D7. Coverage-oriented sampling, not prevalence-representative

**Decision.** Stratify the golden set: 10 natural + 10 targeted per
intent. Rare intents are supplemented to a minimum of 8 examples.

**Rationale.** A purely random sample would leave `lost_property` (1.6%
of traffic) with 1–2 examples, making its per-class metrics meaningless.

**Consequence.** Natural-slice and targeted-slice metrics are reported
separately. Accuracy is a secondary metric; macro F1 is primary.

---

### D8. Human confirmation of every annotation-pool row

**Decision.** Auto-suggest labels with a rule + TF-IDF cascade, then
require `human_confirmed = y` on every row before freezing.

**Rationale.** Machine-labeled rows would not constitute a golden set.
The cascade agreement was 53%; 145 of 310 rows were corrected.

**Consequence.** 198 examples frozen (59 dev / 139 test). SHA `acde341d...`.

---

### D9. Coverage set is not the golden set

**Decision.** Exclude all root_ids from `coverage_labeling_sheet.csv`
and `intent_examples.csv` when building the golden set.

**Rationale.** Coverage labels were rule-generated. Reusing them would
leak the taxonomy's own rules into evaluation.

**Consequence.** Golden set and coverage set are provably disjoint at
root_id and normalized-text level.

---

### D10. Test split is evaluated once

**Decision.** The 139-row test split is used exactly once, with the
chosen classifier, after dev-selection is complete.

**Rationale.** Any tuning against test would invalidate the final claim.

**Consequence.** `TEST_LOCK.json` in each notebook verifies hashes and
refuses re-runs. When the notebook was re-executed after a schema-only
change, the lock was reset and the test re-run from cache — the
predictions file was byte-identical. Documented in `06`.

---

## Day 4 — Classifier

### D11. Few-shot LLM over classical baselines

**Decision.** Three approaches evaluated on dev: rules, TF-IDF+LR (two
training regimes), few-shot LLM. Winner by predeclared rule.

**Rationale.** Rules give a floor. TF-IDF+LR gives an ML baseline.
The LLM needs to beat both to justify its cost.

**Consequence.** Few-shot LLM won: 0.747 op macro F1 on dev (vs 0.556
for the best TF-IDF regime). Test: 0.624.

---

### D12. Rules do not attempt to be competitive

**Decision.** The rules baseline is intentionally simple — nine regex
patterns, first-match-wins.

**Rationale.** Its purpose is a floor, not a competitor. Tuning rules
to close the gap to ML would obscure what "no ML" achieves.

**Consequence.** Rules F1 on `delay_compensation` = 0.000. Documented,
not fixed.

---

### D13. Classifier identifier retained despite misleading name

**Decision.** Keep the identifier `llm_zeroshot` in frozen artifacts,
even though the method is few-shot.

**Rationale.** Renaming after test evaluation would invalidate
`TEST_LOCK.json` and force a test re-run. That violates the one-shot
protocol.

**Consequence.** The report refers to it as "few-shot LLM". The
artifact filename retains the legacy identifier.

---

## Day 5 — Retrieval

### D14. Corpus disjointness is a hard gate

**Decision.** Exclude all golden dev/test root_ids AND their normalized
texts from the retrieval corpus. Assert at both levels.

**Rationale.** A same-customer leakage (via `root_id`) or same-message
leakage (via `text_hash`) would make retrieval appear to work when it
was actually finding the answer key.

**Consequence.** 50-document corpus. Every retriever evaluated against
the same disjoint benchmark.

---

### D15. Relevance = intent-match (documented proxy)

**Decision.** A retrieved document is "relevant" if its intent equals
the query's true intent.

**Rationale.** No human relevance judgments exist. Intent-match is
objective, reproducible, and testable.

**Consequence.** A 20-query human audit was added to check whether the
proxy correlates with usefulness. It does, weakly: nDCG@5 = 0.592,
graded P@5 = 0.330. Automated recall@5 overstates usefulness.

---

### D16. Intent-conditioned retrieval is diagnostic

**Decision.** Evaluate `oracle_intent_bm25` and `predicted_intent_bm25`
as diagnostics, not as candidates for selection.

**Rationale.** Oracle uses the true intent (unavailable at runtime).
Predicted uses the classifier (which may be wrong). The gap between them
measures the cost of classifier errors.

**Consequence.** Result: oracle 0.966, unconditioned 0.746, predicted
0.610. Intent-conditioning helps only when classifier accuracy exceeds
~0.75.

---

## Day 6 — Agent

### D17. Escalation-suitability judge is independent of generation

**Decision.** The judge receives only `customer_text`. Not intent, not
confidence, not retrieved context, not the generated reply.

**Rationale.** The purpose is to produce an independent label for
"should this have been automated?" If the judge saw the classifier's
output or the reply, the label would be tainted by the pipeline's own
decisions.

**Consequence.** Judge-human agreement on the 20-row spot check is 0.95.

---

### D18. Safety gate is predeclared, not tuned

**Decision.** `unsafe_automation_rate ≤ 0.10` is fixed before looking at
any dev result.

**Rationale.** Tuning the gate against dev would make the selection rule
a form of test contamination.

**Consequence.** Every candidate failed the gate. Documented as the
primary finding, not "fixed" by lowering the bar.

---

### D19. Fallback preserves the predeclared rule

**Decision.** When no candidate passes the gate, proceed with all
candidates and prefer the simplest.

**Rationale.** Overriding the fallback after seeing the failure would
violate the same discipline that produced the failure.

**Consequence.** `ungrounded` selected. Test: unsafe rate 0.597.

---

### D20. Three judges, three rubrics, three SHAs

**Decision.** Escalation-suitability, universal quality, and groundedness
are scored by three separate rubric prompts, each frozen and hashed
before any judging.

**Rationale.** Each rubric answers a different question. Merging them
into one prompt would blur the signal.

**Consequence.** Three `*_rubric_sha256` fields in `chosen_agent.json`.

---

### D21. Test generation and test judging are separately locked

**Decision.** `TEST_LOCK.json` locks generation. `EVAL_LOCK.json` locks
all judging artifacts.

**Rationale.** Generation and judging are separate computational events.
Both must be frozen for the evaluation to be reproducible.

**Consequence.** Any re-run of a judging cell after `EVAL_LOCK.json`
exists is refused.

---

## Day 7 — Evaluation

### D22. Report four headline numbers, not one

**Decision.** Report classifier F1, retrieval recall@5, reply quality,
and safe automation coverage separately.

**Rationale.** An agent that automates everything unsafely can have a
high reply-quality score. Collapsing the pipeline into one metric hides
the trade-off.

**Consequence.** The report's headline table has 11 rows.

---

### D23. Distinguish "earliest defect" from "observed failure"

**Decision.** Two attribution columns: `earliest_defect_stage` (which
pipeline component first failed) and `observed_outcome` (what the
system actually produced).

**Rationale.** A correct escalation with a wrong classifier prediction
has a defect at the classifier stage, but the escalation was the right
action. Both views matter.

**Consequence.** Cascade tables report both.

---

### D24. Do not fix the `delay_compensation` boundary in v1

**Decision.** The classifier's weakest intent boundary is documented, not
patched. A v2 recommendation specifies the fix.

**Rationale.** Test is spent. Fixing the boundary would require a fresh
holdout to validate. Post-hoc tuning against the same test would
invalidate the one-shot protocol.

**Consequence.** `delay_compensation` F1 = 0.286 on test, documented
as the single largest error source.

---

### D25. Cost and latency remain uncaptured

**Decision.** Do not estimate token cost or latency from cached LLM
calls. Note as a limitation.

**Rationale.** The cache stores responses, not call metadata. Estimating
would be misleading.

**Consequence.** `metrics.json` records `cost_latency.note` as
"Not captured in this run."

---

## Summary

- 25 decisions recorded.
- Every decision is either (a) documented in a notebook or (b) reflected
  in a frozen artifact.
- Test is evaluated once. No artifact has been modified after its
  `TEST_LOCK.json` was written.