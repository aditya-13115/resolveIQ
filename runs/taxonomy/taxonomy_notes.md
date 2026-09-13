# Taxonomy notes � GWRHelp

- Source: `runs\brand_selection\first_inbound_per_thread.pkl`
- GWRHelp threads (raw):        1,612
- Analysis corpus (post-norm):  1,610
- Excluded (normalized empty):  2
  See `excluded_uninformative_messages.csv`
- Exploration sample: 100
- Coverage sample: 300 (see coverage_labeling_sheet.csv)
- Frozen version: 1
- Frozen SHA-256: `7a05e4af68a50981a3d38264b1aad8a4146fc90a342bb9804bcb5cb5148fe679`
- Git commit: `a2fc7d3b3e73cd512e5a352e9491723735edde4c`

## Method
1. Schema-validated load of first-inbound-per-thread.
2. Stratified exploration sample (length quantiles).
3. Lightweight normalization; rows that normalize to empty are quarantined.
4. Frequency + TF-IDF discovery (GWR-specific stopwords removed).
5. SVD + KMeans clustering as supporting evidence only.
6. Hand-authored candidate taxonomy with probe regexes for evidence counting.
7. Jaccard overlap on probe matches; >0.30 flagged for manual inspection.
8. Coverage labeling on 300 messages; mapped=0.880,
   other=0.113, ambiguous=0.007. All thresholds pass.
9. Examples stratified into prototypical / boundary / short.

## Non-goals
- No LLM classifier, no retrieval, no generation, no golden set.
- `brand_responses_classified.csv` was NOT used as ground truth.
- `evaluation/golden_set.jsonl` and friends were NOT read.

## Downstream contract (03_golden_set.ipynb)
Must read:
  - `configs/intents.yaml`
  - `runs/taxonomy/intents.yaml.sha256`
  - `runs/taxonomy/intent_examples.csv`
  - `runs/taxonomy/intent_distribution.csv` (if coverage was labelled)
  - `runs/taxonomy/excluded_uninformative_messages.csv`
Must record the frozen hash in the golden set manifest.

## Coverage validation

Rule-based coverage pass on N=300 messages:
- mapped: 0.880
- other: 0.113
- ambiguous: 0.007
- unlabelled: 0.000

All thresholds passed (mapped ≥ 0.80, other ≤ 0.15, ambiguous ≤ 0.10).

## Handoff to 03_golden_set.ipynb

The frozen taxonomy (SHA-256 recorded in `intents.yaml.sha256`) is the
source of truth for the golden set. `03_golden_set.ipynb` reads
`configs/intents.yaml` and verifies the hash before proceeding. Any drift
in the taxonomy invalidates the golden set's labels.

The 300-message coverage sample (`coverage_labeling_sheet.csv`) is
**excluded** from the golden set — its labels were rule-generated, not
human-verified. The golden set draws from a separate disjoint pool.